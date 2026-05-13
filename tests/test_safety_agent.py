from __future__ import annotations

import pytest

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.safety.agent import SafetyAgent
from packages.agents.safety.schemas import (
    SafetyAgentOutput,
    SafetyAnalysis,
    SafetyHazard,
)


def test_hazard_validates_required_fields() -> None:
    """All key fields required and length-bounded."""
    hazard = SafetyHazard(
        category="biological",
        description="CHO cells in culture media pose minor biological hazard if released into ISS atmosphere.",
        likelihood="low",
        severity="marginal",
        mitigation="Double containment via cassette housing and outer experiment module.",
    )
    assert hazard.category == "biological"


def test_hazard_rejects_short_description() -> None:
    with pytest.raises(ValueError):
        SafetyHazard(
            category="biological",
            description="too short",
            likelihood="low",
            severity="marginal",
            mitigation="x" * 30,
        )


def test_analysis_confidence_in_range() -> None:
    with pytest.raises(ValueError):
        SafetyAnalysis(
            summary="x" * 100,
            biosafety_classification="BSL-1",
            hazards=[],
            containment_requirements=[],
            review_milestones=[],
            open_questions=[],
            overall_confidence=1.5,
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_safety_agent_protein_crystal_classification() -> None:
    """Protein crystallization should classify as non-biological.

    Lysozyme is a protein, not an organism. A weakly-grounded agent will
    default to BSL-1 anyway; this test enforces correct classification.
    """
    protocol = ProtocolRequirements(
        description=(
            "Protein crystallization experiment using lysozyme as a model protein. "
            "Vapor diffusion method requiring 10 days of stable temperature at 20C. "
            "100 samples in parallel. Crystals must be returned to Earth for "
            "X-ray diffraction analysis."
        ),
        organism="lysozyme (protein, no live organism)",
        duration_days=10,
        temperature_c=20.0,
        requires_sample_return=True,
        intent="commercial",
    )

    agent = SafetyAgent()
    output = await agent.analyze(protocol)

    assert isinstance(output, SafetyAgentOutput)
    assert output.retrieval_chunks_used > 0
    assert output.analysis.biosafety_classification == "non-biological", (
        f"Expected non-biological classification for lysozyme protein "
        f"crystallization, got {output.analysis.biosafety_classification}"
    )
