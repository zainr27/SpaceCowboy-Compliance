from __future__ import annotations

import json as _json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

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
from packages.orchestrator.executor import ParallelExecutor
from packages.orchestrator.orchestrator import Orchestrator
from packages.orchestrator.schemas import OrchestratorReport

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/hardware/analyze", response_model=HardwareAgentOutput)
async def hardware_analyze(protocol: ProtocolRequirements) -> HardwareAgentOutput:
    """Analyze a biotech protocol for ISS hardware compatibility."""
    try:
        agent = HardwareAgent()
        return await agent.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Hardware analysis failed: {type(e).__name__}",
        ) from e


@router.post("/microgravity/analyze", response_model=MicrogravityAgentOutput)
async def microgravity_analyze(protocol: ProtocolRequirements) -> MicrogravityAgentOutput:
    """Analyze a biotech protocol for microgravity adaptation requirements.

    Returns structured modifications, expected behaviors, and research precedents.
    """
    try:
        agent = MicrogravityAgent()
        return await agent.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Microgravity agent failed: {type(e).__name__}: {e}",
        ) from e


@router.post("/safety/analyze", response_model=SafetyAgentOutput)
async def safety_analyze(protocol: ProtocolRequirements) -> SafetyAgentOutput:
    """Screen a biotech protocol for ISS safety review requirements.

    Returns biosafety classification, hazards, containment requirements,
    and NASA safety review milestones.
    """
    try:
        agent = SafetyAgent()
        return await agent.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Safety agent failed: {type(e).__name__}: {e}",
        ) from e


@router.post("/mission/analyze", response_model=MissionAgentOutput)
async def mission_analyze(protocol: ProtocolRequirements) -> MissionAgentOutput:
    """Analyze a biotech protocol for ISS mission integration logistics.

    Returns facility recommendations, ascent options, resource budgets,
    crew time estimates, and project timeline.
    """
    try:
        agent = MissionAgent()
        return await agent.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Mission agent failed: {type(e).__name__}: {e}",
        ) from e


@router.post("/regulatory/analyze", response_model=RegulatoryAgentOutput)
async def regulatory_analyze(protocol: ProtocolRequirements) -> RegulatoryAgentOutput:
    """Analyze a biotech protocol for regulatory pathway requirements.

    Returns applicable regulatory frameworks, compliance requirements,
    review processes, and open questions requiring external counsel.
    """
    try:
        agent = RegulatoryAgent()
        return await agent.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Regulatory agent failed: {type(e).__name__}: {e}",
        ) from e


@router.post("/orchestrator/analyze", response_model=OrchestratorReport)
async def orchestrator_analyze(protocol: ProtocolRequirements) -> OrchestratorReport:
    """Run the complete five-agent analysis on a biotech protocol.

    Returns a unified report with executive summary, per-agent results,
    cross-agent insights, deduplicated citations, and aggregated open questions.
    """
    try:
        orch = Orchestrator()
        return await orch.analyze(protocol)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator failed: {type(e).__name__}: {e}",
        ) from e


@router.post("/orchestrator/stream")
async def orchestrator_stream(
    protocol: ProtocolRequirements,
    request: Request,
) -> StreamingResponse:
    """Stream orchestrator progress as Server-Sent Events.

    Each event is:  data: {json}\\n\\n
    Event types: progress | complete | error
    """
    executor = ParallelExecutor()

    async def generate():  # type: ignore[return]
        try:
            async for event in executor.execute_streaming(protocol):
                if await request.is_disconnected():
                    break
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
