from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Protocol

import structlog

from packages.agents.base import call_llm_structured
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.orchestrator.executor import ExecutionResults
from packages.orchestrator.schemas import (
    AgentName,
    ConfidenceProfile,
    CrossAgentInsight,
    ExecutiveSummary,
    OrchestratorReport,
    UnifiedCitation,
)

logger = structlog.get_logger(__name__)


class Synthesizer(Protocol):
    """Protocol for orchestrator synthesizers."""

    name: str

    async def synthesize(
        self,
        protocol: ProtocolRequirements,
        results: ExecutionResults,
        total_duration_ms: int,
        executor_name: str,
    ) -> OrchestratorReport: ...


class RuleBasedSynthesizer:
    """Deterministic composition of sub-agent outputs.

    Builds the unified report by:
    1. Deduplicating citations across all sub-agents
    2. Computing aggregate confidence
    3. Detecting cross-agent insights via rule-based checks
    4. Aggregating and deduplicating open questions
    5. Generating an executive summary via a single targeted LLM call
    """

    name = "rule_based"
    SUMMARY_MODEL = "gpt-4o"

    async def synthesize(
        self,
        protocol: ProtocolRequirements,
        results: ExecutionResults,
        total_duration_ms: int,
        executor_name: str,
    ) -> OrchestratorReport:
        logger.info("rule_based_synth_start")

        unified_citations = self._build_unified_citations(results)
        confidence = self._compute_confidence(results)
        insights = self._detect_insights(results)
        open_questions = self._aggregate_open_questions(results)
        executive_summary = await self._generate_executive_summary(protocol, results, confidence)

        logger.info(
            "rule_based_synth_complete",
            unified_citations=len(unified_citations),
            cross_agent_insights=len(insights),
            open_questions=len(open_questions),
        )

        return OrchestratorReport(
            protocol=protocol,
            total_duration_ms=total_duration_ms,
            executor=executor_name,  # type: ignore[arg-type]
            synthesizer=self.name,  # type: ignore[arg-type]
            agent_executions=results.executions,
            executive_summary=executive_summary,
            confidence=confidence,
            hardware=results.hardware,
            microgravity=results.microgravity,
            safety=results.safety,
            mission=results.mission,
            regulatory=results.regulatory,
            cross_agent_insights=insights,
            citations=unified_citations,
            open_questions=open_questions,
        )

    @staticmethod
    def _build_unified_citations(results: ExecutionResults) -> list[UnifiedCitation]:
        """Deduplicate citations across all sub-agents by chunk_id."""
        # Intermediate: keyed by chunk_id str, value is (UnifiedCitation-in-progress, best_score)
        partial: dict[str, UnifiedCitation] = {}

        all_agent_citations: list[tuple[AgentName, list]] = [  # type: ignore[type-arg]
            ("hardware", results.hardware.citations if results.hardware else []),
            ("microgravity", results.microgravity.citations if results.microgravity else []),
            ("safety", results.safety.citations if results.safety else []),
            ("mission", results.mission.citations if results.mission else []),
            ("regulatory", results.regulatory.citations if results.regulatory else []),
        ]

        for agent_name, citations in all_agent_citations:
            for c in citations:
                key = str(c.chunk_id)
                if key not in partial:
                    partial[key] = UnifiedCitation(
                        unified_index=0,  # assigned later
                        chunk_id=uuid.UUID(str(c.chunk_id)),
                        document_id=uuid.UUID(str(c.document_id)),
                        title=c.title,
                        source_url=c.source_url,
                        page_number=c.page_number,
                        section_path=c.section_path,
                        relevance_score=c.relevance_score,
                        cited_by=[agent_name],
                    )
                else:
                    existing = partial[key]
                    if agent_name not in existing.cited_by:
                        existing.cited_by.append(agent_name)
                    if c.relevance_score > existing.relevance_score:
                        existing.relevance_score = c.relevance_score

        sorted_citations = sorted(
            partial.values(),
            key=lambda uc: uc.relevance_score,
            reverse=True,
        )

        for i, uc in enumerate(sorted_citations, start=1):
            uc.unified_index = i

        return sorted_citations

    @staticmethod
    def _compute_confidence(results: ExecutionResults) -> ConfidenceProfile:
        """Average confidence across successful agents."""
        scores: dict[str, float] = {}
        if results.hardware:
            scores["hardware"] = results.hardware.analysis.overall_confidence
        if results.microgravity:
            scores["microgravity"] = results.microgravity.analysis.overall_confidence
        if results.safety:
            scores["safety"] = results.safety.analysis.overall_confidence
        if results.mission:
            scores["mission"] = results.mission.analysis.overall_confidence
        if results.regulatory:
            scores["regulatory"] = results.regulatory.analysis.overall_confidence

        overall = (sum(scores.values()) / len(scores)) if scores else 0.0

        return ConfidenceProfile(
            hardware=scores.get("hardware"),
            microgravity=scores.get("microgravity"),
            safety=scores.get("safety"),
            mission=scores.get("mission"),
            regulatory=scores.get("regulatory"),
            overall=overall,
        )

    @staticmethod
    def _detect_insights(results: ExecutionResults) -> list[CrossAgentInsight]:
        """Rule-based detection of cross-agent insights."""
        insights: list[CrossAgentInsight] = []

        # Rule 1: Corpus gap — open questions with thematic overlap across agents
        all_open: list[tuple[AgentName, str]] = []
        if results.safety:
            for q in results.safety.analysis.open_questions:
                all_open.append(("safety", q))
        if results.mission:
            for q in results.mission.analysis.open_questions:
                all_open.append(("mission", q))
        if results.regulatory:
            for q in results.regulatory.analysis.open_questions:
                all_open.append(("regulatory", q))

        themes: dict[str, list[AgentName]] = defaultdict(list)
        for agent, q in all_open:
            q_lower = q.lower()
            for theme_keyword in [
                "itar",
                "fda",
                "casis",
                "ip ",
                "data",
                "cold stowage",
                "media exchange",
            ]:
                if theme_keyword in q_lower and agent not in themes[theme_keyword]:
                    themes[theme_keyword].append(agent)

        for theme, agents in themes.items():
            if len(agents) >= 2:
                insights.append(
                    CrossAgentInsight(
                        kind="corpus_gap",
                        description=(
                            f"Multiple agents ({', '.join(agents)}) surfaced open questions related to "
                            f"'{theme}'. This indicates a corpus gap that affects multiple analysis dimensions."
                        ),
                        involved_agents=agents,
                    )
                )

        # Rule 2: Consistency check — safety BSL vs hardware containment language
        if results.safety and results.hardware:
            bsl = results.safety.analysis.biosafety_classification
            if bsl in ("BSL-2", "BSL-3", "BSL-4"):
                hw_text = " ".join(
                    h.rationale + " " + " ".join(h.constraints)
                    for h in results.hardware.analysis.recommended_hardware
                ).lower()
                if "containment" not in hw_text and "hrl" not in hw_text:
                    insights.append(
                        CrossAgentInsight(
                            kind="tension",
                            description=(
                                f"Safety analysis classified protocol as {bsl} but hardware recommendations "
                                f"do not explicitly address containment requirements. Verify recommended "
                                f"hardware meets BSL containment standards before flight."
                            ),
                            involved_agents=["safety", "hardware"],
                        )
                    )

        # Rule 3: Compound risk — high-severity hazards + critical microgravity mods
        if results.safety and results.microgravity:
            critical_hazards = [
                h
                for h in results.safety.analysis.hazards
                if h.severity in ("catastrophic", "critical")
            ]
            critical_mods = [
                m for m in results.microgravity.analysis.modifications if m.severity == "critical"
            ]
            if critical_hazards and critical_mods:
                insights.append(
                    CrossAgentInsight(
                        kind="compound_risk",
                        description=(
                            f"Protocol has {len(critical_hazards)} high-severity safety hazard(s) AND "
                            f"{len(critical_mods)} critical microgravity modification(s). Both must be "
                            f"addressed before flight; either alone could disqualify the protocol."
                        ),
                        involved_agents=["safety", "microgravity"],
                    )
                )

        return insights

    @staticmethod
    def _aggregate_open_questions(results: ExecutionResults) -> list[str]:
        """Aggregate open questions across agents, light deduplication."""
        all_questions: list[str] = []
        if results.safety:
            all_questions.extend(results.safety.analysis.open_questions)
        if results.mission:
            all_questions.extend(results.mission.analysis.open_questions)
        if results.regulatory:
            all_questions.extend(results.regulatory.analysis.open_questions)

        seen: set[str] = set()
        unique: list[str] = []
        for q in all_questions:
            key = q.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(q)
        return unique

    async def _generate_executive_summary(
        self,
        protocol: ProtocolRequirements,
        results: ExecutionResults,
        confidence: ConfidenceProfile,
    ) -> ExecutiveSummary:
        """Generate executive summary via a single targeted LLM call."""
        system_prompt = """You are writing the executive summary section of a structured protocol analysis report. Your input is a set of structured findings from five sub-agents. Your output is a JSON object matching the ExecutiveSummary schema.

CONSTRAINTS:
1. Use ONLY information present in the structured findings. Do not introduce new facts.
2. The headline is one sentence summarizing the overall analysis posture.
3. facility_recommendation, primary_microgravity_concern, and mission_pathway should be one-sentence statements drawn from the sub-agent outputs. Set to None if the corresponding sub-agent didn't run or didn't produce a clear result.
4. biosafety_classification must come from the safety agent's classification. If safety didn't run, use "unknown".
5. regulatory_floor describes the universal regulatory requirements (typically "NASA payload safety review required"). If regulatory didn't run, describe what's known.
6. Be specific: name facilities, list concerns, cite numbers when they exist in the findings.

Return JSON only."""

        findings = self._format_findings_for_summary(results)
        user_prompt = f"""Protocol intent: {protocol.intent}
Protocol description: {protocol.description[:500]}

Aggregate confidence: {confidence.overall:.2f}

Structured findings from sub-agents:
{findings}

Generate the executive summary."""

        try:
            summary, _ = await call_llm_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=ExecutiveSummary,
                model=self.SUMMARY_MODEL,
                max_tokens=1024,
                temperature=0.0,
            )
            return summary
        except Exception:
            logger.exception("executive_summary_generation_failed")
            return self._fallback_summary(results)

    @staticmethod
    def _format_findings_for_summary(results: ExecutionResults) -> str:
        """Compact structured representation of each agent's top finding."""
        sections: list[str] = []

        if results.hardware:
            hw = results.hardware.analysis
            top_hw = hw.recommended_hardware[0] if hw.recommended_hardware else None
            sections.append(
                f"HARDWARE (conf={hw.overall_confidence:.2f}):\n"
                f"  top_facility: {top_hw.name if top_hw else 'none'}\n"
                f"  fit_score: {top_hw.fit_score if top_hw else 'n/a'}\n"
                f"  gaps: {len(hw.gaps)}"
            )

        if results.microgravity:
            mg = results.microgravity.analysis
            critical_mods = [m for m in mg.modifications if m.severity == "critical"]
            sections.append(
                f"MICROGRAVITY (conf={mg.overall_confidence:.2f}):\n"
                f"  total_modifications: {len(mg.modifications)}\n"
                f"  critical_modifications: {len(critical_mods)}\n"
                f"  top_aspect: {mg.modifications[0].aspect if mg.modifications else 'none'}"
            )

        if results.safety:
            sa = results.safety.analysis
            sections.append(
                f"SAFETY (conf={sa.overall_confidence:.2f}):\n"
                f"  biosafety: {sa.biosafety_classification}\n"
                f"  hazards: {len(sa.hazards)}\n"
                f"  review_milestones: {len(sa.review_milestones)}"
            )

        if results.mission:
            mi = results.mission.analysis
            top_fac = mi.recommended_facilities[0] if mi.recommended_facilities else None
            top_asc = mi.ascent_options[0] if mi.ascent_options else None
            sections.append(
                f"MISSION (conf={mi.overall_confidence:.2f}):\n"
                f"  top_facility: {top_fac.facility_name if top_fac else 'none'}\n"
                f"  ascent: {top_asc.vehicle if top_asc else 'none'}\n"
                f"  cold_stowage: {mi.resource_budget.requires_cold_stowage}\n"
                f"  crew_interaction: {mi.crew_time.interaction_type}"
            )

        if results.regulatory:
            rg = results.regulatory.analysis
            required = [
                f.framework for f in rg.applicable_frameworks if f.applicability == "required"
            ]
            sections.append(
                f"REGULATORY (conf={rg.overall_confidence:.2f}):\n"
                f"  required_frameworks: {required}\n"
                f"  compliance_requirements: {len(rg.compliance_requirements)}\n"
                f"  open_questions: {len(rg.open_questions)}"
            )

        return "\n\n".join(sections) if sections else "(no agent results)"

    @staticmethod
    def _fallback_summary(results: ExecutionResults) -> ExecutiveSummary:
        """Deterministic fallback if the LLM summary call fails."""
        bsl = "unknown"
        if results.safety:
            bsl = results.safety.analysis.biosafety_classification

        facility = None
        if results.mission and results.mission.analysis.recommended_facilities:
            facility = (
                f"Recommended facility: "
                f"{results.mission.analysis.recommended_facilities[0].facility_name}"
            )
        elif results.hardware and results.hardware.analysis.recommended_hardware:
            facility = (
                f"Recommended hardware: {results.hardware.analysis.recommended_hardware[0].name}"
            )

        return ExecutiveSummary(
            headline=(
                f"Protocol analysis completed across {results.succeeded_count} of 5 sub-agents."
            ),
            facility_recommendation=facility,
            primary_microgravity_concern=None,
            biosafety_classification=bsl,
            mission_pathway=None,
            regulatory_floor="NASA payload safety review required for all ISS payloads.",
        )


class LLMMediatedSynthesizer:
    """Stub for a future LLM-mediated synthesizer.

    Rather than rule-based composition + targeted summary call, this would
    pass all sub-agent outputs to a final LLM call that produces both the
    summary AND the cross-agent insights as integrated reasoning.

    Interface matches RuleBasedSynthesizer.
    """

    name = "llm_mediated"

    async def synthesize(
        self,
        protocol: ProtocolRequirements,
        results: ExecutionResults,
        total_duration_ms: int,
        executor_name: str,
    ) -> OrchestratorReport:
        raise NotImplementedError(
            "LLMMediatedSynthesizer is reserved for future implementation. "
            "Use RuleBasedSynthesizer for now."
        )
