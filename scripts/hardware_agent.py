"""Run the hardware compatibility agent from the CLI.

Usage:
    make hw-agent preset=cell_culture
    make hw-agent preset=plant_growth
    make hw-agent preset=protein_crystallization
    uv run python scripts/hardware_agent.py --preset cell_culture
    uv run python scripts/hardware_agent.py --description "..." --organism "E. coli"
"""

from __future__ import annotations

import argparse
import asyncio

from apps.api.logging_config import configure_logging
from packages.agents.hardware.agent import HardwareAgent
from packages.agents.hardware.schemas import HardwareAgentOutput, ProtocolRequirements

# ---------------------------------------------------------------------------
# Preset protocols for quick testing
# ---------------------------------------------------------------------------

PRESETS: dict[str, ProtocolRequirements] = {
    "cell_culture": ProtocolRequirements(
        description=(
            "Mammalian cell culture study investigating the effect of microgravity on "
            "CHO cell growth kinetics and monoclonal antibody production. Cells will be "
            "maintained in batch culture for 21 days at 37°C with 5% CO2. Media exchange "
            "required every 3 days. Fluorescence imaging at day 7, 14, and 21. Fixed samples "
            "to be returned to Earth for post-flight proteomics analysis."
        ),
        organism="CHO cells",
        duration_days=21,
        temperature_c=37.0,
        co2_pct=5.0,
        requires_media_exchange=True,
        requires_imaging=True,
        requires_sample_return=True,
        biosafety_level="BSL-1",
        intent="research",
    ),
    "plant_growth": ProtocolRequirements(
        description=(
            "Arabidopsis thaliana seed germination and root development study in microgravity. "
            "Seeds will be germinated and grown for 14 days under continuous LED lighting. "
            "Root gravitropism and gene expression will be studied. Plants will be fixed in "
            "RNAlater at day 14 for return to Earth for transcriptomic analysis. Water delivery "
            "to roots in microgravity is a primary operational concern."
        ),
        organism="Arabidopsis thaliana",
        duration_days=14,
        light_required=True,
        requires_sample_return=True,
        biosafety_level="BSL-1",
        intent="research",
    ),
    "protein_crystallization": ProtocolRequirements(
        description=(
            "Protein crystallization experiment targeting lysozyme as a model system to study "
            "crystal growth quality in microgravity versus ground controls. Vapor diffusion "
            "method with hanging drop setup. No active temperature control required beyond "
            "ambient ISS cabin temperature (~22°C). Crystals to be returned to Earth for "
            "X-ray diffraction analysis. No crew interaction required after setup."
        ),
        organism=None,
        duration_days=30,
        temperature_c=22.0,
        requires_sample_return=True,
        biosafety_level="BSL-1",
        intent="research",
    ),
}


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_output(result: HardwareAgentOutput) -> None:
    print()
    print("=" * 80)
    print("HARDWARE COMPATIBILITY ANALYSIS")
    print("=" * 80)
    print()

    a = result.analysis
    print(f"Summary: {a.summary}")
    print()
    print(
        f"Overall confidence: {a.overall_confidence:.2f}  "
        f"| Retrieval: {result.retrieval_ms}ms  "
        f"| Reasoning: {result.reasoning_ms}ms  "
        f"| Chunks used: {result.retrieval_chunks_used}"
    )
    print()

    if a.recommended_hardware:
        print("RECOMMENDED HARDWARE")
        print("-" * 80)
        for i, hw in enumerate(a.recommended_hardware, start=1):
            citations = ", ".join(f"[{c}]" for c in hw.citation_indices) or "none"
            print(f"  {i}. {hw.name}  (fit={hw.fit_score:.2f}, citations={citations})")
            print(f"     {hw.rationale}")
            if hw.constraints:
                print(f"     Constraints: {'; '.join(hw.constraints)}")
        print()

    if a.gaps:
        print("GAPS")
        print("-" * 80)
        for gap in a.gaps:
            print(f"  [{gap.severity.upper()}] {gap.requirement}")
            print(f"    {gap.notes}")
        print()

    if result.citations:
        print("CITATIONS")
        print("-" * 80)
        for c in result.citations:
            page = f" p.{c.page_number}" if c.page_number else ""
            print(f"  [{c.index}] {c.title}{page}  (score={c.relevance_score:.3f})")
            print(f"       {c.source_url}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the hardware compatibility agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", choices=list(PRESETS), help="Use a preset protocol")
    group.add_argument("--description", help="Protocol description (free text)")

    parser.add_argument("--organism", default=None)
    parser.add_argument("--duration-days", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--top-n", type=int, default=8)
    args = parser.parse_args()

    configure_logging()

    if args.preset:
        protocol = PRESETS[args.preset]
    else:
        protocol = ProtocolRequirements(
            description=args.description,
            organism=args.organism,
            duration_days=args.duration_days,
        )

    agent = HardwareAgent()
    result = await agent.analyze(protocol, retrieval_top_n=args.top_n)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print_output(result)


if __name__ == "__main__":
    asyncio.run(main())
