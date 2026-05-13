from __future__ import annotations

from fastapi import APIRouter, HTTPException

from packages.kb.models.retrieval import RetrievalRequest, RetrievalResponse
from packages.kb.retrieval.service import retrieve

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_endpoint(req: RetrievalRequest) -> RetrievalResponse:
    """Retrieve relevant chunks for a natural-language query.

    Combines dense vector search, BM25 keyword search, and Cohere reranking.
    Returns chunks with full provenance (document title, page, section).
    """
    try:
        return await retrieve(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {type(e).__name__}") from e
