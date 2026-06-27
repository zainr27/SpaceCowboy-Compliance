from __future__ import annotations

import time

import structlog

from packages.agents.base import (
    MultiQueryRetrievalResult,
    call_llm_structured,
    retrieve_multi_query,
)
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.microgravity.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.microgravity.schemas import (
    MicrogravityAgentOutput,
    MicrogravityAnalysis,
    ResolvedCitation,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class MicrogravityAgent:
    """Identifies protocol modifications needed for microgravity execution.

    Pipeline:
    1. Decompose protocol into 2-3 orthogonal queries (physics, biology, precedent)
    2. Multi-query retrieval from KB using MICROGRAVITY profile
    3. Call LLM with system prompt + protocol + retrieved context
    4. Parse structured response, resolve citation indices
    5. Return full MicrogravityAgentOutput
    """

    AGENT_NAME = "microgravity_adaptation_agent"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._kb = KnowledgeBase.for_agent(AgentProfile.MICROGRAVITY)

    async def analyze(
        self,
        protocol: ProtocolRequirements,
        retrieval_top_n: int = 8,
    ) -> MicrogravityAgentOutput:
        start = time.monotonic()
        logger.info(
            "microgravity_agent_start",
            organism=protocol.organism,
            duration_days=protocol.duration_days,
        )

        queries = self._decompose_query(protocol)
        logger.info(
            "microgravity_agent_query_decomposition",
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
            logger.warning("microgravity_agent_no_retrieval_results")
            return self._empty_result(retrieval)

        analysis, llm_meta = await call_llm_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, retrieval.formatted_context),
            output_schema=MicrogravityAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, retrieval.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "microgravity_agent_complete",
            modifications=len(analysis.modifications),
            behaviors=len(analysis.expected_behaviors),
            precedents=len(analysis.research_precedents),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
        )

        return MicrogravityAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(retrieval.chunks),
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=llm_meta["duration_ms"],
        )

    def _decompose_query(self, protocol: ProtocolRequirements) -> list[str]:
        """Build orthogonal queries for microgravity-relevant retrieval.

        Three facets:
        1. Physics — how does microgravity affect fluids/gases/forces relevant to this protocol?
        2. Biology — how do living systems respond to microgravity in this experiment's context?
        3. Precedent — what similar experiments have flown and what did they find?
        """
        queries: list[str] = []

        # Query 1: Physics — fluids, gases, sedimentation, convection
        physics_parts = [
            "microgravity fluid behavior convection diffusion",
            protocol.description,
        ]
        if protocol.requires_media_exchange:
            physics_parts.append("liquid handling capillary forces")
        if protocol.co2_pct is not None:
            physics_parts.append("gas exchange atmospheric boundary layer")
        queries.append(" ".join(physics_parts))

        # Query 2: Biology — organism-specific microgravity response
        bio_parts = ["microgravity biological response"]
        if protocol.organism:
            bio_parts.append(protocol.organism)
        else:
            bio_parts.append("cellular plant response")
        if "plant" in protocol.description.lower() or (
            protocol.organism and "plant" in protocol.organism.lower()
        ):
            bio_parts.append("gravitropism phototropism root growth")
        elif "cell" in protocol.description.lower() or (
            protocol.organism and "cell" in protocol.organism.lower()
        ):
            bio_parts.append("cell culture cytoskeleton gene expression")
        queries.append(" ".join(bio_parts))

        # Query 3: Precedent — only if there's specific organism or technique signal
        precedent_parts: list[str] = []
        if protocol.organism:
            precedent_parts.append(f"ISS spaceflight experiment {protocol.organism}")
        if "crystallization" in protocol.description.lower():
            precedent_parts.append("protein crystallization microgravity precedent")
        if protocol.requires_imaging:
            precedent_parts.append("microscopy imaging spaceflight")
        if precedent_parts:
            queries.append(" ".join(precedent_parts))

        return queries

    @staticmethod
    def _resolve_citations(
        analysis: MicrogravityAnalysis,
        kb_citations: list[Citation],
    ) -> list[ResolvedCitation]:
        """Map citation indices used across all parts of the analysis."""
        used_indices: set[int] = set()
        for mod in analysis.modifications:
            used_indices.update(mod.citation_indices)
        for behavior in analysis.expected_behaviors:
            used_indices.update(behavior.citation_indices)
        for precedent in analysis.research_precedents:
            used_indices.update(precedent.citation_indices)

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
    def _empty_result(retrieval: MultiQueryRetrievalResult) -> MicrogravityAgentOutput:
        return MicrogravityAgentOutput(
            analysis=MicrogravityAnalysis(
                summary="No relevant microgravity research found in the knowledge base for this protocol.",
                modifications=[],
                expected_behaviors=[],
                research_precedents=[],
                overall_confidence=0.0,
            ),
            citations=[],
            retrieval_chunks_used=0,
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=0,
        )
