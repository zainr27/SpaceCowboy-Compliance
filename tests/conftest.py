import pytest

import packages.kb.storage.database as db_module


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def reset_db_engine() -> None:
    """Dispose engine bound to the previous test's loop before each test.

    Without dispose(), the connection pool is leaked across tests. At small
    counts this is invisible; under load it exhausts Postgres max_connections.
    """
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None
    yield
    if db_module._engine is not None:
        await db_module._engine.dispose()
    db_module._engine = None
    db_module._session_factory = None
