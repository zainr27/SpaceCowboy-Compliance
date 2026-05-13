from __future__ import annotations

import pytest

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.regulatory.agent import RegulatoryAgent
from packages.agents.regulatory.schemas import (
    FrameworkApplicability,
    RegulatoryAgentOutput,
    RegulatoryAnalysis,
)


def test_framework_applicability_validates_required_fields() -> None:
    fa = FrameworkApplicability(
        framework="NASA_payload_safety",
        applicability="required",
        rationale="All ISS payloads must clear NASA payload safety review process per NPR 8715.3.",
    )
    assert fa.framework == "NASA_payload_safety"


def test_framework_applicability_rejects_short_rationale() -> None:
    with pytest.raises(ValueError):
        FrameworkApplicability(
            framework="NASA_payload_safety",
            applicability="required",
            rationale="too short",
        )


def test_analysis_confidence_in_range() -> None:
    with pytest.raises(ValueError):
        RegulatoryAnalysis(
            summary="x" * 100,
            applicable_frameworks=[],
            compliance_requirements=[],
            review_processes=[],
            open_questions=[],
            overall_confidence=1.5,
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_regulatory_agent_identifies_nasa_payload_safety() -> None:
    """All ISS payloads must clear NASA payload safety review.

    Regardless of protocol intent, NASA_payload_safety should appear in
    applicable_frameworks with applicability='required'. This is the
    universal regulatory floor for ISS experiments.
    """
    protocol = ProtocolRequirements(
        description=(
            "A 21-day cell culture experiment growing CHO cells at 37C with "
            "5% CO2 supplementation. Media exchange every 48 hours. Samples "
            "returned to Earth for analysis."
        ),
        organism="CHO cells",
        duration_days=21,
        temperature_c=37.0,
        co2_pct=5.0,
        requires_media_exchange=True,
        requires_sample_return=True,
        biosafety_level="BSL-1",
        intent="research",
    )

    agent = RegulatoryAgent()
    output = await agent.analyze(protocol)

    assert isinstance(output, RegulatoryAgentOutput)
    assert output.retrieval_chunks_used > 0

    nasa_frameworks = [
        f for f in output.analysis.applicable_frameworks if f.framework == "NASA_payload_safety"
    ]
    assert (
        len(nasa_frameworks) >= 1
    ), "Expected NASA_payload_safety to be in applicable_frameworks for any ISS experiment"
    assert nasa_frameworks[0].applicability == "required", (
        f"Expected NASA_payload_safety applicability='required', got "
        f"{nasa_frameworks[0].applicability}"
    )
