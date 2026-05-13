from __future__ import annotations

import time

import structlog

from packages.kb.models.retrieval import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievedChunk,
)
from packages.kb.retrieval.hybrid import hybrid_search
from packages.kb.retrieval.reranker import rerank

logger = structlog.get_logger(__name__)


async def retrieve(req: RetrievalRequest) -> RetrievalResponse:
    """Retrieve relevant chunks for a query.

    Pipeline:
    1. Hybrid search (dense + sparse) returns up to k candidates.
    2. Optionally rerank candidates to produce top_n final results.

    Sub-agents in Layer 3 call this with appropriate source_types filters.
    """
    overall_start = time.monotonic()

    retrieval_start = time.monotonic()
    candidates = await hybrid_search(
        query=req.query,
        source_types=req.source_types,
        organization=req.organization,
        k=req.k,
        dense_weight=req.dense_weight,
    )
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    total_candidates = len(candidates)

    rerank_ms: int | None = None
    final_chunks: list[RetrievedChunk]
    if req.use_reranker and candidates:
        rerank_start = time.monotonic()
        final_chunks = await rerank(
            query=req.query,
            chunks=candidates,
            top_n=req.rerank_top_n,
        )
        rerank_ms = int((time.monotonic() - rerank_start) * 1000)
    else:
        final_chunks = candidates[: req.rerank_top_n]

    logger.info(
        "retrieve_complete",
        query_length=len(req.query),
        candidates=total_candidates,
        returned=len(final_chunks),
        retrieval_ms=retrieval_ms,
        rerank_ms=rerank_ms,
        total_ms=int((time.monotonic() - overall_start) * 1000),
    )

    return RetrievalResponse(
        chunks=final_chunks,
        query=req.query,
        total_candidates=total_candidates,
        retrieval_ms=retrieval_ms,
        rerank_ms=rerank_ms,
    )
