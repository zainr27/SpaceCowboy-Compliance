"""CLI for the Mission Integration Agent.

Usage:
    make mission-agent preset=plant_growth
    uv run python scripts/mission_agent.py --preset plant_growth
"""

from __future__ import annotations

import argparse
import asyncio

from scripts.hardware_agent import PRESETS

from apps.api.logging_config import configure_logging
from packages.agents.mission.agent import MissionAgent
from packages.agents.mission.schemas import MissionAgentOutput


def _print_output(output: MissionAgentOutput) -> None:
    print()
    print("=" * 80)
    print("MISSION INTEGRATION ANALYSIS")
    print("=" * 80)
    print()
    print(f"Summary: {output.analysis.summary}")
    print(
        f"Overall confidence: {output.analysis.overall_confidence:.2f}"
        f"  | Retrieval: {output.retrieval_chunks_used} chunks, {output.retrieval_ms}ms"
        f"  | Reasoning: {output.reasoning_ms}ms"
    )
    print()

    if output.analysis.recommended_facilities:
        print("RECOMMENDED FACILITIES")
        print("-" * 80)
        for i, f in enumerate(output.analysis.recommended_facilities, 1):
            print(f"\n{i}. {f.facility_name}")
            print(f"   Provider:  {f.provider}")
            print(f"   Rationale: {f.fit_rationale}")
            if f.constraints:
                print("   Constraints:")
                for c in f.constraints:
                    print(f"     - {c}")
            if f.citation_indices:
                print(f"   Cites: {f.citation_indices}")
    else:
        print("RECOMMENDED FACILITIES: none identified")
    print()

    if output.analysis.ascent_options:
        print("ASCENT OPTIONS")
        print("-" * 80)
        for i, a in enumerate(output.analysis.ascent_options, 1):
            print(f"\n{i}. {a.vehicle}")
            print(f"   Rationale: {a.rationale}")
            if a.constraints:
                print("   Constraints:")
                for c in a.constraints:
                    print(f"     - {c}")
            if a.citation_indices:
                print(f"   Cites: {a.citation_indices}")
        print()

    print("RESOURCE BUDGET")
    print("-" * 80)
    rb = output.analysis.resource_budget
    upmass = (
        f"{rb.upmass_estimate_kg} kg"
        if rb.upmass_estimate_kg is not None
        else "not estimable from sources"
    )
    downmass = (
        f"{rb.downmass_estimate_kg} kg"
        if rb.downmass_estimate_kg is not None
        else "not estimable from sources"
    )
    print(f"  Upmass:          {upmass}")
    print(f"  Downmass:        {downmass}")
    print(f"  Cold stowage:    {'required' if rb.requires_cold_stowage else 'not required'}")
    print(f"  Powered locker:  {'required' if rb.requires_powered_locker else 'not required'}")
    print(f"  Rationale: {rb.rationale}")
    if rb.citation_indices:
        print(f"  Cites: {rb.citation_indices}")
    print()

    print("CREW TIME")
    print("-" * 80)
    ct = output.analysis.crew_time
    hours = (
        f"{ct.total_hours_estimate} hours"
        if ct.total_hours_estimate is not None
        else "not estimable from sources"
    )
    print(f"  Estimate:        {hours}")
    print(f"  Interaction:     {ct.interaction_type}")
    print(f"  Rationale: {ct.rationale}")
    if ct.citation_indices:
        print(f"  Cites: {ct.citation_indices}")
    print()

    if output.analysis.timeline:
        print("TIMELINE MILESTONES")
        print("-" * 80)
        for i, m in enumerate(output.analysis.timeline, 1):
            timing = f" ({m.typical_timing})" if m.typical_timing else ""
            print(f"\n{i}. {m.name}{timing}")
            print(f"   Deliverables: {m.deliverables}")
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
        for cit in output.citations:
            page = f", p.{cit.page_number}" if cit.page_number else ""
            print(f"  [{cit.index}] {cit.title}{page}")
            print(f"      Score: {cit.relevance_score:.3f}  {cit.source_url}")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Mission Integration Agent")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    configure_logging()
    protocol = PRESETS[args.preset]

    agent = MissionAgent()
    output = await agent.analyze(protocol)

    if args.json:
        print(output.model_dump_json(indent=2))
    else:
        _print_output(output)


if __name__ == "__main__":
    asyncio.run(main())
