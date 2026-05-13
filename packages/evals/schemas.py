from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class QueryIntent(StrEnum):
    """The category of question being asked. Used for per-category scoring."""

    HARDWARE_LOOKUP = "hardware_lookup"
    SAFETY_PRECEDENT = "safety_precedent"
    PROTOCOL_ADAPTATION = "protocol_adaptation"
    MISSION_INTEGRATION = "mission_integration"
    REGULATORY_PATHWAY = "regulatory_pathway"
    GENERAL = "general"


class GoldenExample(BaseModel):
    """A single eval example with ground truth.

    Examples come in two flavors:
    - keyword-based: easier to author, scored by content match
    - chunk-based: precise, scored by retrieved chunk IDs
    Most examples start as keyword-based and graduate to chunk-based
    once you have a real corpus to point at.
    """

    id: str = Field(..., description="Stable identifier, e.g. 'hw_cell_culture_01'")
    query: str
    intent: QueryIntent = QueryIntent.GENERAL
    expected_keywords: list[str] = Field(
        default_factory=list,
        description="Words/phrases that should appear in retrieved chunks. Case-insensitive.",
    )
    expected_chunk_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Specific chunks that should be in top-k. Optional.",
    )
    expected_source_types: list[str] = Field(
        default_factory=list,
        description="Source types that should appear in retrieved chunks. Optional.",
    )
    forbidden_keywords: list[str] = Field(
        default_factory=list,
        description="Words that should NOT appear in top result (negative tests).",
    )
    notes: str | None = None


class ExampleResult(BaseModel):
    """Result of running one example through retrieval."""

    example_id: str
    query: str
    intent: QueryIntent
    retrieved_chunk_ids: list[uuid.UUID]
    top_chunk_id: uuid.UUID | None
    top_score: float | None

    keyword_coverage: float | None = None
    chunk_recall_at_5: float | None = None
    chunk_recall_at_10: float | None = None
    mrr: float | None = None
    source_type_match: float | None = None
    forbidden_keyword_violation: bool = False

    retrieval_ms: int
    rerank_ms: int | None


class EvalRunSummary(BaseModel):
    """Aggregate results of a full eval run."""

    run_id: uuid.UUID
    run_at: datetime
    git_sha: str | None
    config: dict
    example_count: int

    mean_keyword_coverage: float | None
    mean_recall_at_5: float | None
    mean_recall_at_10: float | None
    mean_mrr: float | None
    mean_source_type_match: float | None
    forbidden_violations: int
    failed_examples: list[str]

    by_intent: dict[str, dict[str, float]]
    per_example: list[ExampleResult]
