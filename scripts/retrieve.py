"""CLI for testing retrieval interactively.

Usage:
    uv run python scripts/retrieve.py "your query here"
    uv run python scripts/retrieve.py "query" --k 30 --top-n 10 --no-rerank
"""

from __future__ import annotations

import argparse
import asyncio

from apps.api.logging_config import configure_logging
from packages.kb.models.retrieval import RetrievalRequest
from packages.kb.retrieval.service import retrieve


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test retrieval against the knowledge base")
    parser.add_argument("query", help="Natural-language query")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument(
        "--source-types",
        nargs="*",
        default=None,
        help="Filter to specific source types",
    )
    args = parser.parse_args()

    configure_logging()

    response = await retrieve(
        RetrievalRequest(
            query=args.query,
            source_types=args.source_types,
            k=args.k,
            rerank_top_n=args.top_n,
            use_reranker=not args.no_rerank,
        )
    )

    print()
    print(f"Query: {response.query}")
    print(f"Candidates from hybrid: {response.total_candidates}")
    print(
        f"Retrieval: {response.retrieval_ms}ms"
        + (f" | Rerank: {response.rerank_ms}ms" if response.rerank_ms else "")
    )
    print(f"Returned: {len(response.chunks)} chunks")
    print()

    for i, chunk in enumerate(response.chunks, 1):
        print(f"--- Result {i} ---")
        print(f"Title: {chunk.title}")
        print(f"Page: {chunk.page_number} | Section: {chunk.section_path or 'n/a'}")
        scores = []
        if chunk.dense_score is not None:
            scores.append(f"dense={chunk.dense_score:.3f}")
        if chunk.sparse_score is not None:
            scores.append(f"sparse={chunk.sparse_score:.3f}")
        if chunk.fusion_score is not None:
            scores.append(f"fusion={chunk.fusion_score:.4f}")
        if chunk.rerank_score is not None:
            scores.append(f"rerank={chunk.rerank_score:.3f}")
        print(f"Scores: {' | '.join(scores)}")
        print(f"Content: {chunk.content[:300]}...")
        print()


if __name__ == "__main__":
    asyncio.run(main())
