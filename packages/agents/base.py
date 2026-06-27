from __future__ import annotations

import time
from functools import lru_cache
from typing import TypedDict, TypeVar

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from apps.api.config import get_settings
from packages.kb.agents.knowledge_base import Citation, KnowledgeBase
from packages.kb.models.retrieval import RetrievedChunk

logger = structlog.get_logger(__name__)

TOutput = TypeVar("TOutput", bound=BaseModel)


class LLMCallMetadata(TypedDict):
    duration_ms: int
    input_tokens: int
    output_tokens: int
    model: str


class AgentMetadata(BaseModel):
    """Provenance for an agent run."""

    agent_name: str
    model: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    retrieval_chunks: int = 0
    retrieval_ms: int = 0


class AgentResult(BaseModel):
    """Wrapper around any agent's structured output."""

    output: BaseModel
    metadata: AgentMetadata


# Per-request ceiling for a single LLM call. Beyond this the request is
# abandoned so one slow upstream call can't stall the whole orchestration.
LLM_TIMEOUT_S = 45.0


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Lazy, process-wide OpenAI client.

    Cached so we reuse one httpx connection pool (keep-alive + a single TLS
    handshake) across every call instead of rebuilding the client each time.
    """
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=LLM_TIMEOUT_S,
        max_retries=1,
    )


async def call_llm_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    output_schema: type[TOutput],
    model: str = "gpt-4o",
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> tuple[TOutput, LLMCallMetadata]:
    """Call the LLM with a system prompt and user prompt, parse structured output.

    Returns (parsed_output, raw_metadata).
    Raises if the model returns invalid JSON or doesn't match the schema.
    """
    client = get_openai_client()

    schema_json = output_schema.model_json_schema()
    augmented_system = (
        f"{system_prompt}\n\n"
        f"You MUST respond with valid JSON matching this schema exactly:\n"
        f"```json\n{schema_json}\n```\n\n"
        f"Respond ONLY with the JSON object. No prose before or after. "
        f"No markdown code fences. Just the raw JSON."
    )

    start = time.monotonic()
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        # Guarantee syntactically valid JSON from the model. The schema still
        # lives in the system prompt to constrain *shape*; this just removes
        # the prose/code-fence failure modes the manual parser used to hit.
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_prompt},
        ],
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    text = (response.choices[0].message.content or "").strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

    try:
        parsed = output_schema.model_validate_json(text)
    except Exception as e:
        logger.error(
            "agent_output_parse_failed",
            error=str(e),
            raw_text=text[:500],
            schema=output_schema.__name__,
        )
        raise

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    metadata: LLMCallMetadata = {
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model,
    }

    logger.info(
        "llm_structured_complete",
        model=model,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        schema=output_schema.__name__,
    )

    return parsed, metadata


class MultiQueryRetrievalResult(BaseModel):
    """Merged result from running multiple retrieval queries in parallel."""

    chunks: list[RetrievedChunk]
    citations: list[Citation]
    formatted_context: str
    queries_used: list[str]
    total_retrieval_ms: int
    rerank_ms: int | None


async def retrieve_multi_query(
    *,
    kb: KnowledgeBase,
    queries: list[str],
    per_query_k: int = 10,
    final_top_n: int = 8,
    min_docs: int = 3,
) -> MultiQueryRetrievalResult:
    """Run multiple queries in parallel, merge by best score, return top-N chunks.

    Deduplicates by chunk_id, keeping the highest rerank/fusion score per chunk.
    Applies document diversity: reserves slots so at least min_docs distinct source
    documents appear in the final context, preventing one large document from
    monopolizing all slots.
    """
    start = time.monotonic()

    results = await kb.search_many(
        queries,
        k=per_query_k,
        top_n=per_query_k,
        use_reranker=True,
    )

    merged: dict[str, RetrievedChunk] = {}
    for result in results:
        for chunk in result.chunks:
            key = str(chunk.chunk_id)
            score = chunk.rerank_score or chunk.fusion_score or 0.0
            existing = merged.get(key)
            if existing is None:
                merged[key] = chunk
            else:
                existing_score = existing.rerank_score or existing.fusion_score or 0.0
                if score > existing_score:
                    merged[key] = chunk

    sorted_candidates = sorted(
        merged.values(),
        key=lambda c: c.rerank_score or c.fusion_score or 0.0,
        reverse=True,
    )

    # Document diversity: greedily fill slots, ensuring min_docs distinct documents
    # appear before any single document can fill remaining slots.
    seen_docs: set[str] = set()
    diverse: list[RetrievedChunk] = []
    deferred: list[RetrievedChunk] = []
    for chunk in sorted_candidates:
        doc_key = str(chunk.document_id)
        if doc_key not in seen_docs or len(seen_docs) >= min_docs:
            diverse.append(chunk)
            seen_docs.add(doc_key)
        else:
            deferred.append(chunk)
        if len(diverse) == final_top_n:
            break
    # Fill remaining slots with highest-scoring deferred chunks
    if len(diverse) < final_top_n:
        diverse.extend(deferred[: final_top_n - len(diverse)])

    sorted_chunks = diverse[:final_top_n]

    citations = _build_citations_from_chunks(sorted_chunks)
    formatted = _format_context_multi_query(queries, sorted_chunks, citations)

    total_ms = int((time.monotonic() - start) * 1000)
    rerank_values = [r.rerank_ms for r in results if r.rerank_ms is not None]
    rerank_ms_total: int | None = sum(rerank_values) if rerank_values else None

    logger.info(
        "multi_query_retrieval_complete",
        queries=len(queries),
        merged_candidates=len(merged),
        final_chunks=len(sorted_chunks),
        total_ms=total_ms,
    )

    return MultiQueryRetrievalResult(
        chunks=sorted_chunks,
        citations=citations,
        formatted_context=formatted,
        queries_used=queries,
        total_retrieval_ms=total_ms,
        rerank_ms=rerank_ms_total,
    )


def _build_citations_from_chunks(chunks: list[RetrievedChunk]) -> list[Citation]:
    """Build Citation objects from a list of RetrievedChunks."""
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


def _format_context_multi_query(
    queries: list[str],
    chunks: list[RetrievedChunk],
    citations: list[Citation],
) -> str:
    """Format merged multi-query chunks into a prompt-ready context block."""
    if not chunks:
        queries_str = "; ".join(queries)
        return f"Queries: {queries_str}\n\nNo relevant sources found."

    lines = ["Queries used:"]
    for q in queries:
        lines.append(f"  - {q}")
    lines.append("")

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
