from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class SchedulerGate:
    def __init__(self, heavy_data_sync_limit: int = 1):
        self._heavy_data_sync = asyncio.Semaphore(max(1, heavy_data_sync_limit))

    @asynccontextmanager
    async def heavy_data_sync(self) -> AsyncIterator[None]:
        async with self._heavy_data_sync:
            yield

    @asynccontextmanager
    async def light_status(self) -> AsyncIterator[None]:
        yield
