from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A single chunk returned by the retrieval service."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    source_url: str
    source_type: str
    title: str
    page_number: int | None = None
    section_path: str | None = None
    chunk_type: str
    # Scoring breakdown for debugging and analysis
    dense_score: float | None = None
    sparse_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


class RetrievalRequest(BaseModel):
    """Input to the retrieval service."""

    query: str = Field(..., min_length=1, max_length=2000)
    source_types: list[str] | None = Field(
        default=None,
        description="Filter to specific source types (e.g. ['hardware_spec', 'safety']). None = all.",
    )
    organization: str | None = None
    k: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Initial retrieval depth before reranking",
    )
    rerank_top_n: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Final result count after reranking",
    )
    use_reranker: bool = True
    dense_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight of dense score in hybrid fusion. Sparse weight = 1 - dense_weight.",
    )


class RetrievalResponse(BaseModel):
    """Output from the retrieval service."""

    chunks: list[RetrievedChunk]
    query: str
    total_candidates: int  # How many came back from hybrid search before reranking
    retrieval_ms: int
    rerank_ms: int | None = None
