from __future__ import annotations

import time

import structlog

from packages.agents.base import (
    MultiQueryRetrievalResult,
    call_llm_structured,
    retrieve_multi_query,
)
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.safety.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.safety.schemas import (
    ResolvedCitation,
    SafetyAgentOutput,
    SafetyAnalysis,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class SafetyAgent:
    """Screens protocols for ISS safety review requirements.

    Pipeline:
    1. Decompose protocol into hazard / process / precedent queries
    2. Multi-query retrieval from KB using SAFETY profile
    3. Call LLM with system prompt + protocol + retrieved context
    4. Parse structured response, resolve citation indices
    """

    AGENT_NAME = "safety_screening_agent"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._kb = KnowledgeBase.for_agent(AgentProfile.SAFETY)

    async def analyze(
        self,
        protocol: ProtocolRequirements,
        retrieval_top_n: int = 8,
    ) -> SafetyAgentOutput:
        start = time.monotonic()
        logger.info(
            "safety_agent_start",
            organism=protocol.organism,
            biosafety_declared=protocol.biosafety_level,
        )

        queries = self._decompose_query(protocol)
        logger.info(
            "safety_agent_query_decomposition",
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
            logger.warning("safety_agent_no_retrieval_results")
            return self._empty_result(retrieval)

        analysis, llm_meta = await call_llm_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, retrieval.formatted_context),
            output_schema=SafetyAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, retrieval.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "safety_agent_complete",
            biosafety=analysis.biosafety_classification,
            hazards=len(analysis.hazards),
            containment_reqs=len(analysis.containment_requirements),
            milestones=len(analysis.review_milestones),
            open_questions=len(analysis.open_questions),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
        )

        return SafetyAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(retrieval.chunks),
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=llm_meta["duration_ms"],
        )

    def _decompose_query(self, protocol: ProtocolRequirements) -> list[str]:
        """Build orthogonal queries for safety-relevant retrieval.

        Three facets:
        1. Hazard — what are the specific safety concerns for this protocol?
        2. Process — what NASA review milestones apply?
        3. Precedent — how have similar experiments been classified?
        """
        queries: list[str] = []

        # Query 1: Hazard identification
        hazard_parts = ["safety hazard containment biosafety"]
        if protocol.organism:
            hazard_parts.append(f"{protocol.organism} biohazard")
        if protocol.biosafety_level:
            hazard_parts.append(f"{protocol.biosafety_level} containment requirements")
        desc_lower = protocol.description.lower()
        if "genetically modified" in desc_lower or "gmo" in desc_lower:
            hazard_parts.append("genetically modified organism containment")
        if "pathogen" in desc_lower or "infectious" in desc_lower:
            hazard_parts.append("pathogenic organism containment")
        if "chemical" in desc_lower or "solvent" in desc_lower or "fixative" in desc_lower:
            hazard_parts.append("chemical hazard toxic")
        if "pressure" in desc_lower or "sealed" in desc_lower:
            hazard_parts.append("pressure vessel safety")
        queries.append(" ".join(hazard_parts))

        # Query 2: NASA safety review process
        process_parts = [
            "NASA payload safety review process",
            "PSWG safety data package phase",
        ]
        if protocol.intent == "commercial":
            process_parts.append("commercial payload safety approval")
        queries.append(" ".join(process_parts))

        # Query 3: Precedent — conditional on organism/experiment type
        precedent_parts: list[str] = []
        if protocol.organism:
            precedent_parts.append(
                f"prior ISS experiment safety classification {protocol.organism}"
            )
        if "cell" in desc_lower:
            precedent_parts.append("cell culture biosafety ISS payload")
        if "plant" in desc_lower:
            precedent_parts.append("plant growth payload safety review")
        if precedent_parts:
            queries.append(" ".join(precedent_parts))

        return queries

    @staticmethod
    def _resolve_citations(
        analysis: SafetyAnalysis,
        kb_citations: list[Citation],
    ) -> list[ResolvedCitation]:
        used_indices: set[int] = set()
        for hazard in analysis.hazards:
            used_indices.update(hazard.citation_indices)
        for req in analysis.containment_requirements:
            used_indices.update(req.citation_indices)
        for milestone in analysis.review_milestones:
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
    def _empty_result(retrieval: MultiQueryRetrievalResult) -> SafetyAgentOutput:
        return SafetyAgentOutput(
            analysis=SafetyAnalysis(
                summary="No relevant safety information found in the knowledge base for this protocol.",
                biosafety_classification="non-biological",
                hazards=[],
                containment_requirements=[],
                review_milestones=[],
                open_questions=[
                    "The knowledge base did not return relevant safety content for this protocol."
                ],
                overall_confidence=0.0,
            ),
            citations=[],
            retrieval_chunks_used=0,
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=0,
        )
