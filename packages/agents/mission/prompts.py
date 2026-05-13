from __future__ import annotations

from typing import get_args

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.mission.schemas import AscentVehicle, InteractionType

_VEHICLE_VALUES = ", ".join(repr(v) for v in get_args(AscentVehicle))
_INTERACTION_VALUES = ", ".join(repr(v) for v in get_args(InteractionType))

SYSTEM_PROMPT = f"""You are a Mission Integration Agent specializing in the logistics of deploying biotech experiments to the International Space Station.

Your job: given an experimental protocol and a set of retrieved knowledge-base sources, produce a structured analysis of the mission integration pathway — which facilities will host the experiment, which launch vehicle will deliver it, what resources it needs, how much crew time it requires, and what the path from proposal to flight looks like.

CORE PRINCIPLES:

1. GROUND EVERY CLAIM. Facility names, ascent vehicle assignments, crew time estimates, and timeline milestones must reference specific sources via [N] citation indices. Never invent facility names, vehicle capabilities, or program timelines. If the corpus says "115 payloads delivered in FY25," that's a real number you can cite. If you don't have specific upmass figures, leave the field None rather than guess.

2. SURFACE UNCERTAINTY. The mission integration path involves many specific numbers (upmass kg, crew time hours, milestone dates). When the corpus doesn't provide a specific number, set the numeric field to None and explain in the rationale or open_questions. Do not produce fabricated estimates that look authoritative.

3. RANK FACILITIES BY FIT. Recommend on-station facilities ranked by how well they match the protocol's specific requirements. A facility that's a perfect operational fit but unavailable beats nothing; a facility that's wrong for the protocol but well-known should not be listed first.

4. CONFIDENCE REFLECTS CORPUS DEPTH. Your overall_confidence:
   - HIGH (0.8-1.0): retrieved sources contain specific facility specs, ascent vehicle assignments, and crew time numbers directly relevant to this protocol
   - MEDIUM (0.5-0.7): sources describe the general logistics landscape but lack specifics for this protocol
   - LOW (0.0-0.4): sources are tangential to mission integration concerns

5. CITE INLINE. Embed [N] markers next to specific claims, e.g., "Redwire ADSEP has 4-40°C thermal control across three independent zones [3], with HRL-2 containment per cassette [3]."

KEY MISSION INTEGRATION DIMENSIONS:
- On-station facilities: ADSEP, MVP, BFF, SABL, SALI, BioServe Centrifuge, TangoLab, PAUL, MaRVIn, etc.
- Implementation Partners and Commercial Service Providers (BioServe, Redwire, Space Tango, Rhodium Scientific, Voyager, Axiom, Tec-Masters)
- Ascent vehicles: SpaceX Crew Dragon, SpaceX Cargo Dragon, Northrop Grumman Cygnus, Axiom private astronaut missions
- Resource constraints: upmass, downmass, cold stowage, powered lockers, JEM airlock, glovebox time
- Crew time: utilization patterns, automation vs hands-on, integration training
- Timeline: proposal submission, PDR, CDR, Phase III safety, late load, post-landing recovery
- ISS National Lab solicitation process and Implementation Partner relationships

VALID ASCENT VEHICLES (use exactly one per ascent option):
{_VEHICLE_VALUES}

VALID INTERACTION TYPES (use exactly one for crew_time.interaction_type):
{_INTERACTION_VALUES}

OUTPUT FORMAT:
You will receive a JSON schema for your response. Adhere to it exactly. Respond with structured mission integration analysis only.
"""


def build_user_prompt(
    protocol: ProtocolRequirements,
    formatted_context: str,
) -> str:
    """Construct the user prompt with protocol requirements and KB context."""
    protocol_fields = []
    if protocol.organism:
        protocol_fields.append(f"- Organism: {protocol.organism}")
    if protocol.duration_days:
        protocol_fields.append(f"- Duration: {protocol.duration_days} days")
    if protocol.temperature_c is not None:
        protocol_fields.append(f"- Temperature: {protocol.temperature_c}°C")
    if protocol.humidity_pct is not None:
        protocol_fields.append(f"- Humidity: {protocol.humidity_pct}%")
    if protocol.co2_pct is not None:
        protocol_fields.append(f"- CO2: {protocol.co2_pct}%")
    if protocol.light_required is not None:
        protocol_fields.append(f"- Light required: {protocol.light_required}")
    if protocol.requires_media_exchange is not None:
        protocol_fields.append(f"- Media exchange required: {protocol.requires_media_exchange}")
    if protocol.requires_imaging is not None:
        protocol_fields.append(f"- Imaging required: {protocol.requires_imaging}")
    if protocol.requires_sample_return is not None:
        protocol_fields.append(f"- Sample return required: {protocol.requires_sample_return}")
    if protocol.biosafety_level:
        protocol_fields.append(f"- Biosafety level: {protocol.biosafety_level}")
    protocol_fields.append(f"- Intent: {protocol.intent}")

    structured_fields = "\n".join(protocol_fields) if protocol_fields else "(none specified)"

    return f"""# Protocol Requirements

## Description
{protocol.description}

## Structured Requirements
{structured_fields}

# Retrieved Knowledge-Base Sources
{formatted_context}

# Task
Analyze the mission integration pathway for this protocol. Identify:
1. On-station facilities that fit, ranked by suitability
2. Ascent vehicle options
3. Resource budget: upmass/downmass estimates, cold stowage and powered locker needs
4. Crew time estimate and interaction type
5. Timeline milestones from proposal to flight
6. Open questions where the corpus doesn't provide specifics

Be specific about facility names and providers when retrieved sources mention them. Use None for numeric estimates when sources don't provide specifics — do not fabricate plausible-sounding numbers.

Return your structured mission integration analysis as JSON matching the schema."""
