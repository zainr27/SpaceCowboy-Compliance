from __future__ import annotations

import structlog
from sqlalchemy import text

from packages.kb.ingestion.embedder import embed_query
from packages.kb.models.retrieval import RetrievedChunk
from packages.kb.storage.database import get_session

logger = structlog.get_logger(__name__)

# RRF constant. 60 is the standard from the original paper; works well across domains.
_RRF_K = 60


async def hybrid_search(
    query: str,
    source_types: list[str] | None = None,
    organization: str | None = None,
    k: int = 20,
    dense_weight: float = 0.7,
) -> list[RetrievedChunk]:
    """Run dense + sparse retrieval, fuse via Reciprocal Rank Fusion.

    Returns up to k chunks ranked by fused score. Each chunk includes
    per-method scores for debugging.
    """
    sparse_weight = 1.0 - dense_weight

    # Embed the query (note: input_type='query', not 'document')
    query_vector = await embed_query(query)

    # Build the SQL. Both halves run in parallel within a single statement,
    # then we fuse ranks in the outer query.
    sql = text("""
    WITH dense AS (
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            c.page_number,
            c.section_path,
            c.chunk_type,
            d.source_url,
            d.source_type,
            d.title,
            d.organization,
            1 - (c.embedding <=> CAST(:query_vec AS vector)) AS dense_score,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> CAST(:query_vec AS vector)) AS dense_rank
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
            AND (CAST(:source_types AS text[]) IS NULL OR d.source_type = ANY(CAST(:source_types AS text[])))
            AND (CAST(:organization AS text) IS NULL OR d.organization = :organization)
        ORDER BY c.embedding <=> CAST(:query_vec AS vector)
        LIMIT :inner_k
    ),
    sparse AS (
        SELECT
            c.id AS chunk_id,
            ts_rank_cd(c.content_tsv, plainto_tsquery('english', :query_text)) AS sparse_score,
            ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.content_tsv, plainto_tsquery('english', :query_text)) DESC) AS sparse_rank
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.content_tsv @@ plainto_tsquery('english', :query_text)
            AND (CAST(:source_types AS text[]) IS NULL OR d.source_type = ANY(CAST(:source_types AS text[])))
            AND (CAST(:organization AS text) IS NULL OR d.organization = :organization)
        ORDER BY sparse_score DESC
        LIMIT :inner_k
    ),
    fused AS (
        SELECT
            COALESCE(d.chunk_id, s.chunk_id) AS chunk_id,
            d.document_id,
            d.content,
            d.page_number,
            d.section_path,
            d.chunk_type,
            d.source_url,
            d.source_type,
            d.title,
            d.dense_score,
            s.sparse_score,
            (
                COALESCE(:dense_weight / (:rrf_k + d.dense_rank), 0)
                + COALESCE(:sparse_weight / (:rrf_k + s.sparse_rank), 0)
            ) AS fusion_score
        FROM dense d
        FULL OUTER JOIN sparse s ON d.chunk_id = s.chunk_id
    )
    SELECT
        f.chunk_id,
        f.document_id,
        f.content,
        f.page_number,
        f.section_path,
        f.chunk_type,
        f.source_url,
        f.source_type,
        f.title,
        f.dense_score,
        f.sparse_score,
        f.fusion_score,
        -- Re-fetch document fields for rows that came only from sparse
        COALESCE(f.document_id, sp_doc.id) AS resolved_document_id,
        COALESCE(f.content, sp_chunk.content) AS resolved_content,
        COALESCE(f.page_number, sp_chunk.page_number) AS resolved_page_number,
        COALESCE(f.section_path, sp_chunk.section_path) AS resolved_section_path,
        COALESCE(f.chunk_type, sp_chunk.chunk_type) AS resolved_chunk_type,
        COALESCE(f.source_url, sp_doc.source_url) AS resolved_source_url,
        COALESCE(f.source_type, sp_doc.source_type) AS resolved_source_type,
        COALESCE(f.title, sp_doc.title) AS resolved_title
    FROM fused f
    LEFT JOIN chunks sp_chunk ON sp_chunk.id = f.chunk_id AND f.content IS NULL
    LEFT JOIN documents sp_doc ON sp_doc.id = sp_chunk.document_id AND f.document_id IS NULL
    ORDER BY f.fusion_score DESC
    LIMIT :outer_k
    """)

    # Inner k controls how many candidates each retriever returns before fusion.
    # We pull 2x the final k from each side to give RRF room to work.
    inner_k = k * 2

    async with get_session() as session:
        result = await session.execute(
            sql,
            {
                "query_vec": str(query_vector),  # pgvector accepts a list-literal string
                "query_text": query,
                "source_types": source_types,
                "organization": organization,
                "inner_k": inner_k,
                "outer_k": k,
                "dense_weight": dense_weight,
                "sparse_weight": sparse_weight,
                "rrf_k": _RRF_K,
            },
        )
        rows = result.mappings().all()

    chunks: list[RetrievedChunk] = []
    for row in rows:
        chunks.append(
            RetrievedChunk(
                chunk_id=row["chunk_id"],
                document_id=row["resolved_document_id"],
                content=row["resolved_content"],
                source_url=row["resolved_source_url"],
                source_type=row["resolved_source_type"],
                title=row["resolved_title"],
                page_number=row["resolved_page_number"],
                section_path=row["resolved_section_path"],
                chunk_type=row["resolved_chunk_type"],
                dense_score=row["dense_score"],
                sparse_score=row["sparse_score"],
                fusion_score=row["fusion_score"],
            )
        )

    logger.info(
        "hybrid_search_complete",
        query_length=len(query),
        candidates=len(chunks),
        source_types=source_types,
    )
    return chunks
