import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_db_engine() -> None:
    """Reset the lazy DB engine singleton before each test.

    pytest-asyncio creates a new event loop per test by default. asyncpg
    connections are bound to the loop they were created on, so reusing an
    engine across loops raises "Future attached to a different loop".
    Resetting the singleton forces a fresh engine (and fresh connections)
    on each test's loop.
    """
    import packages.kb.storage.database as db_module

    db_module._engine = None
    db_module._session_factory = None
