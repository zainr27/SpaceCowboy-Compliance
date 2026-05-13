"""CLI for running a knowledge-base search with an agent profile.

Usage:
    uv run python scripts/agent_search.py hardware "what supports cell culture?"
    uv run python scripts/agent_search.py safety "BSL-2 containment requirements"
    uv run python scripts/agent_search.py mission "ISS sample return options"
"""

from __future__ import annotations

import argparse
import asyncio

from apps.api.logging_config import configure_logging
from packages.kb.agents.knowledge_base import KnowledgeBase
from packages.kb.agents.profiles import PROFILES, AgentProfile


async def main() -> None:
    parser = argparse.ArgumentParser(description="Profile-scoped KB search")
    parser.add_argument(
        "profile",
        choices=[p.value for p in AgentProfile],
        help="Which agent profile to use",
    )
    parser.add_argument("query", help="The query string")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--no-rerank", action="store_true")
    args = parser.parse_args()

    configure_logging()

    profile = AgentProfile(args.profile)
    kb = KnowledgeBase.for_agent(profile)

    print(f"\nProfile: {profile.value}")
    print(f"Source types: {PROFILES[profile].source_types}")
    print(f"Description: {PROFILES[profile].description}")
    print(f"\nQuery: {args.query}")
    print("=" * 80)

    result = await kb.search(
        args.query,
        top_n=args.top_n,
        use_reranker=not args.no_rerank,
    )

    print(f"\nRetrieved {len(result)} chunks in {result.retrieval_ms}ms")
    if result.rerank_ms:
        print(f"Reranking took {result.rerank_ms}ms")
    print()
    print("FORMATTED CONTEXT (what an LLM would see):")
    print("-" * 80)
    print(result.formatted_context)
    print("-" * 80)
    print()
    print("CITATIONS:")
    for idx, c in enumerate(result.citations, start=1):
        print(f"  [{idx}] {c.title} | {c.source_url} | score={c.relevance_score:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
