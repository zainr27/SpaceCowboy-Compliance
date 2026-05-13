from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.kb.agents.knowledge_base import KnowledgeBase
from packages.kb.agents.profiles import PROFILES, AgentProfile

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


class KBSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    profile: AgentProfile | None = None
    source_types: list[str] | None = None
    organization: str | None = None
    k: int | None = Field(default=None, ge=1, le=100)
    top_n: int | None = Field(default=None, ge=1, le=50)
    use_reranker: bool = True


class KBSearchResponse(BaseModel):
    query: str
    profile: str | None
    formatted_context: str
    citations: list[dict]
    chunk_count: int
    retrieval_ms: int
    rerank_ms: int | None


@router.post("/search", response_model=KBSearchResponse)
async def kb_search(req: KBSearchRequest) -> KBSearchResponse:
    """Run a knowledge-base search scoped to an agent profile.

    Use `profile` to apply that agent's source-type defaults.
    Or pass `source_types` directly for custom filtering.
    """
    try:
        kb = KnowledgeBase.for_agent(req.profile) if req.profile is not None else KnowledgeBase()

        result = await kb.search(
            query=req.query,
            k=req.k,
            top_n=req.top_n,
            source_types=req.source_types,
            organization=req.organization,
            use_reranker=req.use_reranker,
        )

        return KBSearchResponse(
            query=result.query,
            profile=str(result.profile) if result.profile else None,
            formatted_context=result.formatted_context,
            citations=[
                {
                    "index": idx,
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "title": c.title,
                    "source_url": c.source_url,
                    "page_number": c.page_number,
                    "section_path": c.section_path,
                    "relevance_score": c.relevance_score,
                }
                for idx, c in enumerate(result.citations, start=1)
            ],
            chunk_count=len(result),
            retrieval_ms=result.retrieval_ms,
            rerank_ms=result.rerank_ms,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"KB search failed: {type(e).__name__}",
        ) from e


@router.get("/profiles")
async def list_profiles() -> dict:
    """Return all available agent profiles with their source-type mappings."""
    return {
        str(profile): {
            "source_types": config.source_types,
            "default_k": config.default_k,
            "default_top_n": config.default_top_n,
            "description": config.description,
        }
        for profile, config in PROFILES.items()
    }
