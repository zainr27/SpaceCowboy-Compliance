from __future__ import annotations

import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from packages.kb.ingestion.chunker import compute_content_hash
from packages.kb.models.schemas import (
    DocumentMetadata,
    EmbeddedChunk,
    IngestionResult,
)
from packages.kb.storage.database import get_session
from packages.kb.storage.models import Chunk, Document

logger = structlog.get_logger(__name__)


async def get_document_by_checksum(checksum: str) -> Document | None:
    """Look up a document by its file checksum (for dedup)."""
    async with get_session() as session:
        result = await session.execute(select(Document).where(Document.checksum == checksum))
        return result.scalar_one_or_none()


async def insert_document(
    metadata: DocumentMetadata,
    raw_path: Path,
    checksum: str,
) -> uuid.UUID:
    """Insert a document row, return its ID.

    Raises IntegrityError if the checksum already exists. Caller should
    catch and decide whether to skip or re-ingest.
    """
    async with get_session() as session:
        doc = Document(
            source_url=metadata.source_url,
            source_type=metadata.source_type,
            title=metadata.title,
            publication_date=metadata.publication_date,
            organization=metadata.organization,
            raw_path=str(raw_path),
            checksum=checksum,
            doc_metadata=metadata.extra,
        )
        session.add(doc)
        await session.flush()
        doc_id = doc.id
        logger.info("inserted_document", document_id=str(doc_id), title=metadata.title)
        return doc_id


async def insert_chunks(
    document_id: uuid.UUID,
    chunks: list[EmbeddedChunk],
) -> int:
    """Bulk insert chunks for a document."""
    if not chunks:
        return 0

    async with get_session() as session:
        rows = [
            Chunk(
                document_id=document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                content_hash=compute_content_hash(c.content),
                page_number=c.page_number,
                section_path=c.section_path,
                chunk_type=c.chunk_type,
                embedding=c.embedding,
                token_count=c.token_count,
            )
            for c in chunks
        ]
        session.add_all(rows)
        await session.flush()
        logger.info(
            "inserted_chunks",
            document_id=str(document_id),
            count=len(rows),
        )
        return len(rows)


async def ingest_document_if_new(
    metadata: DocumentMetadata,
    raw_path: Path,
    checksum: str,
    embedded_chunks: list[EmbeddedChunk],
) -> IngestionResult:
    """High-level: insert document + chunks atomically.

    Skips if a document with the same checksum already exists.
    """
    start = time.monotonic()

    existing = await get_document_by_checksum(checksum)
    if existing is not None:
        logger.info(
            "document_already_ingested",
            checksum=checksum,
            existing_id=str(existing.id),
        )
        return IngestionResult(
            document_id=str(existing.id),
            title=existing.title,
            source_type=existing.source_type,
            chunks_inserted=0,
            chunks_embedded=0,
            skipped_existing=True,
            duration_seconds=time.monotonic() - start,
        )

    try:
        doc_id = await insert_document(metadata, raw_path, checksum)
    except IntegrityError:
        # Race condition: another process inserted between our check and insert
        existing = await get_document_by_checksum(checksum)
        assert existing is not None
        return IngestionResult(
            document_id=str(existing.id),
            title=existing.title,
            source_type=existing.source_type,
            chunks_inserted=0,
            chunks_embedded=0,
            skipped_existing=True,
            duration_seconds=time.monotonic() - start,
        )

    inserted = await insert_chunks(doc_id, embedded_chunks)
    duration = time.monotonic() - start

    return IngestionResult(
        document_id=str(doc_id),
        title=metadata.title,
        source_type=metadata.source_type,
        chunks_inserted=inserted,
        chunks_embedded=inserted,
        duration_seconds=duration,
    )
