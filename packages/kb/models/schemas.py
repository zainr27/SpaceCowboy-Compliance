from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    """Metadata supplied at ingestion time. Becomes a Document row."""

    source_url: str
    source_type: str = Field(
        ...,
        description="One of: nasa_payload_guide, casis_solicitation, iss_annual_report, paper, hardware_spec, regulatory",
    )
    title: str
    publication_date: date | None = None
    organization: str | None = None
    extra: dict = Field(default_factory=dict)


class RawChunk(BaseModel):
    """A chunk produced by the chunker, before embedding."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    chunk_index: int
    content: str
    page_number: int | None = None
    section_path: str | None = None
    chunk_type: str = "text"  # text | table | figure_caption
    token_count: int | None = None


class EmbeddedChunk(RawChunk):
    """A chunk with its embedding vector attached."""

    embedding: list[float]


class IngestionResult(BaseModel):
    """Summary of an ingestion run, returned to the caller."""

    document_id: str
    title: str
    source_type: str
    chunks_inserted: int
    chunks_embedded: int
    skipped_existing: bool = False
    duration_seconds: float
