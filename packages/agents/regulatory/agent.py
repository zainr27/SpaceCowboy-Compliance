from __future__ import annotations

import time

import structlog

from packages.agents.base import (
    MultiQueryRetrievalResult,
    call_llm_structured,
    retrieve_multi_query,
)
from packages.agents.hardware.schemas import ProtocolRequirements
from packages.agents.regulatory.prompts import SYSTEM_PROMPT, build_user_prompt
from packages.agents.regulatory.schemas import (
    RegulatoryAgentOutput,
    RegulatoryAnalysis,
    ResolvedCitation,
)
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.agents.profiles import AgentProfile

logger = structlog.get_logger(__name__)


class RegulatoryAgent:
    """Maps protocols to applicable regulatory frameworks and compliance requirements.

    Pipeline:
    1. Decompose protocol into framework / compliance / commercial queries
    2. Multi-query retrieval via REGULATORY profile
    3. Call LLM with system prompt + protocol + retrieved context
    4. Parse structured response, resolve citation indices
    """

    AGENT_NAME = "regulatory_pathway_agent"
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._kb = KnowledgeBase.for_agent(AgentProfile.REGULATORY)

    async def analyze(
        self,
        protocol: ProtocolRequirements,
        retrieval_top_n: int = 8,
    ) -> RegulatoryAgentOutput:
        start = time.monotonic()
        logger.info(
            "regulatory_agent_start",
            organism=protocol.organism,
            intent=protocol.intent,
            biosafety=protocol.biosafety_level,
        )

        queries = self._decompose_query(protocol)
        logger.info(
            "regulatory_agent_query_decomposition",
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
            logger.warning("regulatory_agent_no_retrieval_results")
            return self._empty_result(retrieval)

        analysis, llm_meta = await call_llm_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(protocol, retrieval.formatted_context),
            output_schema=RegulatoryAnalysis,
            model=self._model,
        )

        resolved_citations = self._resolve_citations(analysis, retrieval.citations)

        total_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "regulatory_agent_complete",
            applicable_frameworks=len(analysis.applicable_frameworks),
            requirements=len(analysis.compliance_requirements),
            reviews=len(analysis.review_processes),
            open_questions=len(analysis.open_questions),
            overall_confidence=analysis.overall_confidence,
            total_ms=total_ms,
        )

        return RegulatoryAgentOutput(
            analysis=analysis,
            citations=resolved_citations,
            retrieval_chunks_used=len(retrieval.chunks),
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=llm_meta["duration_ms"],
        )

    def _decompose_query(self, protocol: ProtocolRequirements) -> list[str]:
        """Build orthogonal queries for regulatory pathway retrieval.

        Three facets:
        1. Framework — which regulatory bodies apply (NASA, FDA, export, etc.)?
        2. Compliance — what specific requirements and documentation are needed?
        3. Commercial — ISS National Lab / CASIS process if commercial intent?
        """
        queries: list[str] = []

        # Query 1: Framework — broad regulatory landscape
        framework_parts = ["regulatory framework compliance space"]
        desc_lower = protocol.description.lower()
        if protocol.intent == "clinical_pathway" or "clinical" in desc_lower:
            framework_parts.append("FDA clinical preclinical IND")
        if protocol.intent == "commercial":
            framework_parts.append("commercial space FDA export control")
        if "pharmaceutical" in desc_lower or "drug" in desc_lower:
            framework_parts.append("FDA pharmacogenomics drug-gene interaction")
        if "genetic" in desc_lower or "gmo" in desc_lower or "modified" in desc_lower:
            framework_parts.append("genetic data GINA export control biotech")
        queries.append(" ".join(framework_parts))

        # Query 2: Compliance and review — NASA process and specifics
        compliance_parts = [
            "NASA payload safety review compliance",
            "PSWG safety data package review process",
        ]
        if protocol.biosafety_level:
            compliance_parts.append(f"{protocol.biosafety_level} regulatory containment")
        queries.append(" ".join(compliance_parts))

        # Query 3: Commercial — CASIS / ISS National Lab if applicable
        if protocol.intent in ("commercial", "clinical_pathway"):
            commercial_parts = [
                "ISS National Lab CASIS commercial use agreement",
                "Implementation Partner contract compliance",
            ]
            if protocol.intent == "clinical_pathway":
                commercial_parts.append("IP intellectual property data governance")
            queries.append(" ".join(commercial_parts))

        return queries

    @staticmethod
    def _resolve_citations(
        analysis: RegulatoryAnalysis,
        kb_citations: list[Citation],
    ) -> list[ResolvedCitation]:
        used_indices: set[int] = set()
        for framework in analysis.applicable_frameworks:
            used_indices.update(framework.citation_indices)
        for req in analysis.compliance_requirements:
            used_indices.update(req.citation_indices)
        for review in analysis.review_processes:
            used_indices.update(review.citation_indices)

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
    def _empty_result(retrieval: MultiQueryRetrievalResult) -> RegulatoryAgentOutput:
        return RegulatoryAgentOutput(
            analysis=RegulatoryAnalysis(
                summary="No relevant regulatory content found in the knowledge base for this protocol.",
                applicable_frameworks=[],
                compliance_requirements=[],
                review_processes=[],
                open_questions=[
                    "The knowledge base did not return relevant regulatory content for this protocol. "
                    "Regulatory landscape must be assessed by external legal and compliance counsel."
                ],
                overall_confidence=0.0,
            ),
            citations=[],
            retrieval_chunks_used=0,
            retrieval_ms=retrieval.total_retrieval_ms,
            reasoning_ms=0,
        )
