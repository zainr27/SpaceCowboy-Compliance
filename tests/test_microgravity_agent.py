from __future__ import annotations

import pytest

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.microgravity.agent import MicrogravityAgent
from packages.agents.microgravity.schemas import (
    MicrogravityAgentOutput,
    MicrogravityAnalysis,
    ProtocolModification,
)


def test_modification_requires_three_part_reasoning() -> None:
    """A modification must articulate earth assumption, mg reality, and change."""
    mod = ProtocolModification(
        aspect="fluid_handling",
        earthbound_assumption="On Earth, gravity drives liquid drainage in porous root media.",
        microgravity_reality="In microgravity, capillary forces dominate and water distributes more uniformly.",
        recommended_change="Use larger particle substrate (1-2mm arcillite) and reduce moisture setpoints by 20-30% relative to 1g controls.",
        severity="important",
    )
    assert mod.aspect == "fluid_handling"
    assert mod.severity == "important"


def test_modification_validates_min_lengths() -> None:
    """Each text field has a minimum length."""
    with pytest.raises(ValueError):
        ProtocolModification(
            aspect="fluid_handling",
            earthbound_assumption="too short",
            microgravity_reality="x" * 30,
            recommended_change="x" * 30,
            severity="minor",
        )


def test_analysis_confidence_in_range() -> None:
    """overall_confidence must be in [0, 1]."""
    with pytest.raises(ValueError):
        MicrogravityAnalysis(
            summary="x" * 100,
            modifications=[],
            expected_behaviors=[],
            research_precedents=[],
            overall_confidence=1.5,
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_microgravity_agent_plant_growth_end_to_end() -> None:
    """End-to-end run on a plant growth protocol. Plant content is strong in corpus."""
    protocol = ProtocolRequirements(
        description=(
            "A 30-day plant growth experiment with Arabidopsis thaliana, examining "
            "gravitropic response and seed-to-seed development under controlled "
            "humidity and light. Requires automated watering and CO2 regulation."
        ),
        organism="Arabidopsis thaliana",
        duration_days=30,
        temperature_c=22.0,
        humidity_pct=70.0,
        co2_pct=0.04,
        light_required=True,
        requires_imaging=True,
    )

    agent = MicrogravityAgent()
    output = await agent.analyze(protocol)

    assert isinstance(output, MicrogravityAgentOutput)
    assert output.retrieval_chunks_used > 0
    assert 0.0 <= output.analysis.overall_confidence <= 1.0
    assert output.analysis.overall_confidence >= 0.4, (
        f"Expected confidence >= 0.4 on plant_growth given corpus coverage, "
        f"got {output.analysis.overall_confidence}"
    )
