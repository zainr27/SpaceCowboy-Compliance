from __future__ import annotations

from fastapi import APIRouter

from packages.orchestrator.gap_store import get_backlog

router = APIRouter(prefix="/gaps", tags=["gaps"])


@router.get("/backlog")
async def gap_backlog() -> dict[str, object]:
    """Ranked 'ingest these next' backlog aggregated from past analyses.

    Surfaces the open questions and corpus-gap themes the agents most often
    could not ground in the current corpus.
    """
    return get_backlog()
