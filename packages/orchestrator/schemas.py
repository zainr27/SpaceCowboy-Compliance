from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from packages.agents.hardware.schemas import HardwareAgentOutput, ProtocolRequirements
from packages.agents.microgravity.schemas import MicrogravityAgentOutput
from packages.agents.mission.schemas import MissionAgentOutput
from packages.agents.regulatory.schemas import RegulatoryAgentOutput
from packages.agents.safety.schemas import SafetyAgentOutput

AgentName = Literal["hardware", "microgravity", "safety", "mission", "regulatory"]


class ScopeVerdict(BaseModel):
    """Pre-flight judgment of whether a request is in this tool's domain.

    This tool analyzes *biological/biochemical/physiological* experimental
    protocols destined for spaceflight. A request that is clearly something
    else (compute infrastructure, pure software, finance, etc.) is out of
    scope and should be refused before the expensive five-agent run.
    """

    in_scope: bool = Field(
        ...,
        description="True if this is a biological experimental protocol for spaceflight.",
    )
    category: str = Field(
        ...,
        description="Short label for what the request actually is, e.g. "
        "'biological_protocol', 'compute_infrastructure', 'software', 'other'.",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=400,
        description="One-sentence explanation of the judgment, for the user.",
    )


class AgentExecution(BaseModel):
    """Captures the result of a single sub-agent run."""

    agent: AgentName
    succeeded: bool
    duration_ms: int
    chunks_used: int = 0
    error: str | None = Field(
        None,
        description="Error message if agent failed. None if succeeded.",
    )


class UnifiedCitation(BaseModel):
    """A citation that may be referenced by multiple sub-agents.

    Indices are reassigned in the unified report; each sub-agent's
    original indices get remapped during synthesis.
    """

    unified_index: int = Field(..., description="1-based index in the final report")
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float = Field(
        ..., description="Best relevance score across all agents that cited this chunk"
    )
    cited_by: list[AgentName] = Field(
        default_factory=list,
        description="Which sub-agents cited this chunk",
    )


class CrossAgentInsight(BaseModel):
    """An insight that emerges from comparing outputs across sub-agents."""

    kind: Literal[
        "consistency_check",
        "tension",
        "compound_risk",
        "corpus_gap",
    ]
    description: str = Field(..., min_length=30, max_length=800)
    involved_agents: list[AgentName]


class ConfidenceProfile(BaseModel):
    """Per-agent confidence breakdown."""

    hardware: float | None = None
    microgravity: float | None = None
    safety: float | None = None
    mission: float | None = None
    regulatory: float | None = None
    overall: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate confidence across all successful agents",
    )


class ExecutiveSummary(BaseModel):
    """A short, prose summary for human readers."""

    headline: str = Field(
        ...,
        description="One-sentence top-line conclusion",
        min_length=30,
        max_length=300,
    )
    facility_recommendation: str | None = Field(
        None,
        description="Top facility recommendation in one sentence, or None if none identified",
    )
    primary_microgravity_concern: str | None = Field(
        None,
        description="The most significant microgravity adaptation, in one sentence",
    )
    biosafety_classification: str = Field(
        ...,
        description="The classified biosafety level (BSL-1/2/3/4 or non-biological)",
    )
    mission_pathway: str | None = Field(
        None,
        description="Top-line mission pathway: ascent vehicle and resource requirements",
    )
    regulatory_floor: str = Field(
        ...,
        description="The minimum regulatory requirements, e.g., NASA payload safety review",
    )


class OrchestratorReport(BaseModel):
    """The complete orchestrated analysis."""

    # Provenance
    protocol: ProtocolRequirements
    total_duration_ms: int
    executor: Literal["parallel", "cascaded"] = "parallel"
    synthesizer: Literal["rule_based", "llm_mediated"] = "rule_based"
    agent_executions: list[AgentExecution]

    # Scope guard verdict. Present when the pre-flight classifier ran; when
    # in_scope is False the agents were skipped and this is an honest refusal.
    scope: ScopeVerdict | None = None

    # Top-level synthesis
    executive_summary: ExecutiveSummary
    confidence: ConfidenceProfile

    # Full sub-agent outputs (preserved for drill-down)
    hardware: HardwareAgentOutput | None = None
    microgravity: MicrogravityAgentOutput | None = None
    safety: SafetyAgentOutput | None = None
    mission: MissionAgentOutput | None = None
    regulatory: RegulatoryAgentOutput | None = None

    # Cross-agent reasoning
    cross_agent_insights: list[CrossAgentInsight] = Field(default_factory=list)

    # Unified citation table
    citations: list[UnifiedCitation] = Field(default_factory=list)

    # Aggregate gaps
    open_questions: list[str] = Field(
        default_factory=list,
        description="Open questions aggregated from all sub-agents, deduplicated",
    )
