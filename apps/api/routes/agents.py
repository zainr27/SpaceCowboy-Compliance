from __future__ import annotations

from fastapi import APIRouter, HTTPException

from packages.agents.hardware.agent import HardwareAgent
from packages.agents.hardware.schemas import HardwareAgentOutput, ProtocolRequirements

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
