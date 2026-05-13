from __future__ import annotations

import cohere
import structlog

from apps.api.config import get_settings
from packages.kb.models.retrieval import RetrievedChunk

logger = structlog.get_logger(__name__)

_client: cohere.AsyncClient | None = None


def _get_client() -> cohere.AsyncClient:
    global _client
    if _client is None:
        _client = cohere.AsyncClient(api_key=get_settings().cohere_api_key)
    return _client


async def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_n: int,
) -> list[RetrievedChunk]:
    """Rerank chunks using Cohere rerank-v3.5.

    Returns top_n chunks sorted by rerank score descending.
    Chunks not in the top_n are dropped.
    """
    if not chunks:
        return []

    top_n = min(top_n, len(chunks))

    documents = [c.content for c in chunks]

    client = _get_client()
    response = await client.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=top_n,
    )

    reranked: list[RetrievedChunk] = []
    for result in response.results:
        chunk = chunks[result.index].model_copy(update={"rerank_score": result.relevance_score})
        reranked.append(chunk)

    logger.info(
        "rerank_complete",
        query_length=len(query),
        input_count=len(chunks),
        output_count=len(reranked),
    )
    return reranked
