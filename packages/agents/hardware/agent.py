from __future__ import annotations

import time

import structlog

from packages.agents.base import (
    MultiQueryRetrievalResult,
    call_claude_structured,
    retrieve_multi_query,
)
from packages.agents.hardware.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.hardware.schemas import (
    HardwareAgentOutput,
    HardwareAnalysis,
    ProtocolRequirements,
    ResolvedCitation,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class HardwareAgent:
    """Maps experimental protocols to compatible ISS hardware.

    Pipeline:
    1. Decompose protocol into orthogonal retrieval queries
    2. Parallel multi-query retrieval, merge by best score
    3. Call LLM with system prompt + protocol + merged context
    4. Parse structured response, resolve citation indices to chunk metadata
    5. Return complete HardwareAgentOutput
    """

    AGENT_NAME = "hardware_compatibility_agent"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._kb = KnowledgeBase.for_agent(AgentProfile.HARDWARE)

    async def analyze(
        self,
        protocol: ProtocolRequirements,
        retrieval_top_n: int = 8,
    ) -> HardwareAgentOutput:
        """Run the full hardware compatibility analysis."""
        start = time.monotonic()
        logger.info(
            "hardware_agent_start",
            organism=protocol.organism,
            duration_days=protocol.duration_days,
        )

        queries = self._decompose_query(protocol)
        logger.info(
            "hardware_agent_query_decomposition",
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
            logger.warning("hardware_agent_no_retrieval_results")
            return self._empty_result(retrieval)

        analysis, claude_meta = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, retrieval.formatted_context),
            output_schema=HardwareAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, retrieval.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "hardware_agent_complete",
            recommendations=len(analysis.recommended_hardware),
            gaps=len(analysis.gaps),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
            queries_used=queries,
        )

        return HardwareAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(retrieval.chunks),
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=claude_meta["duration_ms"],
        )

    def _decompose_query(self, protocol: ProtocolRequirements) -> list[str]:
        """Build 2-3 orthogonal queries targeting different facets of the protocol.

        Query 1 (always): capability — what kind of hardware fits this experiment type.
        Query 2 (if env signal): operating conditions (temp, CO2, humidity, biosafety).
        Query 3 (if op signal): specific operations required (imaging, media exchange, etc).
        """
        queries: list[str] = []

        # Query 1: Capability — always present
        capability_parts = [protocol.description]
        if protocol.organism:
            capability_parts.append(protocol.organism)
        if protocol.intent == "commercial":
            capability_parts.append("manufacturing production")
        elif protocol.intent == "clinical_pathway":
            capability_parts.append("therapeutic clinical")
        queries.append(" ".join(capability_parts))

        # Query 2: Environmental — only if there's real signal
        env_parts = ["ISS hardware operating conditions"]
        if protocol.temperature_c is not None:
            env_parts.append(f"temperature {protocol.temperature_c}C")
        if protocol.humidity_pct is not None:
            env_parts.append(f"humidity {protocol.humidity_pct}%")
        if protocol.co2_pct is not None:
            env_parts.append(f"CO2 {protocol.co2_pct}%")
        if protocol.light_required:
            env_parts.append("lighting illumination")
        if protocol.biosafety_level:
            env_parts.append(f"biosafety {protocol.biosafety_level} containment")
        if len(env_parts) > 1:
            queries.append(" ".join(env_parts))

        # Query 3: Operational — only if the protocol needs specific operations
        op_parts = []
        if protocol.requires_imaging:
            op_parts.append("imaging microscopy video camera")
        if protocol.requires_media_exchange:
            op_parts.append("media exchange perfusion automated")
        if protocol.requires_sample_return:
            op_parts.append("sample return cold stowage downmass")
        if protocol.duration_days and protocol.duration_days > 14:
            op_parts.append(f"long duration {protocol.duration_days} days")
        if op_parts:
            queries.append("ISS hardware " + " ".join(op_parts))

        return queries

    @staticmethod
    def _resolve_citations(
        analysis: HardwareAnalysis,
        kb_citations: list[Citation],
    ) -> list[ResolvedCitation]:
        """Map [N] citation indices from the analysis back to chunk metadata."""
        used_indices: set[int] = set()
        for match in analysis.recommended_hardware:
            used_indices.update(match.citation_indices)

        resolved: list[ResolvedCitation] = []
        for idx in sorted(used_indices):
            list_idx = idx - 1  # prompt is 1-indexed, list is 0-indexed
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
    def _empty_result(retrieval: MultiQueryRetrievalResult) -> HardwareAgentOutput:
        """Graceful empty result when retrieval found nothing."""
        return HardwareAgentOutput(
            analysis=HardwareAnalysis(
                summary="No relevant hardware information found in the knowledge base for this protocol.",
                recommended_hardware=[],
                gaps=[],
                overall_confidence=0.0,
            ),
            citations=[],
            retrieval_chunks_used=0,
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=0,
        )
