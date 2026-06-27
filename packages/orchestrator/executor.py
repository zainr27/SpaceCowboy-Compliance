from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Protocol

import structlog

from packages.agents.base import LLM_TIMEOUT_S, RETRIEVAL_TIMEOUT_S
from packages.agents.hardware.agent import HardwareAgent
from packages.agents.hardware.schemas import HardwareAgentOutput, ProtocolRequirements
from packages.agents.microgravity.agent import MicrogravityAgent
from packages.agents.microgravity.schemas import MicrogravityAgentOutput
from packages.agents.mission.agent import MissionAgent
from packages.agents.mission.schemas import MissionAgentOutput
from packages.agents.regulatory.agent import RegulatoryAgent
from packages.agents.regulatory.schemas import RegulatoryAgentOutput
from packages.agents.safety.agent import SafetyAgent
from packages.agents.safety.schemas import SafetyAgentOutput
from packages.orchestrator.schemas import AgentExecution

logger = structlog.get_logger(__name__)

# Hard ceiling per sub-agent. A single agent that exceeds this is recorded as
# a failure so the report still ships with the agents that did finish, rather
# than the whole orchestration hanging on one slow upstream call.
#
# This is sized against the agent's real serial worst case rather than a round
# number: the retrieval phase is bounded by RETRIEVAL_TIMEOUT_S (Voyage embed +
# hybrid SQL + Cohere rerank for all decomposed queries) and the single LLM
# call is bounded by LLM_TIMEOUT_S, run back-to-back, plus a small headroom for
# scheduling/serialization. Because the inner timeouts now actually bound their
# calls, this ceiling is a true upper bound, not an aspiration.
_AGENT_TIMEOUT_HEADROOM_S = 5.0
AGENT_TIMEOUT_S = RETRIEVAL_TIMEOUT_S + LLM_TIMEOUT_S + _AGENT_TIMEOUT_HEADROOM_S  # 80.0s


class ExecutionResults:
    """Container holding the results from all sub-agents.

    Some agents may have failed; check executions for status.
    """

    def __init__(self) -> None:
        self.executions: list[AgentExecution] = []
        self.hardware: HardwareAgentOutput | None = None
        self.microgravity: MicrogravityAgentOutput | None = None
        self.safety: SafetyAgentOutput | None = None
        self.mission: MissionAgentOutput | None = None
        self.regulatory: RegulatoryAgentOutput | None = None

    @property
    def succeeded_count(self) -> int:
        return sum(1 for e in self.executions if e.succeeded)


class Executor(Protocol):
    """Protocol for sub-agent executors.

    Future cascaded executors implement this same interface, accepting
    information-passing between agents.
    """

    name: str

    async def execute(self, protocol: ProtocolRequirements) -> ExecutionResults: ...


class ParallelExecutor:
    """Runs all five sub-agents in parallel via asyncio.gather.

    Each agent runs independently with no information passing. Total runtime
    approximately max(agent_runtimes).
    """

    name = "parallel"

    def __init__(self) -> None:
        self._hardware = HardwareAgent()
        self._microgravity = MicrogravityAgent()
        self._safety = SafetyAgent()
        self._mission = MissionAgent()
        self._regulatory = RegulatoryAgent()

    async def execute(self, protocol: ProtocolRequirements) -> ExecutionResults:
        logger.info("parallel_executor_start", protocol_intent=protocol.intent)
        start = time.monotonic()

        results = ExecutionResults()

        tasks = [
            self._run_one("hardware", self._hardware.analyze(protocol)),
            self._run_one("microgravity", self._microgravity.analyze(protocol)),
            self._run_one("safety", self._safety.analyze(protocol)),
            self._run_one("mission", self._mission.analyze(protocol)),
            self._run_one("regulatory", self._regulatory.analyze(protocol)),
        ]

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                logger.error("parallel_executor_unexpected_exception", exc_info=outcome)
                continue
            execution, output = outcome
            results.executions.append(execution)
            if execution.succeeded and output is not None:
                if execution.agent == "hardware":
                    results.hardware = output  # type: ignore[assignment]
                elif execution.agent == "microgravity":
                    results.microgravity = output  # type: ignore[assignment]
                elif execution.agent == "safety":
                    results.safety = output  # type: ignore[assignment]
                elif execution.agent == "mission":
                    results.mission = output  # type: ignore[assignment]
                elif execution.agent == "regulatory":
                    results.regulatory = output  # type: ignore[assignment]

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "parallel_executor_complete",
            total_ms=total_ms,
            succeeded=results.succeeded_count,
            failed=5 - results.succeeded_count,
        )
        return results

    @staticmethod
    async def _run_one(
        agent_name: str,
        coro: object,
    ) -> tuple[AgentExecution, object | None]:
        """Run a single agent coroutine, capturing success/failure.

        Bounded by AGENT_TIMEOUT_S, which is itself the sum of the sub-call
        ceilings the agent can hit serially (RETRIEVAL_TIMEOUT_S for the whole
        multi-query retrieval phase + LLM_TIMEOUT_S for the single reasoning
        call + headroom). A timeout is treated as a normal agent failure
        (recorded, not raised) so the rest of the run proceeds. On expiry
        asyncio.timeout cancels the coroutine, which propagates cancellation
        into the in-flight OpenAI/Voyage/Cohere request at its next await point
        rather than letting it run to completion in the background.
        """
        start = time.monotonic()
        try:
            async with asyncio.timeout(AGENT_TIMEOUT_S):
                output = await coro  # type: ignore[misc]
            duration_ms = int((time.monotonic() - start) * 1000)
            chunks_used = getattr(output, "retrieval_chunks_used", 0)
            return (
                AgentExecution(
                    agent=agent_name,  # type: ignore[arg-type]
                    succeeded=True,
                    duration_ms=duration_ms,
                    chunks_used=chunks_used,
                    error=None,
                ),
                output,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("sub_agent_failed", agent=agent_name)
            return (
                AgentExecution(
                    agent=agent_name,  # type: ignore[arg-type]
                    succeeded=False,
                    duration_ms=duration_ms,
                    chunks_used=0,
                    error=f"{type(e).__name__}: {e}",
                ),
                None,
            )

    async def execute_streaming(
        self,
        protocol: ProtocolRequirements,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Run all five agents in parallel, yielding a progress event as each completes.

        ``is_disconnected`` is an optional async predicate (e.g.
        ``request.is_disconnected``). It is checked BEFORE kicking off the five
        agents and again BEFORE the synthesis LLM call, so a client that closes
        the connection does not pay for agent work or the executive-summary
        gpt-4o call. On a detected disconnect the generator returns silently
        without emitting further events.

        Yields:
            {"type": "progress", "agent": "hardware", "succeeded": True,
             "duration_ms": 3200, "error": null, "output": {...} | null}
            ... (one per agent, in completion order — output carries the
                 agent's full result so the client can reveal it immediately)
            {"type": "synthesizing"}   # all agents done; building the summary
            {"type": "complete", "report": {...}}
            OR
            {"type": "out_of_scope", "category": "...", "reason": "..."}
            OR
            {"type": "error", "message": "..."}
        """
        from packages.orchestrator.gap_store import record_gaps
        from packages.orchestrator.scope import classify_scope
        from packages.orchestrator.synthesizer import RuleBasedSynthesizer

        async def _disconnected() -> bool:
            return bool(await is_disconnected()) if is_disconnected is not None else False

        # Don't even build the agent tasks / fire the upstream calls if the
        # client is already gone.
        if await _disconnected():
            return

        # Pre-flight scope gate: refuse clearly out-of-domain requests up front
        # so we never stream five agents over an off-domain prompt.
        verdict = await classify_scope(protocol)
        if not verdict.in_scope:
            yield {
                "type": "out_of_scope",
                "category": verdict.category,
                "reason": verdict.reason,
            }
            return

        results = ExecutionResults()

        task_map: dict[asyncio.Task, str] = {}  # type: ignore[type-arg]
        for agent_name, coro in [
            ("hardware", self._hardware.analyze(protocol)),
            ("microgravity", self._microgravity.analyze(protocol)),
            ("safety", self._safety.analyze(protocol)),
            ("mission", self._mission.analyze(protocol)),
            ("regulatory", self._regulatory.analyze(protocol)),
        ]:
            task = asyncio.create_task(self._run_one(agent_name, coro))
            task_map[task] = agent_name

        wall_start = time.monotonic()
        pending: set[asyncio.Task] = set(task_map.keys())  # type: ignore[type-arg]

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                execution, output = await task
                results.executions.append(execution)
                output_json = (
                    output.model_dump(mode="json")  # type: ignore[attr-defined]
                    if (execution.succeeded and output is not None)
                    else None
                )
                if execution.succeeded and output is not None:
                    if execution.agent == "hardware":
                        results.hardware = output  # type: ignore[assignment]
                    elif execution.agent == "microgravity":
                        results.microgravity = output  # type: ignore[assignment]
                    elif execution.agent == "safety":
                        results.safety = output  # type: ignore[assignment]
                    elif execution.agent == "mission":
                        results.mission = output  # type: ignore[assignment]
                    elif execution.agent == "regulatory":
                        results.regulatory = output  # type: ignore[assignment]
                yield {
                    "type": "progress",
                    "agent": execution.agent,
                    "succeeded": execution.succeeded,
                    "duration_ms": execution.duration_ms,
                    "error": execution.error,
                    "output": output_json,
                }

        total_ms = int((time.monotonic() - wall_start) * 1000)
        # Don't pay for the gpt-4o executive-summary call if the client has
        # already left — this is the single most expensive step and runs after
        # all per-agent results are already streamed out.
        if await _disconnected():
            return
        # Signal that all agents are in and the cross-agent summary call has
        # begun, so the client can show a synthesis step instead of a dead gap.
        yield {"type": "synthesizing"}
        try:
            report = await RuleBasedSynthesizer().synthesize(
                protocol=protocol,
                results=results,
                total_duration_ms=total_ms,
                executor_name=self.name,
            )
            record_gaps(report)
            yield {"type": "complete", "report": report.model_dump(mode="json")}
        except Exception as e:
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}


class CascadedExecutor:
    """Stub for a future cascaded executor.

    A cascaded executor would run sub-agents in sequence, passing each
    agent's output as additional context to subsequent agents. Safety runs
    first to establish BSL, then hardware with containment filtering, then
    microgravity, mission, and regulatory with the established context.

    The interface matches ParallelExecutor so a downstream substitution
    requires no caller changes.
    """

    name = "cascaded"

    async def execute(self, protocol: ProtocolRequirements) -> ExecutionResults:
        raise NotImplementedError(
            "CascadedExecutor is reserved for future implementation. Use ParallelExecutor for now."
        )
