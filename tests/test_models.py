import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.config import get_settings
from packages.kb.storage.models import Chunk, Document


async def make_session() -> AsyncSession:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    return factory(), engine


@pytest.mark.asyncio
@pytest.mark.integration
async def test_insert_and_query_document() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        doc = Document(
            source_url="https://example.com/test.pdf",
            source_type="paper",
            title="Test Document",
            raw_path="/tmp/test.pdf",
            checksum=uuid.uuid4().hex,
        )
        session.add(doc)
        await session.flush()
        doc_id = doc.id

        result = await session.execute(select(Document).where(Document.id == doc_id))
        fetched = result.scalar_one()
        assert fetched.title == "Test Document"
        assert fetched.source_type == "paper"

        await session.delete(fetched)
        await session.commit()

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_insert_chunk_with_embedding() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with factory() as session:
        doc = Document(
            source_url="https://example.com/test2.pdf",
            source_type="paper",
            title="Test Doc 2",
            raw_path="/tmp/test2.pdf",
            checksum=uuid.uuid4().hex,
        )
        session.add(doc)
        await session.flush()

        fake_embedding = [0.1] * 1024  # Right dimensionality
        chunk = Chunk(
            document_id=doc.id,
            chunk_index=0,
            content="The microgravity environment of the ISS allows for unique protein crystallization conditions.",
            content_hash=uuid.uuid4().hex,
            page_number=1,
            section_path="Introduction",
            chunk_type="text",
            embedding=fake_embedding,
            token_count=20,
        )
        session.add(chunk)
        await session.flush()
        chunk_id = chunk.id

        result = await session.execute(select(Chunk).where(Chunk.id == chunk_id))
        fetched = result.scalar_one()
        assert "microgravity" in fetched.content
        assert len(fetched.embedding) == 1024

        await session.delete(doc)  # Cascade deletes the chunk too
        await session.commit()

    await engine.dispose()
