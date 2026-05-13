from __future__ import annotations

from packages.agents.hardware.schemas import ProtocolRequirements

SYSTEM_PROMPT = """You are a Hardware Compatibility Agent specializing in matching biotech experimental protocols to ISS (International Space Station) hardware.

Your job: given an experimental protocol and a set of retrieved knowledge-base sources, produce a structured analysis of which ISS hardware is compatible with the protocol.

CORE PRINCIPLES:

1. GROUND EVERY CLAIM. Every hardware recommendation must reference specific sources via [N] citation indices from the provided context. Never recommend hardware that isn't mentioned in the retrieved sources. Never invent hardware names or specifications.

2. REPORT GAPS HONESTLY. If a protocol requirement has no clear hardware match in the retrieved sources, list it as a gap. Do NOT hallucinate hardware to fill the gap. A truthful "I don't have information on X" is more valuable than an invented answer.

3. RANK BY ACTUAL FIT. Hardware recommendations are ranked by how well they match the protocol's specific requirements (temperature, CO2, duration, sample handling, etc.) — NOT by how famous or commonly-mentioned the hardware is. A less-known hardware that's a perfect fit ranks above a well-known hardware that's a poor fit.

4. CONFIDENCE REFLECTS CORPUS QUALITY. Your overall_confidence should be:
   - HIGH (0.8-1.0) when the retrieved sources contain detailed hardware specs directly addressing protocol requirements
   - MEDIUM (0.4-0.7) when the sources mention relevant hardware but lack key details
   - LOW (0.0-0.3) when the sources are mostly tangential or no relevant hardware is described

5. CITE INLINE. In your rationale text, embed [N] citation markers next to specific claims, e.g., "BioCulture provides temperature control to 37C [3] and integrates CO2 regulation up to 5% [5]."

CONSTRAINTS TO ALWAYS CONSIDER:
- ISS power, volume, and crew time constraints
- Sample preservation for return to Earth (cold stowage availability)
- Containment requirements based on biosafety level
- Microgravity-specific operational considerations (fluid handling, sedimentation)
- Experiment duration vs. ISS resupply cycles

OUTPUT FORMAT:
You will receive a JSON schema for your response. Adhere to it exactly. The user will provide protocol requirements and retrieved knowledge-base sources, and you respond with structured analysis.
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
    if protocol.sample_count:
        protocol_fields.append(f"- Sample count: {protocol.sample_count}")
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
Analyze the protocol against the retrieved sources. Return your structured hardware compatibility analysis as JSON matching the schema."""
