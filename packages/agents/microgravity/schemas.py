from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

ModificationAspect = Literal[
    "fluid_handling",
    "gas_exchange",
    "thermal_management",
    "sedimentation",
    "cell_behavior",
    "growth_morphology",
    "mixing_diffusion",
    "containment",
    "sample_stability",
    "imaging_geometry",
    "other",
]


class ProtocolModification(BaseModel):
    """A specific change the protocol needs because of microgravity."""

    aspect: ModificationAspect = Field(
        ...,
        description="The category of microgravity effect this modification addresses",
    )
    earthbound_assumption: str = Field(
        ...,
        description="What the protocol assumes that's true in 1g but false in microgravity",
        min_length=20,
        max_length=500,
    )
    microgravity_reality: str = Field(
        ...,
        description="What actually happens in microgravity for this aspect",
        min_length=20,
        max_length=500,
    )
    recommended_change: str = Field(
        ...,
        description="The specific protocol modification to address this",
        min_length=20,
        max_length=800,
    )
    severity: Literal["critical", "important", "minor"] = Field(
        ...,
        description=(
            "critical: experiment will fail without this change. "
            "important: results will be substantially affected. "
            "minor: results may have small artifacts but experiment can proceed."
        ),
    )
    citation_indices: list[int] = Field(
        default_factory=list,
        description="Citations [N] supporting this modification's necessity",
    )


class ExpectedBehavior(BaseModel):
    """A prediction about how the experiment will behave differently in microgravity."""

    phenomenon: str = Field(
        ...,
        description="The phenomenon or behavior being predicted",
        min_length=10,
        max_length=200,
    )
    explanation: str = Field(
        ...,
        description="Why this happens, grounded in retrieved sources",
        min_length=30,
        max_length=800,
    )
    impact_on_experiment: str = Field(
        ...,
        description="How this affects the experiment's outcomes or interpretation",
        min_length=30,
        max_length=500,
    )
    citation_indices: list[int] = Field(default_factory=list)


class ResearchPrecedent(BaseModel):
    """A prior experiment or study with relevant findings."""

    description: str = Field(
        ...,
        description="Brief description of the prior experiment",
        min_length=20,
        max_length=500,
    )
    relevance: str = Field(
        ...,
        description="Why this precedent is relevant to the current protocol",
        min_length=20,
        max_length=400,
    )
    finding: str = Field(
        ...,
        description="The key finding or outcome",
        min_length=20,
        max_length=400,
    )
    citation_indices: list[int] = Field(default_factory=list)


class MicrogravityAnalysis(BaseModel):
    """The agent's structured output."""

    summary: str = Field(
        ...,
        description="2-3 sentence overview of how microgravity affects this protocol",
        min_length=50,
        max_length=1000,
    )
    modifications: list[ProtocolModification] = Field(
        default_factory=list,
        description="Specific protocol changes needed",
    )
    expected_behaviors: list[ExpectedBehavior] = Field(
        default_factory=list,
        description="Behaviors that will differ from 1g",
    )
    research_precedents: list[ResearchPrecedent] = Field(
        default_factory=list,
        description="Prior experiments with relevant findings",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0-1 confidence the corpus had enough info to give useful analysis",
    )


class ResolvedCitation(BaseModel):
    """A citation expanded with full source info. Same shape as hardware agent."""

    index: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float


class MicrogravityAgentOutput(BaseModel):
    """Full agent response."""

    analysis: MicrogravityAnalysis
    citations: list[ResolvedCitation]
    retrieval_chunks_used: int
    retrieval_ms: int
    reasoning_ms: int
