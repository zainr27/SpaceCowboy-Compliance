from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.config import get_settings

_settings = get_settings()

# Single engine for the whole app
engine = create_async_engine(
    _settings.database_url,
    echo=_settings.is_dev and False,  # Set True to log every SQL statement (noisy)
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Detects dropped connections, reconnects automatically
)

# Session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # Allows accessing objects after commit
    class_=AsyncSession,
)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Async context manager for a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session_dep() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency variant. Use with Depends(get_session_dep)."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
