"""CLI for the Microgravity Adaptation Agent.

Usage:
    make mg-agent preset=plant_growth
    uv run python scripts/microgravity_agent.py --preset plant_growth
"""

from __future__ import annotations

import argparse
import asyncio

from scripts.hardware_agent import PRESETS

from apps.api.logging_config import configure_logging
from packages.agents.microgravity.agent import MicrogravityAgent
from packages.agents.microgravity.schemas import MicrogravityAgentOutput


def _print_output(output: MicrogravityAgentOutput) -> None:
    print()
    print("=" * 80)
    print("MICROGRAVITY ADAPTATION ANALYSIS")
    print("=" * 80)
    print()
    print(f"Summary: {output.analysis.summary}")
    print(
        f"Overall confidence: {output.analysis.overall_confidence:.2f}"
        f"  | Retrieval: {output.retrieval_chunks_used} chunks, {output.retrieval_ms}ms"
        f"  | Reasoning: {output.reasoning_ms}ms"
    )
    print()

    if output.analysis.modifications:
        print("PROTOCOL MODIFICATIONS")
        print("-" * 80)
        sev_marker = {"critical": "[CRITICAL]", "important": "[IMPORTANT]", "minor": "[minor]"}
        for i, mod in enumerate(output.analysis.modifications, 1):
            print(f"\n{i}. {sev_marker[mod.severity]} Aspect: {mod.aspect}")
            print(f"   Earth assumption:  {mod.earthbound_assumption}")
            print(f"   Microgravity:      {mod.microgravity_reality}")
            print(f"   Recommended:       {mod.recommended_change}")
            if mod.citation_indices:
                print(f"   Cites: {mod.citation_indices}")
    else:
        print("PROTOCOL MODIFICATIONS: none identified")
    print()

    if output.analysis.expected_behaviors:
        print("EXPECTED BEHAVIORS")
        print("-" * 80)
        for i, b in enumerate(output.analysis.expected_behaviors, 1):
            print(f"\n{i}. {b.phenomenon}")
            print(f"   Why:    {b.explanation}")
            print(f"   Impact: {b.impact_on_experiment}")
            if b.citation_indices:
                print(f"   Cites: {b.citation_indices}")
        print()

    if output.analysis.research_precedents:
        print("RESEARCH PRECEDENTS")
        print("-" * 80)
        for i, p in enumerate(output.analysis.research_precedents, 1):
            print(f"\n{i}. {p.description}")
            print(f"   Relevance: {p.relevance}")
            print(f"   Finding:   {p.finding}")
            if p.citation_indices:
                print(f"   Cites: {p.citation_indices}")
        print()

    if output.citations:
        print("CITATIONS")
        print("-" * 80)
        for c in output.citations:
            page = f", p.{c.page_number}" if c.page_number else ""
            print(f"  [{c.index}] {c.title}{page}")
            print(f"      Score: {c.relevance_score:.3f}  {c.source_url}")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Microgravity Adaptation Agent")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    configure_logging()
    protocol = PRESETS[args.preset]

    agent = MicrogravityAgent()
    output = await agent.analyze(protocol)

    if args.json:
        print(output.model_dump_json(indent=2))
    else:
        _print_output(output)


if __name__ == "__main__":
    asyncio.run(main())
