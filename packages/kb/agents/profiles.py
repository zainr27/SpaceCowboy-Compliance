from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class AgentProfile(StrEnum):
    """The five Layer 3 sub-agents, each with a focused retrieval scope."""

    HARDWARE = "hardware"
    MICROGRAVITY = "microgravity"
    SAFETY = "safety"
    MISSION = "mission"
    REGULATORY = "regulatory"


class ProfileConfig(BaseModel):
    """Per-agent retrieval defaults."""

    profile: AgentProfile
    source_types: list[str]
    default_k: int = 20
    default_top_n: int = 5
    description: str


PROFILES: dict[AgentProfile, ProfileConfig] = {
    AgentProfile.HARDWARE: ProfileConfig(
        profile=AgentProfile.HARDWARE,
        source_types=["hardware_spec", "nasa_payload_guide", "iss_annual_report"],
        default_top_n=8,
        description="ISS hardware capabilities, payload guides, hardware mentioned in mission reports.",
    ),
    AgentProfile.MICROGRAVITY: ProfileConfig(
        profile=AgentProfile.MICROGRAVITY,
        source_types=["paper", "nasa_payload_guide"],
        description="Microgravity effects on biological systems, fluid dynamics, protocol adaptations.",
    ),
    AgentProfile.SAFETY: ProfileConfig(
        profile=AgentProfile.SAFETY,
        source_types=["nasa_payload_guide", "regulatory", "casis_solicitation"],
        default_top_n=10,
        description="CASIS safety review process, biosafety levels, containment requirements, hazard classification.",
    ),
    AgentProfile.MISSION: ProfileConfig(
        profile=AgentProfile.MISSION,
        source_types=[
            "nasa_payload_guide",
            "iss_annual_report",
            "casis_solicitation",
            "hardware_spec",
        ],
        description="Mission integration, upmass/downmass, crew time, sample preservation, timeline.",
    ),
    AgentProfile.REGULATORY: ProfileConfig(
        profile=AgentProfile.REGULATORY,
        source_types=["regulatory", "paper"],
        description="FDA pathways, IND requirements, ITAR/EAR for space-bio applications.",
    ),
}


def get_profile(profile: AgentProfile) -> ProfileConfig:
    return PROFILES[profile]
