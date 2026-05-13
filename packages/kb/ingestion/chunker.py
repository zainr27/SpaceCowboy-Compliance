from __future__ import annotations

import hashlib

import structlog
from unstructured.chunking.title import chunk_by_title

from packages.kb.models.schemas import RawChunk

logger = structlog.get_logger(__name__)


def chunk_elements(elements: list) -> list[RawChunk]:
    """Chunk elements by document structure (titles, sections).

    Each chunk is up to ~1500 characters, respecting section boundaries.
    Tables stay intact. Section path is preserved as metadata.
    """
    if not elements:
        return []

    chunks = chunk_by_title(
        elements,
        max_characters=1500,
        new_after_n_chars=1200,
        combine_text_under_n_chars=300,
        multipage_sections=True,
    )

    raw_chunks: list[RawChunk] = []
    for idx, ch in enumerate(chunks):
        content = (ch.text or "").strip()
        if not content:
            continue

        # Extract page number from the chunk's metadata
        page = _safe_page_number(ch)

        # Build a section path from element ancestry if available
        section_path = _safe_section_path(ch)

        # Determine chunk type
        chunk_type = _infer_chunk_type(ch)

        raw_chunks.append(
            RawChunk(
                chunk_index=idx,
                content=content,
                page_number=page,
                section_path=section_path,
                chunk_type=chunk_type,
                token_count=_estimate_tokens(content),
            )
        )

    logger.info(
        "chunked_document",
        total_chunks=len(raw_chunks),
        avg_chars=_average_length(raw_chunks),
    )
    return raw_chunks


def compute_content_hash(content: str) -> str:
    """Hash chunk content for deduplication and idempotency."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _safe_page_number(chunk) -> int | None:
    """Extract page number from a chunk's metadata safely."""
    try:
        return chunk.metadata.page_number
    except AttributeError:
        return None


def _safe_section_path(chunk) -> str | None:
    """Extract section path from a chunk's metadata if available."""
    try:
        # unstructured doesn't always populate this; best-effort
        title = getattr(chunk.metadata, "section", None)
        return title if title else None
    except AttributeError:
        return None


def _infer_chunk_type(chunk) -> str:
    """Classify chunk as text, table, or figure caption."""
    try:
        cat = chunk.category
    except AttributeError:
        return "text"

    if cat == "Table":
        return "table"
    if cat in ("FigureCaption", "Caption"):
        return "figure_caption"
    return "text"


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate: 1 token ≈ 4 characters for English."""
    return max(1, len(text) // 4)


def _average_length(chunks: list[RawChunk]) -> float:
    if not chunks:
        return 0.0
    return sum(len(c.content) for c in chunks) / len(chunks)
