from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.logging_config import configure_logging, get_logger
from apps.api.routes import agents, gaps, health, kb, retrieve
from apps.api.security import require_api_key

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("api_starting")
    yield
    logger.info("api_stopping")


app = FastAPI(
    title="Space-Bio Translator API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# /health is intentionally left open (no auth) for liveness probes.
app.include_router(health.router)

# Expensive routes (embeddings / reranks / LLM calls) require an API key when
# one is configured. With no API_KEY set, `require_api_key` is a no-op, so
# local dev and tests work unchanged.
_protected = [Depends(require_api_key)]
app.include_router(retrieve.router, dependencies=_protected)
app.include_router(kb.router, dependencies=_protected)
app.include_router(agents.router, dependencies=_protected)
app.include_router(gaps.router, dependencies=_protected)
