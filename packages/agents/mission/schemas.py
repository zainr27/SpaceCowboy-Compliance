from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

AscentVehicle = Literal[
    "SpaceX_Crew_Dragon",
    "SpaceX_Cargo_Dragon",
    "Northrop_Grumman_Cygnus",
    "Axiom_private_mission",
    "other",
    "unspecified",
]

InteractionType = Literal[
    "fully_automated",
    "minimal_crew",
    "hands_on_crew",
    "complex_crew_ops",
    "unspecified",
]


class FacilityMatch(BaseModel):
    """A specific on-station facility recommendation."""

    facility_name: str = Field(
        ...,
        description="The facility name, e.g., 'Redwire ADSEP', 'BioServe SABL', 'Space Tango TangoLab'",
        min_length=3,
        max_length=150,
    )
    provider: str = Field(
        ...,
        description="The Implementation Partner / Commercial Service Provider operating this facility",
        min_length=3,
        max_length=100,
    )
    fit_rationale: str = Field(
        ...,
        description="Why this facility fits the protocol's needs",
        min_length=30,
        max_length=800,
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Operational constraints for this facility relevant to this protocol",
    )
    citation_indices: list[int] = Field(default_factory=list)


class AscentOption(BaseModel):
    """A launch vehicle option for getting the payload to ISS."""

    vehicle: AscentVehicle
    rationale: str = Field(
        ...,
        description="Why this vehicle fits, based on cargo type and resource constraints",
        min_length=30,
        max_length=500,
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Vehicle-specific constraints: launch cadence, late-load options, cold stowage availability",
    )
    citation_indices: list[int] = Field(default_factory=list)


class ResourceBudget(BaseModel):
    """Mass, volume, and stowage requirements for the experiment."""

    upmass_estimate_kg: float | None = Field(
        None,
        description="Estimated upmass in kilograms, if determinable from sources",
        ge=0.0,
    )
    downmass_estimate_kg: float | None = Field(
        None,
        description="Estimated downmass for sample return",
        ge=0.0,
    )
    requires_cold_stowage: bool = Field(
        ...,
        description="Whether the experiment requires powered cold stowage during transit",
    )
    requires_powered_locker: bool = Field(
        ...,
        description="Whether the experiment requires powered ascent (rather than passive)",
    )
    rationale: str = Field(
        ...,
        description="How the budget was estimated and what's driving the resource needs",
        min_length=30,
        max_length=800,
    )
    citation_indices: list[int] = Field(default_factory=list)


class CrewTimeEstimate(BaseModel):
    """Estimated crew involvement for the experiment."""

    total_hours_estimate: float | None = Field(
        None,
        description="Total crew time hours over the experiment lifecycle, if estimable",
        ge=0.0,
    )
    interaction_type: InteractionType = Field(
        ...,
        description="How much crew interaction the protocol requires",
    )
    rationale: str = Field(
        ...,
        description="What drives the crew time estimate",
        min_length=30,
        max_length=800,
    )
    citation_indices: list[int] = Field(default_factory=list)


class TimelineMilestone(BaseModel):
    """A project milestone on the path from proposal to flight."""

    name: str = Field(
        ...,
        description="Milestone name, e.g., 'Proposal submission', 'PDR', 'Late load handover'",
        min_length=3,
        max_length=200,
    )
    typical_timing: str | None = Field(
        None,
        description="When this occurs relative to launch (e.g., 'L-17 months', 'L-30 days')",
    )
    deliverables: str = Field(
        ...,
        description="What must be delivered or completed at this milestone",
        min_length=20,
        max_length=500,
    )
    citation_indices: list[int] = Field(default_factory=list)


class MissionAnalysis(BaseModel):
    """The agent's structured output."""

    summary: str = Field(
        ...,
        description="2-3 sentence overview of the mission integration path",
        min_length=50,
        max_length=1000,
    )
    recommended_facilities: list[FacilityMatch] = Field(
        default_factory=list,
        description="On-station facilities that fit this protocol, ranked by fit",
    )
    ascent_options: list[AscentOption] = Field(
        default_factory=list,
        description="Viable launch vehicles for this payload",
    )
    resource_budget: ResourceBudget = Field(
        ...,
        description="Mass, volume, and stowage requirements",
    )
    crew_time: CrewTimeEstimate = Field(
        ...,
        description="Expected crew involvement",
    )
    timeline: list[TimelineMilestone] = Field(
        default_factory=list,
        description="Project milestones from proposal to flight",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Logistics questions the corpus could not answer",
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


class MissionAgentOutput(BaseModel):
    analysis: MissionAnalysis
    citations: list[ResolvedCitation]
    retrieval_chunks_used: int
    retrieval_ms: int
    reasoning_ms: int
