from __future__ import annotations

import json
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

from packages.evals.metrics import score_example
from packages.evals.schemas import (
    EvalRunSummary,
    ExampleResult,
    GoldenExample,
    QueryIntent,
)
from packages.kb.models.retrieval import RetrievalRequest
from packages.kb.retrieval.service import retrieve
from packages.kb.storage.database import get_session
from packages.kb.storage.models import EvalRun

logger = structlog.get_logger(__name__)

_DATASET_PATH = Path(__file__).parent / "datasets" / "golden_v1.jsonl"


def load_golden_examples(path: Path | None = None) -> list[GoldenExample]:
    """Load examples from JSONL. Each line is one GoldenExample as JSON."""
    target = path or _DATASET_PATH
    examples: list[GoldenExample] = []
    with target.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                examples.append(GoldenExample(**data))
            except Exception as e:
                logger.error("failed_to_parse_example", line_num=line_num, error=str(e))
                raise
    return examples


async def run_single_example(
    example: GoldenExample,
    k: int = 10,
    top_n: int = 10,
    use_reranker: bool = True,
) -> ExampleResult:
    """Run one query and score it."""
    request = RetrievalRequest(
        query=example.query,
        k=k,
        rerank_top_n=top_n,
        use_reranker=use_reranker,
    )
    response = await retrieve(request)
    scores = score_example(example, response.chunks)

    retrieved_ids = [c.chunk_id for c in response.chunks]
    top_chunk_id = retrieved_ids[0] if retrieved_ids else None
    top_score = (
        response.chunks[0].rerank_score or response.chunks[0].fusion_score
        if response.chunks
        else None
    )

    return ExampleResult(
        example_id=example.id,
        query=example.query,
        intent=example.intent,
        retrieved_chunk_ids=retrieved_ids,
        top_chunk_id=top_chunk_id,
        top_score=top_score,
        keyword_coverage=scores["keyword_coverage"],
        chunk_recall_at_5=scores["chunk_recall_at_5"],
        chunk_recall_at_10=scores["chunk_recall_at_10"],
        mrr=scores["mrr"],
        source_type_match=scores["source_type_match"],
        forbidden_keyword_violation=scores["forbidden_violation"],
        retrieval_ms=response.retrieval_ms,
        rerank_ms=response.rerank_ms,
    )


async def run_eval_suite(
    dataset_path: Path | None = None,
    k: int = 10,
    top_n: int = 10,
    use_reranker: bool = True,
    failure_threshold: float = 0.5,
) -> EvalRunSummary:
    """Run the full eval suite and return an aggregated summary."""
    start = time.monotonic()
    examples = load_golden_examples(dataset_path)
    logger.info("eval_suite_starting", example_count=len(examples))

    # Sequential to avoid hitting Cohere trial rate limits (10 calls/min).
    results: list[ExampleResult] = []
    for example in examples:
        result = await run_single_example(example, k=k, top_n=top_n, use_reranker=use_reranker)
        results.append(result)
        logger.info(
            "example_complete",
            example_id=example.id,
            keyword_coverage=result.keyword_coverage,
            source_type_match=result.source_type_match,
        )

    summary = _aggregate(results, failure_threshold)
    summary.config = {
        "k": k,
        "top_n": top_n,
        "use_reranker": use_reranker,
        "dataset_path": str(dataset_path or _DATASET_PATH),
    }

    await _persist_run(summary)

    logger.info(
        "eval_suite_complete",
        duration_seconds=round(time.monotonic() - start, 1),
        mean_keyword_coverage=summary.mean_keyword_coverage,
        failed_count=len(summary.failed_examples),
    )
    return summary


def _aggregate(
    results: list[ExampleResult],
    failure_threshold: float,
) -> EvalRunSummary:
    def mean(values: list[float | None]) -> float | None:
        clean = [v for v in values if v is not None]
        return sum(clean) / len(clean) if clean else None

    failed = [
        r.example_id
        for r in results
        if r.keyword_coverage is not None and r.keyword_coverage < failure_threshold
    ]

    by_intent: dict[str, dict[str, float]] = {}
    for intent in QueryIntent:
        intent_results = [r for r in results if r.intent == intent]
        if not intent_results:
            continue
        by_intent[str(intent)] = {
            "count": float(len(intent_results)),
            "mean_keyword_coverage": mean([r.keyword_coverage for r in intent_results]) or 0.0,
            "mean_recall_at_5": mean([r.chunk_recall_at_5 for r in intent_results]) or 0.0,
            "mean_mrr": mean([r.mrr for r in intent_results]) or 0.0,
        }

    return EvalRunSummary(
        run_id=uuid.uuid4(),
        run_at=datetime.now(UTC),
        git_sha=_get_git_sha(),
        config={},
        example_count=len(results),
        mean_keyword_coverage=mean([r.keyword_coverage for r in results]),
        mean_recall_at_5=mean([r.chunk_recall_at_5 for r in results]),
        mean_recall_at_10=mean([r.chunk_recall_at_10 for r in results]),
        mean_mrr=mean([r.mrr for r in results]),
        mean_source_type_match=mean([r.source_type_match for r in results]),
        forbidden_violations=sum(1 for r in results if r.forbidden_keyword_violation),
        failed_examples=failed,
        by_intent=by_intent,
        per_example=results,
    )


def _get_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


async def _persist_run(summary: EvalRunSummary) -> None:
    """Store the run in the database for trend tracking."""
    async with get_session() as session:
        row = EvalRun(
            id=summary.run_id,
            run_at=summary.run_at,
            git_sha=summary.git_sha,
            config=summary.config,
            metrics={
                "mean_keyword_coverage": summary.mean_keyword_coverage,
                "mean_recall_at_5": summary.mean_recall_at_5,
                "mean_recall_at_10": summary.mean_recall_at_10,
                "mean_mrr": summary.mean_mrr,
                "mean_source_type_match": summary.mean_source_type_match,
                "forbidden_violations": summary.forbidden_violations,
                "failed_example_count": len(summary.failed_examples),
                "example_count": summary.example_count,
            },
            per_example_results={
                "examples": [r.model_dump(mode="json") for r in summary.per_example],
                "by_intent": summary.by_intent,
                "failed_examples": summary.failed_examples,
            },
        )
        session.add(row)
        await session.flush()
