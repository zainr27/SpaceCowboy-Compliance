from __future__ import annotations

import time
from pathlib import Path

import structlog

from packages.kb.ingestion.chunker import chunk_elements
from packages.kb.ingestion.embedder import embed_chunks
from packages.kb.ingestion.loaders import compute_file_checksum, load_pdf_elements
from packages.kb.models.schemas import DocumentMetadata, IngestionResult
from packages.kb.storage.repository import (
    get_document_by_checksum,
    ingest_document_if_new,
)

logger = structlog.get_logger(__name__)


async def ingest_pdf(
    pdf_path: Path,
    metadata: DocumentMetadata,
) -> IngestionResult:
    """Run the full ingestion pipeline for a single PDF.

    1. Compute checksum, skip if already ingested.
    2. Parse PDF into elements.
    3. Chunk elements by title/section.
    4. Embed chunks in batches.
    5. Insert document + chunks atomically.
    """
    start = time.monotonic()
    pdf_path = pdf_path.resolve()
    logger.info("ingestion_start", path=str(pdf_path), title=metadata.title)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Stage 0: checksum + dedup check
    checksum = compute_file_checksum(pdf_path)
    existing = await get_document_by_checksum(checksum)
    if existing is not None:
        logger.info("skip_existing_document", checksum=checksum)
        return IngestionResult(
            document_id=str(existing.id),
            title=existing.title,
            source_type=existing.source_type,
            chunks_inserted=0,
            chunks_embedded=0,
            skipped_existing=True,
            duration_seconds=time.monotonic() - start,
        )

    # Stage 1: parse
    elements = load_pdf_elements(pdf_path)

    # Stage 2: chunk
    raw_chunks = chunk_elements(elements)
    if not raw_chunks:
        raise ValueError(f"No chunks produced from {pdf_path}")

    # Stage 3: embed
    embedded = await embed_chunks(raw_chunks)

    # Stage 4: persist
    result = await ingest_document_if_new(
        metadata=metadata,
        raw_path=pdf_path,
        checksum=checksum,
        embedded_chunks=embedded,
    )

    logger.info(
        "ingestion_complete",
        document_id=result.document_id,
        chunks=result.chunks_inserted,
        duration_seconds=result.duration_seconds,
    )
    return result
