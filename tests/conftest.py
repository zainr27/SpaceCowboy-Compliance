import pytest

import packages.kb.retrieval.reranker as reranker_module
import packages.kb.storage.database as db_module


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def reset_singletons() -> None:
    """Dispose loop-bound singletons before each test and clean up after.

    pytest-asyncio creates a new event loop per test. asyncpg connections and
    httpx async clients are bound to the loop they were created on; reusing
    them across loops raises "Future/Event loop is closed" errors.
    """
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None
    reranker_module._client = None

    yield

    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None
    reranker_module._client = None
