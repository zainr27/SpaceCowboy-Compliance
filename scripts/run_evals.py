"""Run the eval suite and print a formatted report.

Usage:
    make eval
    uv run python scripts/run_evals.py --no-rerank
    uv run python scripts/run_evals.py --threshold 0.7
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from apps.api.logging_config import configure_logging
from packages.evals.runner import run_eval_suite
from packages.evals.schemas import EvalRunSummary


def _fmt(value: float | None, places: int = 3) -> str:
    if value is None:
        return "  n/a"
    return f"{value:.{places}f}"


def _bar(value: float | None, width: int = 20) -> str:
    if value is None:
        return " " * width
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)


def print_summary(summary: EvalRunSummary) -> None:
    print()
    print("=" * 80)
    print(f"EVAL RUN: {summary.run_id}")
    print(f"At:       {summary.run_at.isoformat()}")
    if summary.git_sha:
        print(f"Git:      {summary.git_sha[:12]}")
    print(f"Examples: {summary.example_count}")
    print(f"Config:   {summary.config}")
    print("=" * 80)
    print()
    print("AGGREGATE METRICS")
    print("-" * 80)
    print(
        f"  Keyword coverage:     {_fmt(summary.mean_keyword_coverage)} {_bar(summary.mean_keyword_coverage)}"
    )
    print(
        f"  Recall@5:             {_fmt(summary.mean_recall_at_5)} {_bar(summary.mean_recall_at_5)}"
    )
    print(
        f"  Recall@10:            {_fmt(summary.mean_recall_at_10)} {_bar(summary.mean_recall_at_10)}"
    )
    print(f"  MRR:                  {_fmt(summary.mean_mrr)} {_bar(summary.mean_mrr)}")
    print(
        f"  Source type match:    {_fmt(summary.mean_source_type_match)} {_bar(summary.mean_source_type_match)}"
    )
    print(f"  Forbidden violations: {summary.forbidden_violations}")
    print(f"  Failed examples:      {len(summary.failed_examples)} / {summary.example_count}")
    print()

    if summary.by_intent:
        print("BY INTENT")
        print("-" * 80)
        for intent, scores in summary.by_intent.items():
            print(
                f"  {intent:<25} "
                f"count={int(scores['count']):<3} "
                f"coverage={_fmt(scores['mean_keyword_coverage'])} "
                f"recall@5={_fmt(scores['mean_recall_at_5'])} "
                f"mrr={_fmt(scores['mean_mrr'])}"
            )
        print()

    print("PER-EXAMPLE")
    print("-" * 80)
    for r in summary.per_example:
        if r.forbidden_keyword_violation:
            status = "VIOL"
        elif r.keyword_coverage is not None and r.keyword_coverage < 0.5:
            status = "FAIL"
        else:
            status = "PASS"
        print(
            f"  [{status}] {r.example_id:<32} "
            f"cov={_fmt(r.keyword_coverage)} "
            f"src={_fmt(r.source_type_match)} "
            f"({r.retrieval_ms}ms)"
        )
    print()

    if summary.failed_examples:
        print("FAILED EXAMPLES (keyword coverage below threshold)")
        print("-" * 80)
        for fid in summary.failed_examples:
            failed = next(r for r in summary.per_example if r.example_id == fid)
            print(f"  {fid}: '{failed.query[:60]}' (coverage={_fmt(failed.keyword_coverage)})")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the retrieval eval suite")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    configure_logging()

    summary = await run_eval_suite(
        dataset_path=args.dataset,
        k=args.k,
        top_n=args.top_n,
        use_reranker=not args.no_rerank,
        failure_threshold=args.threshold,
    )

    print_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())
