from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.logging_config import configure_logging, get_logger
from apps.api.routes import health

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

app.include_router(health.router)
