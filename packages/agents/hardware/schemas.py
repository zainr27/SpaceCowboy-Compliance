from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Input: A biotech experimental protocol
# ============================================================================


class ProtocolRequirements(BaseModel):
    """Structured protocol input. The agent reasons against these requirements."""

    description: str = Field(
        ...,
        description="Plain-text protocol summary, 1-3 paragraphs",
        min_length=50,
        max_length=5000,
    )

    organism: str | None = Field(
        None,
        description="e.g., 'CHO cells', 'E. coli K-12', 'Arabidopsis thaliana'",
    )
    duration_days: int | None = Field(None, ge=1, le=365)
    sample_count: int | None = None

    temperature_c: float | None = None
    humidity_pct: float | None = None
    co2_pct: float | None = None
    light_required: bool | None = None

    requires_media_exchange: bool | None = None
    requires_imaging: bool | None = None
    requires_sample_return: bool | None = None
    biosafety_level: Literal["BSL-1", "BSL-2", "BSL-3"] | None = None

    intent: Literal["research", "commercial", "clinical_pathway"] = "research"


# ============================================================================
# Output: Structured hardware compatibility analysis
# ============================================================================


class HardwareMatch(BaseModel):
    """A single ISS hardware recommendation."""

    name: str = Field(..., description="Hardware name, e.g., 'BioCulture System'")
    fit_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0-1 confidence the hardware fits this protocol",
    )
    rationale: str = Field(
        ...,
        description="2-4 sentences explaining why this hardware fits, referencing specific protocol requirements",
        min_length=50,
        max_length=1500,
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Known limitations of this hardware that affect the protocol",
    )
    citation_indices: list[int] = Field(
        default_factory=list,
        description="Indices [1], [2] etc. from the formatted context that support this recommendation",
    )


class HardwareGap(BaseModel):
    """A protocol requirement that no retrieved hardware appears to satisfy."""

    requirement: str = Field(..., description="The specific protocol requirement")
    severity: Literal["blocker", "concern", "minor"]
    notes: str = Field(..., description="Why this is a gap and what would resolve it")


class HardwareAnalysis(BaseModel):
    """The agent's structured output — what the LLM produces directly."""

    summary: str = Field(
        ...,
        description="2-3 sentence overall assessment of hardware compatibility",
        min_length=50,
        max_length=1000,
    )
    recommended_hardware: list[HardwareMatch] = Field(
        default_factory=list,
        description="Ranked list of compatible hardware, best first. May be empty if no matches.",
    )
    gaps: list[HardwareGap] = Field(
        default_factory=list,
        description="Protocol requirements with no clear hardware match",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0-1 confidence the corpus contained enough info to give a useful answer",
    )


# ============================================================================
# Full result with citations resolved back to chunks
# ============================================================================


class ResolvedCitation(BaseModel):
    """A citation expanded with full source info."""

    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float


class HardwareAgentOutput(BaseModel):
    """Full agent response: the LLM's analysis + retrieval provenance added by agent code."""

    analysis: HardwareAnalysis
    citations: list[ResolvedCitation]
    retrieval_chunks_used: int
    retrieval_ms: int
    reasoning_ms: int
