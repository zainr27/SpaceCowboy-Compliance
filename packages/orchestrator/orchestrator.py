from __future__ import annotations

import time

import structlog

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.orchestrator.executor import ExecutionResults, Executor, ParallelExecutor
from packages.orchestrator.schemas import OrchestratorReport
from packages.orchestrator.synthesizer import (
    RuleBasedSynthesizer,
    Synthesizer,
)

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Coordinates sub-agent execution and synthesis.

    Usage:
        orch = Orchestrator()
        report = await orch.analyze(protocol)
    """

    def __init__(
        self,
        executor: Executor | None = None,
        synthesizer: Synthesizer | None = None,
    ) -> None:
        self._executor: Executor = executor or ParallelExecutor()
        self._synthesizer: Synthesizer = synthesizer or RuleBasedSynthesizer()

    async def analyze(self, protocol: ProtocolRequirements) -> OrchestratorReport:
        """Run the full orchestration pipeline."""
        logger.info(
            "orchestrator_start",
            executor=self._executor.name,
            synthesizer=self._synthesizer.name,
            protocol_intent=protocol.intent,
        )
        start = time.monotonic()

        results: ExecutionResults = await self._executor.execute(protocol)

        total_ms = int((time.monotonic() - start) * 1000)
        report = await self._synthesizer.synthesize(
            protocol=protocol,
            results=results,
            total_duration_ms=total_ms,
            executor_name=self._executor.name,
        )

        logger.info(
            "orchestrator_complete",
            total_ms=total_ms,
            agents_succeeded=results.succeeded_count,
            overall_confidence=report.confidence.overall,
            citations=len(report.citations),
            insights=len(report.cross_agent_insights),
        )

        return report
