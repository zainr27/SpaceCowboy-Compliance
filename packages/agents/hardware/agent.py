from __future__ import annotations

import time

import structlog

from packages.agents.base import call_claude_structured
from packages.agents.hardware.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.hardware.schemas import (
    HardwareAgentOutput,
    HardwareAnalysis,
    ProtocolRequirements,
    ResolvedCitation,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase, SearchResult
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class HardwareAgent:
    """Maps experimental protocols to compatible ISS hardware.

    Pipeline:
    1. Retrieve relevant hardware-focused content from KB (HARDWARE profile)
    2. Format context with citation indices
    3. Call Claude with system prompt + protocol + context
    4. Parse structured response, resolve citation indices to chunk metadata
    5. Return complete HardwareAgentOutput
    """

    AGENT_NAME = "hardware_compatibility_agent"
    DEFAULT_MODEL = "claude-sonnet-4-5"

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

        retrieval_query = self._build_retrieval_query(protocol)
        search_result = await self._kb.search(
            query=retrieval_query,
            top_n=retrieval_top_n,
        )

        if not search_result.chunks:
            logger.warning("hardware_agent_no_retrieval_results")
            return self._empty_result(search_result)

        analysis, claude_meta = await call_claude_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, search_result.formatted_context),
            output_schema=HardwareAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, search_result.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "hardware_agent_complete",
            recommendations=len(analysis.recommended_hardware),
            gaps=len(analysis.gaps),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
        )

        return HardwareAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(search_result.chunks),
            retrieval_ms=search_result.retrieval_ms,
            reasoning_ms=claude_meta["duration_ms"],
        )

    def _build_retrieval_query(self, protocol: ProtocolRequirements) -> str:
        """Construct a retrieval query mixing semantic and keyword signal."""
        parts = [protocol.description]
        if protocol.organism:
            parts.append(f"organism: {protocol.organism}")
        if protocol.temperature_c is not None:
            parts.append(f"temperature {protocol.temperature_c}C")
        if protocol.co2_pct is not None:
            parts.append(f"CO2 {protocol.co2_pct}%")
        if protocol.requires_imaging:
            parts.append("imaging microscopy")
        if protocol.requires_media_exchange:
            parts.append("media exchange perfusion")
        return " ".join(parts)

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
    def _empty_result(search_result: SearchResult) -> HardwareAgentOutput:
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
            retrieval_ms=search_result.retrieval_ms,
            reasoning_ms=0,
        )
