from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Document(Base):
    """A source document in the knowledge base."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="One of: nasa_payload_guide, casis_solicitation, iss_annual_report, paper, hardware_spec, regulatory",
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    organization: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Local or S3 path to the original file",
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hex digest of the raw file",
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    doc_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_documents_source_type", "source_type"),
        Index("idx_documents_metadata", "doc_metadata", postgresql_using="gin"),
        UniqueConstraint("checksum", name="uq_documents_checksum"),
    )


class Chunk(Base):
    """A chunk of a document with its embedding."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="text",
        comment="One of: text, table, figure_caption",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),  # voyage-3-large is 1024-dim
        nullable=True,
        comment="Null until embedded; populated by ingestion pipeline",
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    # Generated full-text search column for hybrid retrieval
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
    )

    document: Mapped[Document] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),
        Index("idx_chunks_document", "document_id"),
        Index(
            "idx_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_chunks_tsv", "content_tsv", postgresql_using="gin"),
        Index("idx_chunks_metadata", "chunk_metadata", postgresql_using="gin"),
    )


class EvalExample(Base):
    """A golden-set example used to evaluate retrieval quality."""

    __tablename__ = "eval_examples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_intent: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="One of: hardware_lookup, safety_precedent, protocol_adaptation, mission_integration, regulatory_pathway",
    )
    expected_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    expected_documents: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}",
    )
    expected_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
        comment="Fallback for examples without chunk-level ground truth",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class EvalRun(Base):
    """A single execution of the eval suite, for tracking quality over time."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    per_example_results: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
