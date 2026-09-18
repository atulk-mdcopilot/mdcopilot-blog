"""Per-provider concurrency: one semaphore per (event loop, provider key)."""

import asyncio
import threading
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ProviderLimiter:
    """Caps concurrent calls per provider key, never shared between event loops."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("provider concurrency must be >= 1")
        self._limit = limit
        self._semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Semaphore]] = (
            weakref.WeakKeyDictionary()
        )

    @property
    def limit(self) -> int:
        return self._limit

    @asynccontextmanager
    async def slot(self, provider: str) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        per_loop = self._semaphores.get(loop)
        if per_loop is None:
            per_loop = {}
            self._semaphores[loop] = per_loop
        semaphore = per_loop.get(provider)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._limit)
            per_loop[provider] = semaphore
        async with semaphore:
            yield


_LIMITERS: dict[int, ProviderLimiter] = {}
_LOCK = threading.Lock()


def process_limiter(limit: int) -> ProviderLimiter:
    """The same limiter for the same limit within one process."""
    with _LOCK:
        limiter = _LIMITERS.get(limit)
        if limiter is None:
            limiter = ProviderLimiter(limit)
            _LIMITERS[limit] = limiter
        return limiter
