"""Security and cost-control dependencies for the API.

Provides:
- `require_api_key`: optional API-key authentication. When no key is
  configured (`API_KEY` unset/empty), it is a no-op pass-through so local dev
  and the test suite work with zero config. When configured, it validates an
  `X-API-Key` header or an `Authorization: Bearer <key>` header against the
  configured key(s) using a constant-time comparison.
- `analysis_slot`: a process-wide concurrency cap on expensive analyses. When
  all slots are in use, excess concurrent requests receive HTTP 429 rather
  than queueing unboundedly (a cost-bomb guard).
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Header, HTTPException, status

from apps.api.config import get_settings


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency enforcing optional API-key authentication.

    - If no API keys are configured, this is a no-op (auth disabled).
    - Otherwise, the request must present a valid key via either the
      `X-API-Key` header or `Authorization: Bearer <key>`.
    - Comparison is constant-time to avoid timing side channels.
    - Raises 401 on a missing or invalid key.
    """
    configured = get_settings().api_keys
    if not configured:
        return  # Auth disabled.

    presented = x_api_key
    if presented is None and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            presented = token

    if presented is not None:
        for key in configured:
            if secrets.compare_digest(presented, key):
                return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Process-wide concurrency guard for expensive analyses. We track active
# slots with a counter + lock rather than a Semaphore so we can fail fast
# (429) when full instead of queueing unboundedly — a cost-bomb guard.
# Lazily initialised so the size is config-driven and the test suite (which
# never hits these routes) is unaffected.
_active = 0
_lock = None


def _get_lock():  # type: ignore[no-untyped-def]
    global _lock
    if _lock is None:
        import asyncio

        _lock = asyncio.Lock()
    return _lock


@asynccontextmanager
async def _acquire_slot() -> AsyncIterator[None]:
    global _active
    limit = max(1, get_settings().max_concurrent_analyses)
    lock = _get_lock()

    async with lock:
        if _active >= limit:
            # Fail fast instead of queueing a cost-bomb.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Server is at capacity; retry shortly.",
                headers={"Retry-After": "5"},
            )
        _active += 1

    try:
        yield
    finally:
        async with lock:
            _active -= 1


async def analysis_slot() -> AsyncIterator[None]:
    """FastAPI dependency: acquire a concurrency slot for the request.

    Returns 429 immediately if all slots are in use (no unbounded queueing).
    The slot is held for the duration of the request and released on teardown.
    """
    async with _acquire_slot():
        yield
