from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

RegulatoryFramework = Literal[
    "NASA_payload_safety",
    "FDA_preclinical",
    "FDA_pharmacogenomics",
    "FAA_commercial_space",
    "ITAR_export_control",
    "EAR_export_control",
    "CASIS_ISS_National_Lab",
    "Commercial_Resupply_Services",
    "IP_data_governance",
    "GINA_genetic_data",
    "other",
]

ApplicabilityLevel = Literal[
    "required", "likely_applicable", "potentially_applicable", "not_applicable"
]
EffortLevel = Literal["high", "medium", "low", "minimal"]


class FrameworkApplicability(BaseModel):
    """Assessment of whether a regulatory framework applies to this protocol."""

    framework: RegulatoryFramework
    applicability: ApplicabilityLevel = Field(
        ...,
        description=(
            "How clearly this framework applies. "
            "required: framework must be navigated. "
            "likely_applicable: probably applies given protocol characteristics. "
            "potentially_applicable: depends on factors not specified in protocol. "
            "not_applicable: clearly does not apply."
        ),
    )
    rationale: str = Field(
        ...,
        description="Why this framework does or doesn't apply",
        min_length=30,
        max_length=800,
    )
    citation_indices: list[int] = Field(default_factory=list)


class ComplianceRequirement(BaseModel):
    """A specific compliance requirement the protocol must address."""

    framework: RegulatoryFramework = Field(
        ...,
        description="Which framework this requirement comes from",
    )
    requirement: str = Field(
        ...,
        description="What the requirement is",
        min_length=20,
        max_length=600,
    )
    estimated_effort: EffortLevel = Field(
        ...,
        description="Rough effort to satisfy this requirement",
    )
    rationale: str = Field(
        ...,
        description="Why this requirement applies and what addressing it involves",
        min_length=30,
        max_length=800,
    )
    citation_indices: list[int] = Field(default_factory=list)


class ReviewProcess(BaseModel):
    """A regulatory or compliance review the protocol must clear."""

    name: str = Field(
        ...,
        description="Name of the review process",
        min_length=5,
        max_length=200,
    )
    responsible_authority: str = Field(
        ...,
        description="Which agency, organization, or board conducts this review",
        min_length=3,
        max_length=200,
    )
    deliverables: str = Field(
        ...,
        description="What documentation or evidence is submitted",
        min_length=20,
        max_length=600,
    )
    typical_timeline: str | None = Field(
        None,
        description="Time required for this review, if specified in sources",
    )
    citation_indices: list[int] = Field(default_factory=list)


class RegulatoryAnalysis(BaseModel):
    """The agent's structured output."""

    summary: str = Field(
        ...,
        description="2-3 sentence overview of the regulatory landscape for this protocol",
        min_length=50,
        max_length=1000,
    )
    applicable_frameworks: list[FrameworkApplicability] = Field(
        default_factory=list,
        description="Assessment of each potentially applicable regulatory framework",
    )
    compliance_requirements: list[ComplianceRequirement] = Field(
        default_factory=list,
        description="Specific compliance requirements derived from the applicable frameworks",
    )
    review_processes: list[ReviewProcess] = Field(
        default_factory=list,
        description="Reviews the protocol must clear before flight or commercialization",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Regulatory questions the corpus cannot answer; require external counsel",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )


class ResolvedCitation(BaseModel):
    """Same shape as other agents."""

    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float


class RegulatoryAgentOutput(BaseModel):
    analysis: RegulatoryAnalysis
    citations: list[ResolvedCitation]
    retrieval_chunks_used: int
    retrieval_ms: int
    reasoning_ms: int
