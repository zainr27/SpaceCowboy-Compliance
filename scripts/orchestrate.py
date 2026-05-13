"""CLI for the Spacebio Protocol Orchestrator.

Usage:
    make orchestrate preset=plant_growth
    uv run python scripts/orchestrate.py --preset cell_culture --json
"""

from __future__ import annotations

import argparse
import asyncio

from scripts.hardware_agent import PRESETS

from apps.api.logging_config import configure_logging
from packages.orchestrator.orchestrator import Orchestrator
from packages.orchestrator.schemas import OrchestratorReport


def _header(title: str, width: int = 80) -> str:
    return "\n" + "=" * width + f"\n{title}\n" + "=" * width


def _subheader(title: str, width: int = 80) -> str:
    return "\n" + "-" * width + f"\n{title}\n" + "-" * width


def _confidence_bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def _print_report(report: OrchestratorReport) -> None:
    p = report.protocol

    print(_header("SPACEBIO-TRANSLATOR | PROTOCOL ANALYSIS REPORT"))
    print()
    print(f"  Protocol intent: {p.intent}")
    if p.organism:
        print(f"  Organism:        {p.organism}")
    if p.duration_days:
        print(f"  Duration:        {p.duration_days} days")
    if p.biosafety_level:
        print(f"  Declared BSL:    {p.biosafety_level}")
    print()
    print(f"  Description: {p.description[:200]}{'...' if len(p.description) > 200 else ''}")
    print()
    print(f"  Total runtime:   {report.total_duration_ms}ms")
    print(f"  Executor:        {report.executor}")
    print(f"  Synthesizer:     {report.synthesizer}")
    succeeded = sum(1 for e in report.agent_executions if e.succeeded)
    print(f"  Agents:          {succeeded}/5 succeeded")

    print(_header("CONFIDENCE PROFILE"))
    c = report.confidence
    print(f"  Overall:       {c.overall:.2f}  {_confidence_bar(c.overall)}")
    if c.hardware is not None:
        print(f"  Hardware:      {c.hardware:.2f}  {_confidence_bar(c.hardware)}")
    if c.microgravity is not None:
        print(f"  Microgravity:  {c.microgravity:.2f}  {_confidence_bar(c.microgravity)}")
    if c.safety is not None:
        print(f"  Safety:        {c.safety:.2f}  {_confidence_bar(c.safety)}")
    if c.mission is not None:
        print(f"  Mission:       {c.mission:.2f}  {_confidence_bar(c.mission)}")
    if c.regulatory is not None:
        print(f"  Regulatory:    {c.regulatory:.2f}  {_confidence_bar(c.regulatory)}")

    print(_header("EXECUTIVE SUMMARY"))
    es = report.executive_summary
    print(f"  {es.headline}")
    print()
    print(f"  Biosafety:               {es.biosafety_classification}")
    if es.facility_recommendation:
        print(f"  Facility:                {es.facility_recommendation}")
    if es.primary_microgravity_concern:
        print(f"  Microgravity concern:    {es.primary_microgravity_concern}")
    if es.mission_pathway:
        print(f"  Mission pathway:         {es.mission_pathway}")
    print(f"  Regulatory floor:        {es.regulatory_floor}")

    if report.cross_agent_insights:
        print(_header("CROSS-AGENT INSIGHTS"))
        for i, ins in enumerate(report.cross_agent_insights, 1):
            print(f"\n  {i}. [{ins.kind.upper()}] (agents: {', '.join(ins.involved_agents)})")
            print(f"     {ins.description}")

    print(_header("PER-AGENT FINDINGS"))

    if report.hardware:
        h = report.hardware.analysis
        print(_subheader("HARDWARE COMPATIBILITY"))
        print(f"  Summary:              {h.summary}")
        if h.recommended_hardware:
            top = h.recommended_hardware[0]
            print(f"  Top recommendation:   {top.name} (fit_score={top.fit_score:.2f})")
        if h.gaps:
            print(f"  Gaps:                 {len(h.gaps)} identified")

    if report.microgravity:
        m = report.microgravity.analysis
        print(_subheader("MICROGRAVITY ADAPTATION"))
        print(f"  Summary:              {m.summary}")
        if m.modifications:
            crit = sum(1 for x in m.modifications if x.severity == "critical")
            print(f"  Modifications:        {len(m.modifications)} total, {crit} critical")
        if m.research_precedents:
            print(f"  Research precedents:  {len(m.research_precedents)}")

    if report.safety:
        s = report.safety.analysis
        print(_subheader("SAFETY SCREENING"))
        print(f"  Summary:              {s.summary}")
        print(f"  Biosafety:            {s.biosafety_classification}")
        if s.hazards:
            print(f"  Hazards:              {len(s.hazards)} identified")
        if s.review_milestones:
            print(f"  Review milestones:    {len(s.review_milestones)}")

    if report.mission:
        mi = report.mission.analysis
        print(_subheader("MISSION INTEGRATION"))
        print(f"  Summary:              {mi.summary}")
        if mi.recommended_facilities:
            top_fac = mi.recommended_facilities[0]
            print(f"  Top facility:         {top_fac.facility_name} ({top_fac.provider})")
        if mi.ascent_options:
            print(f"  Ascent:               {mi.ascent_options[0].vehicle}")
        print(f"  Cold stowage:         {mi.resource_budget.requires_cold_stowage}")
        print(f"  Crew interaction:     {mi.crew_time.interaction_type}")

    if report.regulatory:
        r = report.regulatory.analysis
        print(_subheader("REGULATORY PATHWAY"))
        print(f"  Summary:              {r.summary}")
        required = [f.framework for f in r.applicable_frameworks if f.applicability == "required"]
        if required:
            print(f"  Required frameworks:  {', '.join(required)}")
        if r.compliance_requirements:
            print(f"  Requirements:         {len(r.compliance_requirements)}")

    failed = [e for e in report.agent_executions if not e.succeeded]
    if failed:
        print(_header("FAILED AGENTS"))
        for e in failed:
            print(f"  {e.agent}: {e.error}")

    if report.open_questions:
        print(_header("OPEN QUESTIONS (require external review)"))
        for i, q in enumerate(report.open_questions, 1):
            print(f"  {i}. {q}")

    if report.citations:
        print(_header(f"CITATIONS ({len(report.citations)} unique sources)"))
        for cit in report.citations:
            page = f", p.{cit.page_number}" if cit.page_number else ""
            cited_by = ", ".join(cit.cited_by)
            print(f"\n  [{cit.unified_index}] {cit.title}{page}")
            print(f"      Cited by: {cited_by}")
            print(f"      Score:    {cit.relevance_score:.3f}")
            print(f"      URL:      {cit.source_url}")
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Spacebio Protocol Orchestrator")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), required=True)
    parser.add_argument(
        "--json", action="store_true", help="Emit raw JSON instead of pretty output"
    )
    args = parser.parse_args()

    configure_logging()
    protocol = PRESETS[args.preset]

    orch = Orchestrator()
    report = await orch.analyze(protocol)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        _print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
