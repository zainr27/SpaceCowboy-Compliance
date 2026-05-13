from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Self

import structlog

from packages.kb.agents.profiles import (
    AgentProfile,
    ProfileConfig,
    get_profile,
)
from packages.kb.models.retrieval import (
    RetrievalRequest,
    RetrievedChunk,
)
from packages.kb.retrieval.service import retrieve as raw_retrieve

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Citation:
    """A reference to a specific chunk, suitable for citing in agent output."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source_url: str
    page_number: int | None
    section_path: str | None
    relevance_score: float

    def as_inline(self, idx: int) -> str:
        page = f", p.{self.page_number}" if self.page_number else ""
        return f"[{idx}] {self.title}{page}"

    def as_url(self) -> str:
        return self.source_url


@dataclass(frozen=True)
class SearchResult:
    """The complete result of a KnowledgeBase search.

    Designed to be fed directly into an LLM prompt as context.
    """

    query: str
    chunks: list[RetrievedChunk]
    citations: list[Citation]
    formatted_context: str
    retrieval_ms: int
    rerank_ms: int | None
    profile: AgentProfile | None

    def __bool__(self) -> bool:
        return bool(self.chunks)

    def __len__(self) -> int:
        return len(self.chunks)


class KnowledgeBase:
    """Agent-facing wrapper around the retrieval pipeline.

    Two usage patterns:

    1. Profile-bound (recommended for sub-agents):

        kb = KnowledgeBase.for_agent(AgentProfile.HARDWARE)
        result = await kb.search("what hardware supports cell culture?")

    2. Unscoped (for orchestrators and the synthesis agent):

        kb = KnowledgeBase()
        result = await kb.search("anything", source_types=["paper", "regulatory"])
    """

    def __init__(self, profile: AgentProfile | None = None) -> None:
        self._profile = profile
        self._config: ProfileConfig | None = get_profile(profile) if profile is not None else None

    @classmethod
    def for_agent(cls, profile: AgentProfile) -> Self:
        """Create a KB instance scoped to a specific agent's source types."""
        return cls(profile=profile)

    async def search(
        self,
        query: str,
        *,
        k: int | None = None,
        top_n: int | None = None,
        source_types: list[str] | None = None,
        organization: str | None = None,
        use_reranker: bool = True,
    ) -> SearchResult:
        """Run a search and return a fully-formatted result.

        If this KB is profile-bound, source_types defaults to the profile's
        types. Pass source_types explicitly to override.
        """
        start = time.monotonic()

        resolved_source_types = source_types or (
            self._config.source_types if self._config else None
        )
        resolved_k = k or (self._config.default_k if self._config else 20)
        resolved_top_n = top_n or (self._config.default_top_n if self._config else 5)

        req = RetrievalRequest(
            query=query,
            source_types=resolved_source_types,
            organization=organization,
            k=resolved_k,
            rerank_top_n=resolved_top_n,
            use_reranker=use_reranker,
        )

        response = await raw_retrieve(req)

        citations = self._build_citations(response.chunks)
        formatted = self._format_context(query, response.chunks, citations)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "kb_search_complete",
            profile=str(self._profile) if self._profile else "unscoped",
            query_length=len(query),
            source_types=resolved_source_types,
            returned=len(response.chunks),
            total_ms=elapsed_ms,
            retrieval_ms=response.retrieval_ms,
            rerank_ms=response.rerank_ms,
        )

        return SearchResult(
            query=query,
            chunks=response.chunks,
            citations=citations,
            formatted_context=formatted,
            retrieval_ms=response.retrieval_ms,
            rerank_ms=response.rerank_ms,
            profile=self._profile,
        )

    async def search_many(
        self,
        queries: list[str],
        **kwargs: Any,
    ) -> list[SearchResult]:
        """Run multiple queries in parallel. Useful for agent ReAct loops."""
        return await asyncio.gather(*[self.search(q, **kwargs) for q in queries])

    @staticmethod
    def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
        return [
            Citation(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                title=c.title,
                source_url=c.source_url,
                page_number=c.page_number,
                section_path=c.section_path,
                relevance_score=c.rerank_score or c.fusion_score or 0.0,
            )
            for c in chunks
        ]

    @staticmethod
    def _format_context(
        query: str,
        chunks: list[RetrievedChunk],
        citations: list[Citation],
    ) -> str:
        """Format chunks into a prompt-ready context block.

        Each chunk is prefixed with [N] so the LLM can cite [1], [2] in its
        output, which can then be resolved back to real documents.
        """
        if not chunks:
            return f"Query: {query}\n\nNo relevant sources found."

        lines = [f"Query: {query}", ""]
        for idx, (chunk, citation) in enumerate(zip(chunks, citations, strict=True), start=1):
            header_parts = [f"[{idx}]", citation.title]
            if citation.page_number:
                header_parts.append(f"(p. {citation.page_number})")
            elif citation.section_path:
                header_parts.append(f"({citation.section_path})")
            lines.append(" ".join(header_parts))
            lines.append(chunk.content)
            lines.append("")

        return "\n".join(lines).rstrip()
