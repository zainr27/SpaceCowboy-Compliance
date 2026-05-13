from __future__ import annotations

import uuid

from packages.evals.schemas import GoldenExample
from packages.kb.models.retrieval import RetrievedChunk


def keyword_coverage(chunks: list[RetrievedChunk], expected: list[str]) -> float:
    """Fraction of expected keywords found across all retrieved chunks.

    Case-insensitive substring match. Returns 0.0 if no expected keywords.
    """
    if not expected or not chunks:
        return 0.0
    combined = " ".join(c.content for c in chunks).lower()
    found = sum(1 for kw in expected if kw.lower() in combined)
    return found / len(expected)


def recall_at_k(
    retrieved_ids: list[uuid.UUID],
    expected_ids: list[uuid.UUID],
    k: int,
) -> float | None:
    """Of the expected chunks, how many appeared in top-k?

    Returns None if no chunk-level ground truth.
    """
    if not expected_ids:
        return None
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for eid in expected_ids if eid in top_k)
    return hits / len(expected_ids)


def mrr(
    retrieved_ids: list[uuid.UUID],
    expected_ids: list[uuid.UUID],
) -> float | None:
    """Mean Reciprocal Rank: 1 / (position of first correct result).

    Returns None if no chunk-level ground truth. Returns 0.0 if no expected
    chunks were retrieved.
    """
    if not expected_ids:
        return None
    expected_set = set(expected_ids)
    for i, rid in enumerate(retrieved_ids, start=1):
        if rid in expected_set:
            return 1.0 / i
    return 0.0


def source_type_match(
    chunks: list[RetrievedChunk],
    expected_source_types: list[str],
) -> float | None:
    """Fraction of retrieved chunks whose source_type is in the expected set.

    Returns None if no expected source types.
    """
    if not expected_source_types:
        return None
    if not chunks:
        return 0.0
    expected_set = set(expected_source_types)
    matches = sum(1 for c in chunks if c.source_type in expected_set)
    return matches / len(chunks)


def forbidden_keyword_violation(
    chunks: list[RetrievedChunk],
    forbidden: list[str],
) -> bool:
    """True if the top chunk contains any forbidden keyword.

    Only checks the top result — if irrelevant content ranks first, that's the
    failure mode worth catching.
    """
    if not forbidden or not chunks:
        return False
    top_content = chunks[0].content.lower()
    return any(kw.lower() in top_content for kw in forbidden)


def score_example(
    example: GoldenExample,
    chunks: list[RetrievedChunk],
) -> dict:
    """Apply all relevant metrics to one example's retrieval results."""
    retrieved_ids = [c.chunk_id for c in chunks]
    return {
        "keyword_coverage": keyword_coverage(chunks, example.expected_keywords),
        "chunk_recall_at_5": recall_at_k(retrieved_ids, example.expected_chunk_ids, 5),
        "chunk_recall_at_10": recall_at_k(retrieved_ids, example.expected_chunk_ids, 10),
        "mrr": mrr(retrieved_ids, example.expected_chunk_ids),
        "source_type_match": source_type_match(chunks, example.expected_source_types),
        "forbidden_violation": forbidden_keyword_violation(chunks, example.forbidden_keywords),
    }
