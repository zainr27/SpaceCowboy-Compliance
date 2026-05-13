from __future__ import annotations

import asyncio

import pytest

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.orchestrator.executor import (
    CascadedExecutor,
    ExecutionResults,
    ParallelExecutor,
)
from packages.orchestrator.orchestrator import Orchestrator
from packages.orchestrator.schemas import OrchestratorReport
from packages.orchestrator.synthesizer import (
    LLMMediatedSynthesizer,
    RuleBasedSynthesizer,
)


def test_parallel_executor_name() -> None:
    assert ParallelExecutor().name == "parallel"


def test_cascaded_executor_not_implemented() -> None:
    """CascadedExecutor is a placeholder; calling it raises NotImplementedError."""
    protocol = ProtocolRequirements(
        description="A test protocol for ensuring the executor stub raises properly when invoked."
    )
    executor = CascadedExecutor()
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop().run_until_complete(executor.execute(protocol))


def test_rule_based_synthesizer_name() -> None:
    assert RuleBasedSynthesizer().name == "rule_based"


def test_llm_mediated_synthesizer_not_implemented() -> None:
    """LLMMediatedSynthesizer is a placeholder."""
    protocol = ProtocolRequirements(
        description="A test protocol for ensuring the synthesizer stub raises properly when invoked."
    )
    synth = LLMMediatedSynthesizer()
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop().run_until_complete(
            synth.synthesize(
                protocol=protocol,
                results=ExecutionResults(),
                total_duration_ms=0,
                executor_name="parallel",
            )
        )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_orchestrator_end_to_end_plant_growth() -> None:
    """Full pipeline on plant_growth preset.

    The strongest corpus coverage is plant biology, so this preset should
    produce a complete report with at least 4 of 5 agents succeeding.
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
        co2_pct=0.04,
        light_required=True,
        requires_imaging=True,
        requires_sample_return=True,
        biosafety_level="BSL-1",
    )

    orch = Orchestrator()
    report = await orch.analyze(protocol)

    assert isinstance(report, OrchestratorReport)
    assert report.executor == "parallel"
    assert report.synthesizer == "rule_based"

    succeeded = sum(1 for e in report.agent_executions if e.succeeded)
    assert succeeded >= 4, f"Expected >=4 agents to succeed, got {succeeded}"

    assert len(report.executive_summary.headline) >= 30
    assert report.executive_summary.biosafety_classification != "unknown"

    chunk_ids = [c.chunk_id for c in report.citations]
    assert len(chunk_ids) == len(set(chunk_ids)), "Citations should be deduplicated"

    assert (
        report.confidence.overall >= 0.4
    ), f"Expected overall confidence >= 0.4 on plant_growth, got {report.confidence.overall}"
