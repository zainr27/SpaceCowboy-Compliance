from __future__ import annotations

from fastapi import APIRouter

from packages.kb.models.retrieval import RetrievalRequest, RetrievalResponse
from packages.kb.retrieval.service import retrieve

router = APIRouter()


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_endpoint(request: RetrievalRequest) -> RetrievalResponse:
    return await retrieve(request)
