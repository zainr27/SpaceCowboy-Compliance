from __future__ import annotations

from fastapi import APIRouter, HTTPException

from packages.agents.hardware.agent import HardwareAgent
from packages.agents.hardware.schemas import HardwareAgentOutput, ProtocolRequirements
from packages.agents.microgravity.agent import MicrogravityAgent
from packages.agents.microgravity.schemas import MicrogravityAgentOutput
from packages.agents.mission.agent import MissionAgent
from packages.agents.mission.schemas import MissionAgentOutput
from packages.agents.safety.agent import SafetyAgent
from packages.agents.safety.schemas import SafetyAgentOutput

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
