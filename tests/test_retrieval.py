from __future__ import annotations

import pytest

from packages.kb.models.retrieval import RetrievalRequest
from packages.kb.retrieval.service import retrieve


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retrieve_returns_results_for_known_query() -> None:
    """A query about the content of an ingested paper should return non-empty results."""
    response = await retrieve(
        RetrievalRequest(
            query="protein crystallization",
            k=10,
            rerank_top_n=3,
        )
    )
    assert len(response.chunks) > 0
    assert response.total_candidates > 0
    assert response.retrieval_ms >= 0

    top_chunk = response.chunks[0]
    assert top_chunk.content
    assert top_chunk.title
    assert top_chunk.source_url
    if response.rerank_ms is not None:
        assert top_chunk.rerank_score is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retrieve_respects_source_type_filter() -> None:
    """Filtering by a non-existent source_type should return zero results."""
    response = await retrieve(
        RetrievalRequest(
            query="protein crystallization",
            source_types=["nonexistent_type"],
            k=10,
            rerank_top_n=5,
        )
    )
    assert len(response.chunks) == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retrieve_disable_reranker() -> None:
    """Disabling reranker returns chunks without rerank scores."""
    response = await retrieve(
        RetrievalRequest(
            query="microgravity",
            k=10,
            rerank_top_n=3,
            use_reranker=False,
        )
    )
    assert response.rerank_ms is None
    if response.chunks:
        assert response.chunks[0].rerank_score is None
