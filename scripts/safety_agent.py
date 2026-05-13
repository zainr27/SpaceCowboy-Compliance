"""CLI for the Safety Screening Agent.

Usage:
    make safety-agent preset=cell_culture
    uv run python scripts/safety_agent.py --preset cell_culture
"""

from __future__ import annotations

import argparse
import asyncio

from scripts.hardware_agent import PRESETS

from apps.api.logging_config import configure_logging
from packages.agents.safety.agent import SafetyAgent
from packages.agents.safety.schemas import SafetyAgentOutput


def _print_output(output: SafetyAgentOutput) -> None:
    print()
    print("=" * 80)
    print("SAFETY SCREENING ANALYSIS")
    print("=" * 80)
    print()
    print(f"Summary: {output.analysis.summary}")
    print(f"Biosafety classification: {output.analysis.biosafety_classification}")
    print(
        f"Overall confidence: {output.analysis.overall_confidence:.2f}"
        f"  | Retrieval: {output.retrieval_chunks_used} chunks, {output.retrieval_ms}ms"
        f"  | Reasoning: {output.reasoning_ms}ms"
    )
    print()

    if output.analysis.hazards:
        print("IDENTIFIED HAZARDS")
        print("-" * 80)
        for i, h in enumerate(output.analysis.hazards, 1):
            print(f"\n{i}. [{h.severity.upper()}] [{h.likelihood} likelihood] {h.category}")
            print(f"   Description: {h.description}")
            print(f"   Mitigation:  {h.mitigation}")
            if h.citation_indices:
                print(f"   Cites: {h.citation_indices}")
    else:
        print("IDENTIFIED HAZARDS: none in retrieved sources")
    print()

    if output.analysis.containment_requirements:
        print("CONTAINMENT REQUIREMENTS")
        print("-" * 80)
        for i, req in enumerate(output.analysis.containment_requirements, 1):
            print(f"\n{i}. {req.requirement}")
            print(f"   Rationale: {req.rationale}")
            if req.citation_indices:
                print(f"   Cites: {req.citation_indices}")
        print()

    if output.analysis.review_milestones:
        print("NASA SAFETY REVIEW MILESTONES")
        print("-" * 80)
        for i, m in enumerate(output.analysis.review_milestones, 1):
            timing = f" ({m.typical_timing})" if m.typical_timing else ""
            print(f"\n{i}. {m.phase}{timing}")
            print(f"   Required: {m.required_documentation}")
            if m.citation_indices:
                print(f"   Cites: {m.citation_indices}")
        print()

    if output.analysis.open_questions:
        print("OPEN QUESTIONS (corpus could not answer)")
        print("-" * 80)
        for q in output.analysis.open_questions:
            print(f"  - {q}")
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
    parser = argparse.ArgumentParser(description="Run the Safety Screening Agent")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    configure_logging()
    protocol = PRESETS[args.preset]

    agent = SafetyAgent()
    output = await agent.analyze(protocol)

    if args.json:
        print(output.model_dump_json(indent=2))
    else:
        _print_output(output)


if __name__ == "__main__":
    asyncio.run(main())
