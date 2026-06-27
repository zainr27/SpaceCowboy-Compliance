from __future__ import annotations

import structlog

from packages.agents.base import call_llm_structured
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.orchestrator.schemas import (
    ConfidenceProfile,
    ExecutiveSummary,
    OrchestratorReport,
    ScopeVerdict,
)

logger = structlog.get_logger(__name__)

# Cheap, fast model — this is a one-shot binary judgment, not deep reasoning.
SCOPE_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are a scope gate for a tool that analyzes BIOLOGICAL experimental protocols destined for spaceflight (the ISS and similar platforms). The tool reasons about biosafety classification, microgravity adaptation of living systems, biology research hardware, mission logistics, and regulatory pathways for life-science payloads.

Decide whether the user's request is such a protocol.

IN SCOPE — biological / biochemical / physiological experiments, e.g.:
- plant, microbial, mammalian, or cell-culture experiments
- protein crystallization, tissue engineering, organoids, bioprinting
- pharmacology, microbiology, genetics, physiology studies
- anything involving living organisms, biological samples, or biochemistry

OUT OF SCOPE — requests that are not a life-science experiment, e.g.:
- compute / data-center / AI / GPU / server infrastructure
- pure software, networking, or electronics projects
- propulsion, structures, materials (non-biological), finance, logistics-only

Be CONSERVATIVE about refusing: if the request is biology-adjacent or ambiguous, mark it in_scope=true and let the full analysis run. Only mark in_scope=false when the request is clearly NOT a biological experiment.

Set `category` to a short snake_case label for what the request actually is. Set `reason` to one plain sentence a user would understand."""


async def classify_scope(protocol: ProtocolRequirements) -> ScopeVerdict:
    """Pre-flight check: is this request a biological protocol we can analyze?

    Fails OPEN — if the classifier call errors, we assume in_scope so a
    transient LLM failure never blocks a legitimate user.
    """
    user_prompt = (
        f"Request to classify:\n\n{protocol.description[:1500]}\n\n"
        f"Stated intent: {protocol.intent}\n"
        f"Organism (if any): {protocol.organism or 'unspecified'}\n\n"
        "Is this a biological experimental protocol for spaceflight?"
    )

    try:
        verdict, _ = await call_llm_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=ScopeVerdict,
            model=SCOPE_MODEL,
            max_tokens=256,
            temperature=0.0,
        )
        logger.info(
            "scope_classified",
            in_scope=verdict.in_scope,
            category=verdict.category,
        )
        return verdict
    except Exception:
        logger.exception("scope_classification_failed_fail_open")
        return ScopeVerdict(
            in_scope=True,
            category="unknown",
            reason="Scope check unavailable; proceeding with full analysis.",
        )


def build_out_of_scope_report(
    protocol: ProtocolRequirements,
    verdict: ScopeVerdict,
    total_duration_ms: int,
    executor_name: str = "parallel",
) -> OrchestratorReport:
    """An honest refusal report: no agents ran, scope verdict explains why."""
    return OrchestratorReport(
        protocol=protocol,
        total_duration_ms=total_duration_ms,
        executor=executor_name,  # type: ignore[arg-type]
        agent_executions=[],
        scope=verdict,
        executive_summary=ExecutiveSummary(
            headline=(
                "This request is outside the tool's scope: it analyzes biological "
                "experimental protocols for spaceflight."
            ),
            facility_recommendation=None,
            primary_microgravity_concern=None,
            biosafety_classification="not_applicable",
            mission_pathway=None,
            regulatory_floor="Not applicable — request is not a biological spaceflight protocol.",
        ),
        confidence=ConfidenceProfile(overall=0.0),
    )
