from __future__ import annotations

import time

import structlog

from packages.kb.models.retrieval import RetrievalRequest, RetrievalResponse
from packages.kb.retrieval.hybrid import hybrid_search
from packages.kb.retrieval.reranker import rerank

logger = structlog.get_logger(__name__)


async def retrieve(request: RetrievalRequest) -> RetrievalResponse:
    """Run hybrid search, optionally rerank, return structured response."""
    t0 = time.monotonic()

    chunks = await hybrid_search(
        query=request.query,
        source_types=request.source_types,
        organization=request.organization,
        k=request.k,
        dense_weight=request.dense_weight,
    )

    retrieval_ms = int((time.monotonic() - t0) * 1000)
    total_candidates = len(chunks)

    rerank_ms: int | None = None
    if request.use_reranker and chunks:
        t1 = time.monotonic()
        chunks = await rerank(
            query=request.query,
            chunks=chunks,
            top_n=request.rerank_top_n,
        )
        rerank_ms = int((time.monotonic() - t1) * 1000)
    else:
        chunks = chunks[: request.rerank_top_n]

    logger.info(
        "retrieve_complete",
        query_length=len(request.query),
        total_candidates=total_candidates,
        returned=len(chunks),
        retrieval_ms=retrieval_ms,
        rerank_ms=rerank_ms,
    )

    return RetrievalResponse(
        chunks=chunks,
        query=request.query,
        total_candidates=total_candidates,
        retrieval_ms=retrieval_ms,
        rerank_ms=rerank_ms,
    )
