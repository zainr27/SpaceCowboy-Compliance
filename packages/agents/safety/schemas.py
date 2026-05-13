from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

HazardCategory = Literal[
    "biological",
    "chemical",
    "physical",
    "energy",
    "radiation",
    "fluid_pressure",
    "thermal",
    "other",
]

HazardLikelihood = Literal["high", "medium", "low"]
HazardSeverity = Literal["catastrophic", "critical", "marginal", "negligible"]
BiosafetyLevel = Literal["BSL-1", "BSL-2", "BSL-3", "BSL-4", "non-biological"]


class SafetyHazard(BaseModel):
    """A specific safety hazard the protocol introduces."""

    category: HazardCategory = Field(..., description="The type of hazard")
    description: str = Field(
        ...,
        description="What the hazard is, in 1-2 sentences",
        min_length=20,
        max_length=500,
    )
    likelihood: HazardLikelihood = Field(
        ...,
        description="Probability the hazard manifests during the experiment",
    )
    severity: HazardSeverity = Field(
        ...,
        description=(
            "Worst-case consequence if the hazard occurs. "
            "catastrophic: loss of life or station. "
            "critical: major injury or station damage. "
            "marginal: minor injury or recoverable damage. "
            "negligible: minor inconvenience."
        ),
    )
    mitigation: str = Field(
        ...,
        description="How the hazard is addressed (containment, procedure, hardware feature)",
        min_length=20,
        max_length=800,
    )
    citation_indices: list[int] = Field(default_factory=list)


class ReviewMilestone(BaseModel):
    """A safety review milestone the experiment must clear."""

    phase: str = Field(
        ...,
        description=(
            "The phase name, e.g., 'Payload Safety Introduction (PSI)', "
            "'Phase I Safety Data Package', 'PDR Safety Review', "
            "'Phase III Approval', 'Certificate of Compliance'"
        ),
        min_length=5,
        max_length=200,
    )
    required_documentation: str = Field(
        ...,
        description="What documentation must be submitted at this phase",
        min_length=20,
        max_length=600,
    )
    typical_timing: str | None = Field(
        None,
        description="When in project lifecycle this occurs, if known (e.g., 'L-18 months', 'pre-CDR')",
    )
    citation_indices: list[int] = Field(default_factory=list)


class ContainmentRequirement(BaseModel):
    """A specific containment or operational requirement."""

    requirement: str = Field(
        ...,
        description="The specific requirement",
        min_length=20,
        max_length=500,
    )
    rationale: str = Field(
        ...,
        description="Why this is required (which hazard it addresses)",
        min_length=20,
        max_length=500,
    )
    citation_indices: list[int] = Field(default_factory=list)


class SafetyAnalysis(BaseModel):
    """The agent's structured output."""

    summary: str = Field(
        ...,
        description="2-3 sentence overall safety posture for this protocol",
        min_length=50,
        max_length=1000,
    )
    biosafety_classification: BiosafetyLevel = Field(
        ...,
        description="The biosafety level classification, or 'non-biological' if not applicable",
    )
    hazards: list[SafetyHazard] = Field(
        default_factory=list,
        description="Identified safety hazards",
    )
    containment_requirements: list[ContainmentRequirement] = Field(
        default_factory=list,
        description="Specific containment and operational requirements",
    )
    review_milestones: list[ReviewMilestone] = Field(
        default_factory=list,
        description="NASA payload safety review phases the experiment must clear",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Safety questions the corpus could not answer",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence the corpus had enough info to give useful analysis",
    )


class ResolvedCitation(BaseModel):
    """Same shape as other agents'."""

    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float


class SafetyAgentOutput(BaseModel):
    analysis: SafetyAnalysis
    citations: list[ResolvedCitation]
    retrieval_chunks_used: int
    retrieval_ms: int
    reasoning_ms: int
