from __future__ import annotations

import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _insert_document(
    session: AsyncSession,
    metadata: DocumentMetadata,
    raw_path: Path,
    checksum: str,
) -> uuid.UUID:
    """Insert a document row within the given session, return its ID.

    Flushes (not commits) so the row gets an ID and any checksum
    UniqueConstraint violation surfaces as IntegrityError, while leaving
    the enclosing transaction open for the caller to commit atomically.
    """
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


async def _insert_chunks(
    session: AsyncSession,
    document_id: uuid.UUID,
    chunks: list[EmbeddedChunk],
) -> int:
    """Bulk insert chunks for a document within the given session.

    Flushes (not commits) so a failure propagates and the enclosing
    transaction can roll back the document insert too.
    """
    if not chunks:
        return 0

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

    Both the document row and all of its chunks are inserted inside a
    single transaction (one ``get_session()``), which commits only after
    both succeed. If chunk insertion fails, the document insert is rolled
    back as well, so no orphan document (zero chunks) can ever be left
    behind to poison the checksum dedup path.

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
        # Single transaction: get_session() commits on clean exit and rolls
        # back on any exception, so the document + chunk inserts are atomic.
        async with get_session() as session:
            doc_id = await _insert_document(session, metadata, raw_path, checksum)
            inserted = await _insert_chunks(session, doc_id, embedded_chunks)
    except IntegrityError:
        # Race condition: another process inserted between our check and insert.
        # The failed transaction has already rolled back (get_session handles it).
        existing = await get_document_by_checksum(checksum)
        if existing is None:
            # IntegrityError that wasn't the checksum race — don't swallow it.
            raise
        return IngestionResult(
            document_id=str(existing.id),
            title=existing.title,
            source_type=existing.source_type,
            chunks_inserted=0,
            chunks_embedded=0,
            skipped_existing=True,
            duration_seconds=time.monotonic() - start,
        )

    duration = time.monotonic() - start

    return IngestionResult(
        document_id=str(doc_id),
        title=metadata.title,
        source_type=metadata.source_type,
        chunks_inserted=inserted,
        chunks_embedded=inserted,
        duration_seconds=duration,
    )
