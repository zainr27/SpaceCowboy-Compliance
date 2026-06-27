from __future__ import annotations

from functools import lru_cache

import structlog
import voyageai

from apps.api.config import get_settings
from packages.kb.models.schemas import EmbeddedChunk, RawChunk

logger = structlog.get_logger(__name__)

_BATCH_SIZE = 128  # Voyage API limit
_MODEL = "voyage-3-large"


@lru_cache(maxsize=1)
def _get_client() -> voyageai.AsyncClient:
    """Process-wide Voyage client, cached to reuse its connection pool across
    the many per-query embedding calls a single orchestration makes."""
    settings = get_settings()
    return voyageai.AsyncClient(api_key=settings.voyage_api_key)


async def embed_chunks(chunks: list[RawChunk]) -> list[EmbeddedChunk]:
    """Embed a list of raw chunks in batches.

    Uses input_type='document' for the corpus side; queries should use
    input_type='query' when retrieving (see retrieval module).
    """
    if not chunks:
        return []

    client = _get_client()
    embedded: list[EmbeddedChunk] = []

    # Process in batches to respect API limits
    for batch_start in range(0, len(chunks), _BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _BATCH_SIZE]
        texts = [c.content for c in batch]

        logger.info(
            "embedding_batch",
            batch_start=batch_start,
            batch_size=len(batch),
            total=len(chunks),
        )

        result = await client.embed(
            texts=texts,
            model=_MODEL,
            input_type="document",
        )

        for raw, vector in zip(batch, result.embeddings, strict=True):
            embedded.append(
                EmbeddedChunk(
                    **raw.model_dump(),
                    embedding=vector,
                )
            )

    logger.info("embedded_all_chunks", count=len(embedded), model=_MODEL)
    return embedded


async def embed_query(query: str) -> list[float]:
    """Embed a single query string. Used by retrieval, not ingestion.

    Note input_type='query' differs from 'document' for asymmetric retrieval.
    """
    client = _get_client()
    result = await client.embed(
        texts=[query],
        model=_MODEL,
        input_type="query",
    )
    return result.embeddings[0]
