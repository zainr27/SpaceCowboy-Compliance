"""Gap-driven ingestion backlog.

Every analysis emits ``open_questions`` and ``corpus_gap`` insights — the system
telling you what it could not ground in the corpus. We append those signals to a
JSONL log per run and aggregate them into a ranked "ingest these next" backlog,
so corpus curation is driven by what the agents actually keep asking for.

Storage is a single append-only JSONL file (one line per analysis). A DB table
would be overkill for an advisory backlog and would add a migration; the file is
trivially inspectable and append-only writes are atomic enough for this use.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

import structlog

from packages.orchestrator.schemas import OrchestratorReport

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "data" / "gap_backlog.jsonl"


def _store_path() -> Path:
    return _DEFAULT_PATH


def _normalize(text: str) -> str:
    """Collapse a question/theme to a grouping key (lowercase, alnum, single-spaced)."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def record_gaps(report: OrchestratorReport, *, now: float | None = None) -> None:
    """Append this run's gap signals to the backlog log. Never raises."""
    try:
        corpus_gaps = [
            {"description": i.description, "agents": list(i.involved_agents)}
            for i in report.cross_agent_insights
            if i.kind == "corpus_gap"
        ]
        # Nothing worth recording if the run had no gaps and no open questions.
        if not corpus_gaps and not report.open_questions:
            return
        entry = {
            "ts": now if now is not None else time.time(),
            "protocol": (report.protocol.description or "")[:200],
            "corpus_gaps": corpus_gaps,
            "open_questions": list(report.open_questions),
        }
        path = _store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        logger.exception("gap_record_failed")


def get_backlog(*, top_questions: int = 12, top_themes: int = 8) -> dict[str, object]:
    """Aggregate the log into a ranked backlog.

    Returns recurring open questions and corpus-gap themes ranked by how many
    analyses surfaced them (frequency), with the most recent timestamp as a
    tiebreaker so fresh-but-rare items aren't buried.
    """
    path = _store_path()
    if not path.exists():
        return {"total_runs": 0, "recurring_questions": [], "gap_themes": []}

    q_count: dict[str, int] = defaultdict(int)
    q_repr: dict[str, str] = {}
    q_last: dict[str, float] = defaultdict(float)
    t_count: dict[str, int] = defaultdict(int)
    t_repr: dict[str, str] = {}
    t_agents: dict[str, set[str]] = defaultdict(set)
    total_runs = 0

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        total_runs += 1
        ts = float(entry.get("ts", 0.0))
        for q in entry.get("open_questions", []):
            key = _normalize(q)
            if not key:
                continue
            q_count[key] += 1
            q_repr.setdefault(key, q)
            q_last[key] = max(q_last[key], ts)
        for gap in entry.get("corpus_gaps", []):
            desc = gap.get("description", "")
            key = _normalize(desc)
            if not key:
                continue
            t_count[key] += 1
            t_repr.setdefault(key, desc)
            for a in gap.get("agents", []):
                t_agents[key].add(a)

    recurring_questions = [
        {"question": q_repr[k], "count": q_count[k]}
        for k in sorted(q_count, key=lambda k: (q_count[k], q_last[k]), reverse=True)
    ][:top_questions]

    gap_themes = [
        {"theme": t_repr[k], "count": t_count[k], "agents": sorted(t_agents[k])}
        for k in sorted(t_count, key=lambda k: t_count[k], reverse=True)
    ][:top_themes]

    return {
        "total_runs": total_runs,
        "recurring_questions": recurring_questions,
        "gap_themes": gap_themes,
    }
