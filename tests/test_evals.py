"""Eval suite as a pytest test.

Excluded from normal `make test` runs (slow, hits external APIs).
Run explicitly with `make eval` or `pytest -m evals`.
"""

from __future__ import annotations

import pytest

from packages.evals.runner import run_eval_suite

# Baselines — raise as the system improves, never lower without a documented reason.
MIN_KEYWORD_COVERAGE = 0.4
MAX_FORBIDDEN_VIOLATIONS = 0


@pytest.mark.asyncio
@pytest.mark.evals
async def test_eval_suite_meets_baseline() -> None:
    """The eval suite must meet minimum thresholds on all key metrics.

    If this fails, retrieval has regressed since the last baseline.
    Investigate the failed_examples list and the by_intent breakdown.
    """
    summary = await run_eval_suite()

    assert summary.example_count > 0, "No examples in the eval suite"
    assert summary.forbidden_violations <= MAX_FORBIDDEN_VIOLATIONS, (
        f"Got {summary.forbidden_violations} forbidden keyword violations — "
        f"top results are surfacing irrelevant content."
    )
    if summary.mean_keyword_coverage is not None:
        assert summary.mean_keyword_coverage >= MIN_KEYWORD_COVERAGE, (
            f"Mean keyword coverage {summary.mean_keyword_coverage:.3f} below "
            f"baseline {MIN_KEYWORD_COVERAGE}. "
            f"Failed: {summary.failed_examples}"
        )
