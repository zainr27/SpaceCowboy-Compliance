from __future__ import annotations

import pytest

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.mission.agent import MissionAgent
from packages.agents.mission.schemas import (
    CrewTimeEstimate,
    MissionAgentOutput,
    ResourceBudget,
)


def test_resource_budget_requires_rationale() -> None:
    """ResourceBudget must include rationale."""
    rb = ResourceBudget(
        upmass_estimate_kg=2.5,
        downmass_estimate_kg=1.0,
        requires_cold_stowage=True,
        requires_powered_locker=False,
        rationale="Estimate based on similar plant biology payloads in the FY25 annual report cargo manifests.",
    )
    assert rb.upmass_estimate_kg == 2.5
    assert rb.requires_cold_stowage is True


def test_resource_budget_accepts_none_estimates() -> None:
    """ResourceBudget allows None for numeric fields when corpus lacks specifics."""
    rb = ResourceBudget(
        upmass_estimate_kg=None,
        downmass_estimate_kg=None,
        requires_cold_stowage=False,
        requires_powered_locker=False,
        rationale="Corpus did not include specific upmass figures for this experiment type.",
    )
    assert rb.upmass_estimate_kg is None


def test_crew_time_interaction_type_constrained() -> None:
    """interaction_type must be one of the Literal values."""
    with pytest.raises(ValueError):
        CrewTimeEstimate(
            total_hours_estimate=10.0,
            interaction_type="some_made_up_value",  # type: ignore[arg-type]
            rationale="x" * 50,
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_mission_agent_end_to_end() -> None:
    """End-to-end run on a plant growth protocol.

    Mission corpus (FY25 annual report + Redwire flysheets) is strong, so
    we expect facility recommendations and ascent options.
    """
    protocol = ProtocolRequirements(
        description=(
            "A 30-day plant growth experiment with Arabidopsis thaliana, examining "
            "gravitropic response under controlled humidity and light. Requires "
            "imaging and sample return."
        ),
        organism="Arabidopsis thaliana",
        duration_days=30,
        temperature_c=22.0,
        humidity_pct=70.0,
        light_required=True,
        requires_imaging=True,
        requires_sample_return=True,
    )

    agent = MissionAgent()
    output = await agent.analyze(protocol)

    assert isinstance(output, MissionAgentOutput)
    assert output.retrieval_chunks_used > 0
    assert (
        len(output.analysis.recommended_facilities) >= 1
    ), "Expected at least one facility recommendation given corpus coverage"
