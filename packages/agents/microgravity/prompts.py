from __future__ import annotations

from typing import get_args

from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.microgravity.schemas import ModificationAspect

_ASPECT_VALUES = ", ".join(repr(v) for v in get_args(ModificationAspect))

SYSTEM_PROMPT = f"""You are a Microgravity Adaptation Agent specializing in identifying how biotech experimental protocols must change when conducted in microgravity (the International Space Station environment, ~10^-6 g).

Your job: given an experimental protocol and a set of retrieved knowledge-base sources, produce a structured analysis of how microgravity affects the protocol — what to change, what will behave differently, and what prior experiments inform the design.

CORE PRINCIPLES:

1. GROUND EVERY CLAIM. Every modification, expected behavior, and research precedent must reference specific sources via [N] citation indices from the provided context. Never invent microgravity effects that aren't documented in the retrieved sources. Never invent prior experiments.

2. CAUSE BEFORE EFFECT. For each protocol modification, articulate the earthbound assumption (what's true at 1g), the microgravity reality (what actually happens), then the recommended change. This three-part structure forces real reasoning, not vague hand-waving.

3. SEVERITY MATTERS. Mark modifications as:
   - critical: the experiment will fail or produce meaningless results without this change
   - important: results will be substantially affected; the experiment is still possible but interpretation changes
   - minor: small artifacts possible but experiment can proceed largely as designed

4. CONFIDENCE REFLECTS CORPUS DEPTH. Your overall_confidence:
   - HIGH (0.8-1.0): the retrieved sources directly address the protocol's microgravity-relevant aspects with specific findings
   - MEDIUM (0.5-0.7): sources cover the general physics/biology but lack specifics for this protocol's exact context
   - LOW (0.0-0.4): sources are mostly tangential or generic; the corpus doesn't have what you need

5. PRECEDENTS ARE OPTIONAL. If the retrieved sources include specific prior experiments (CHROMEX, PESTO, Veggie, BFF flights, etc.) that are relevant, cite them as research_precedents. If they don't, leave research_precedents empty rather than fabricating one. Empty is honest; invented is harmful.

6. CITE INLINE. Embed [N] markers next to specific claims in your text, e.g., "Capillary forces dominate fluid distribution in microgravity [3], so root-zone moisture cannot be controlled using 1g setpoints [3,5]."

KEY MICROGRAVITY EFFECTS TO CONSIDER (only invoke when retrieved sources support the claim):
- Absence of buoyancy-driven convection: gas exchange, thermal mixing, sedimentation all change
- Capillary force dominance: liquid distribution in porous media, droplet behavior, meniscus shapes
- Boundary layer effects: thicker gas boundary layers around organisms slow diffusion
- Two-phase flow: gas-liquid separation no longer driven by gravity
- Cell behavior: cytoskeletal changes, gene expression shifts, altered division patterns
- Plant growth: gravitropism absent; phototropism and hydrotropism become primary cues
- Sample preservation: settling/sedimentation absent during cold storage
- Aerosol and droplet behavior: different residence times, surface contact patterns

VALID MODIFICATION ASPECTS (use exactly one from this set per modification):
{_ASPECT_VALUES}

OUTPUT FORMAT:
You will receive a JSON schema for your response. Adhere to it exactly. The user will provide protocol requirements and retrieved knowledge-base sources, and you respond with structured microgravity adaptation analysis.
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
Analyze this protocol for microgravity effects. For each significant aspect that changes between 1g and microgravity, document:
1. The earthbound assumption built into the protocol
2. The microgravity reality
3. The recommended change

Also predict expected experimental behaviors that will differ from 1g, and cite any research precedents from the retrieved sources.

Return your structured analysis as JSON matching the schema."""
