from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from packages.kb.ingestion.chunker import chunk_elements
from packages.kb.ingestion.loaders import compute_file_checksum
from packages.kb.models.schemas import DocumentMetadata, EmbeddedChunk
from packages.kb.storage.database import get_session
from packages.kb.storage.models import Document


def test_compute_file_checksum_stable(tmp_path: Path) -> None:
    """Same file produces same checksum."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")
    a = compute_file_checksum(f)
    b = compute_file_checksum(f)
    assert a == b
    assert len(a) == 64  # SHA-256 hex


def test_chunker_handles_empty_input() -> None:
    """Chunker on empty input returns empty list."""
    assert chunk_elements([]) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_repository_dedup() -> None:
    """Re-inserting same checksum returns existing document, no new rows."""
    from packages.kb.storage.repository import (
        ingest_document_if_new,
    )

    metadata = DocumentMetadata(
        source_url="https://example.com/test-dedup.pdf",
        source_type="paper",
        title="Dedup Test Doc",
    )
    fake_checksum = "a" * 64
    fake_chunks = [
        EmbeddedChunk(
            chunk_index=0,
            content="Test content for dedup",
            page_number=1,
            embedding=[0.1] * 1024,
        )
    ]

    # First ingestion: inserts
    r1 = await ingest_document_if_new(
        metadata=metadata,
        raw_path=Path("/tmp/fake.pdf"),
        checksum=fake_checksum,
        embedded_chunks=fake_chunks,
    )
    assert r1.chunks_inserted == 1
    assert not r1.skipped_existing

    # Second ingestion: skips
    r2 = await ingest_document_if_new(
        metadata=metadata,
        raw_path=Path("/tmp/fake.pdf"),
        checksum=fake_checksum,
        embedded_chunks=fake_chunks,
    )
    assert r2.skipped_existing
    assert r2.chunks_inserted == 0
    assert r2.document_id == r1.document_id

    # Cleanup
    async with get_session() as session:
        doc = (
            await session.execute(select(Document).where(Document.checksum == fake_checksum))
        ).scalar_one()
        await session.delete(doc)
        await session.commit()
