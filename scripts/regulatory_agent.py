"""CLI for the Regulatory Pathway Agent.

Usage:
    make reg-agent preset=cell_culture
    uv run python scripts/regulatory_agent.py --preset cell_culture
"""

from __future__ import annotations

import argparse
import asyncio

from scripts.hardware_agent import PRESETS

from apps.api.logging_config import configure_logging
from packages.agents.regulatory.agent import RegulatoryAgent
from packages.agents.regulatory.schemas import RegulatoryAgentOutput


def _print_output(output: RegulatoryAgentOutput) -> None:
    print()
    print("=" * 80)
    print("REGULATORY PATHWAY ANALYSIS")
    print("=" * 80)
    print()
    print(f"Summary: {output.analysis.summary}")
    print(
        f"Overall confidence: {output.analysis.overall_confidence:.2f}"
        f"  | Retrieval: {output.retrieval_chunks_used} chunks, {output.retrieval_ms}ms"
        f"  | Reasoning: {output.reasoning_ms}ms"
    )
    print()

    if output.analysis.applicable_frameworks:
        print("APPLICABLE FRAMEWORKS")
        print("-" * 80)
        for i, f in enumerate(output.analysis.applicable_frameworks, 1):
            print(f"\n{i}. [{f.applicability.upper()}] {f.framework}")
            print(f"   Rationale: {f.rationale}")
            if f.citation_indices:
                print(f"   Cites: {f.citation_indices}")
    else:
        print("APPLICABLE FRAMEWORKS: none identified")
    print()

    if output.analysis.compliance_requirements:
        print("COMPLIANCE REQUIREMENTS")
        print("-" * 80)
        for i, req in enumerate(output.analysis.compliance_requirements, 1):
            print(f"\n{i}. [{req.estimated_effort} effort] {req.framework}")
            print(f"   Requirement: {req.requirement}")
            print(f"   Rationale:   {req.rationale}")
            if req.citation_indices:
                print(f"   Cites: {req.citation_indices}")
        print()

    if output.analysis.review_processes:
        print("REVIEW PROCESSES")
        print("-" * 80)
        for i, r in enumerate(output.analysis.review_processes, 1):
            timing = f" ({r.typical_timeline})" if r.typical_timeline else ""
            print(f"\n{i}. {r.name}{timing}")
            print(f"   Authority:    {r.responsible_authority}")
            print(f"   Deliverables: {r.deliverables}")
            if r.citation_indices:
                print(f"   Cites: {r.citation_indices}")
        print()

    if output.analysis.open_questions:
        print("OPEN QUESTIONS (require external review)")
        print("-" * 80)
        for q in output.analysis.open_questions:
            print(f"  - {q}")
        print()

    if output.citations:
        print("CITATIONS")
        print("-" * 80)
        for cit in output.citations:
            page = f", p.{cit.page_number}" if cit.page_number else ""
            print(f"  [{cit.index}] {cit.title}{page}")
            print(f"      Score: {cit.relevance_score:.3f}  {cit.source_url}")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Regulatory Pathway Agent")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    configure_logging()
    protocol = PRESETS[args.preset]

    agent = RegulatoryAgent()
    output = await agent.analyze(protocol)

    if args.json:
        print(output.model_dump_json(indent=2))
    else:
        _print_output(output)


if __name__ == "__main__":
    asyncio.run(main())
