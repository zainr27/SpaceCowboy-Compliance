from __future__ import annotations

import time

import structlog

from packages.agents.base import (
    MultiQueryRetrievalResult,
    call_claude_structured,
    retrieve_multi_query,
)
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.mission.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.mission.schemas import (
    CrewTimeEstimate,
    MissionAgentOutput,
    MissionAnalysis,
    ResolvedCitation,
    ResourceBudget,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class MissionAgent:
    """Maps protocols to ISS mission integration logistics.

    Pipeline:
    1. Decompose protocol into facility / logistics / timeline queries
    2. Multi-query retrieval via MISSION profile
    3. Call LLM with system prompt + protocol + retrieved context
    4. Parse structured response, resolve citation indices
    """

    AGENT_NAME = "mission_integration_agent"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._kb = KnowledgeBase.for_agent(AgentProfile.MISSION)

    async def analyze(
        self,
        protocol: ProtocolRequirements,
        retrieval_top_n: int = 8,
    ) -> MissionAgentOutput:
        start = time.monotonic()
        logger.info(
            "mission_agent_start",
            organism=protocol.organism,
            duration_days=protocol.duration_days,
            requires_sample_return=protocol.requires_sample_return,
        )

        queries = self._decompose_query(protocol)
        logger.info(
            "mission_agent_query_decomposition",
            query_count=len(queries),
            queries=queries,
        )

        retrieval = await retrieve_multi_query(
            kb=self._kb,
            queries=queries,
            per_query_k=10,
            final_top_n=retrieval_top_n,
        )

        if not retrieval.chunks:
            logger.warning("mission_agent_no_retrieval_results")
            return self._empty_result(retrieval)

        analysis, claude_meta = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, retrieval.formatted_context),
            output_schema=MissionAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, retrieval.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "mission_agent_complete",
            facilities=len(analysis.recommended_facilities),
            ascent_options=len(analysis.ascent_options),
            timeline_milestones=len(analysis.timeline),
            open_questions=len(analysis.open_questions),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
        )

        return MissionAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(retrieval.chunks),
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=claude_meta["duration_ms"],
        )

    def _decompose_query(self, protocol: ProtocolRequirements) -> list[str]:
        """Build orthogonal queries for mission integration retrieval.

        Three facets:
        1. Facility — what on-station facility hosts this type of experiment?
        2. Logistics — what resources (mass, stowage, crew) does this need?
        3. Timeline — what's the path from proposal to flight?
        """
        queries: list[str] = []

        # Query 1: Facility — on-station hardware that hosts this kind of experiment
        facility_parts = ["ISS National Lab facility on-station experiment"]
        if protocol.organism:
            facility_parts.append(protocol.organism)
        desc_lower = protocol.description.lower()
        if "cell" in desc_lower or "tissue" in desc_lower:
            facility_parts.append("cell culture incubator facility")
        if "plant" in desc_lower:
            facility_parts.append("plant growth chamber facility")
        if "crystallization" in desc_lower or "crystal" in desc_lower:
            facility_parts.append("protein crystallization facility")
        if protocol.intent == "commercial":
            facility_parts.append("commercial service provider")
        queries.append(" ".join(facility_parts))

        # Query 2: Logistics — ascent vehicles, resources, crew time
        logistics_parts = ["ISS payload upmass cold stowage powered locker"]
        if protocol.requires_sample_return:
            logistics_parts.append("sample return downmass Dragon")
        if protocol.duration_days and protocol.duration_days > 14:
            logistics_parts.append(f"long duration {protocol.duration_days} days")
        queries.append(" ".join(logistics_parts))

        # Query 3: Timeline — proposal-to-flight pathway
        timeline_parts = [
            "ISS National Lab proposal solicitation timeline flight",
            "Implementation Partner integration milestone",
        ]
        if protocol.intent == "commercial":
            timeline_parts.append("commercial payload manifest")
        queries.append(" ".join(timeline_parts))

        return queries

    @staticmethod
    def _resolve_citations(
        analysis: MissionAnalysis,
        kb_citations: list[Citation],
    ) -> list[ResolvedCitation]:
        used_indices: set[int] = set()
        for facility in analysis.recommended_facilities:
            used_indices.update(facility.citation_indices)
        for ascent in analysis.ascent_options:
            used_indices.update(ascent.citation_indices)
        used_indices.update(analysis.resource_budget.citation_indices)
        used_indices.update(analysis.crew_time.citation_indices)
        for milestone in analysis.timeline:
            used_indices.update(milestone.citation_indices)

        resolved: list[ResolvedCitation] = []
        for idx in sorted(used_indices):
            list_idx = idx - 1
            if 0 <= list_idx < len(kb_citations):
                c = kb_citations[list_idx]
                resolved.append(
                    ResolvedCitation(
                        index=idx,
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        title=c.title,
                        source_url=c.source_url,
                        page_number=c.page_number,
                        section_path=c.section_path,
                        relevance_score=c.relevance_score,
                    )
                )
        return resolved

    @staticmethod
    def _empty_result(retrieval: MultiQueryRetrievalResult) -> MissionAgentOutput:
        return MissionAgentOutput(
            analysis=MissionAnalysis(
                summary="No relevant mission integration content found for this protocol.",
                recommended_facilities=[],
                ascent_options=[],
                resource_budget=ResourceBudget(
                    upmass_estimate_kg=None,
                    downmass_estimate_kg=None,
                    requires_cold_stowage=False,
                    requires_powered_locker=False,
                    rationale="Retrieved sources did not contain sufficient information to estimate resources.",
                ),
                crew_time=CrewTimeEstimate(
                    total_hours_estimate=None,
                    interaction_type="unspecified",
                    rationale="Retrieved sources did not contain sufficient information to estimate crew time.",
                ),
                timeline=[],
                open_questions=[
                    "The knowledge base did not return relevant mission integration content for this protocol."
                ],
                overall_confidence=0.0,
            ),
            citations=[],
            retrieval_chunks_used=0,
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=0,
        )
