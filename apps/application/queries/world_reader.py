from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.queries.world import list_world_stories
from apps.application.views.world import WorldStoryListView

_logger = logging.getLogger(__name__)


class WorldStoryReader:
    """Replaceable measured read snapshot; source revisions remain authoritative.

    Cold readers share one read. Once measured, stale reads return immediately
    while one owned session refreshes. Responses keep the measurement timestamp.
    """

    def __init__(self, factory: async_sessionmaker[AsyncSession], *, ttl_seconds: float = 15):
        self.factory = factory
        self.ttl_seconds = ttl_seconds
        self._snapshot: tuple[float, WorldStoryListView] | None = None
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None

    async def read(self, limit: int = 10) -> WorldStoryListView:
        if self._snapshot is None:
            await self._refresh()
        elif self._expired() and (self._refresh_task is None or self._refresh_task.done()):
            self._refresh_task = asyncio.create_task(self._refresh())
            self._refresh_task.add_done_callback(self._observe_refresh)
        assert self._snapshot is not None
        response = self._snapshot[1].model_copy(deep=True)
        response.items = response.items[:limit]
        return response

    async def _refresh(self) -> None:
        async with self._lock:
            if self._expired():
                async with self.factory() as session:
                    snapshot = await list_world_stories(session, limit=18)
                self._snapshot = (monotonic(), snapshot)

    def _expired(self) -> bool:
        return self._snapshot is None or monotonic() - self._snapshot[0] >= self.ttl_seconds

    @staticmethod
    def _observe_refresh(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (error := task.exception()) is not None:
            _logger.warning(
                "WORLD refresh failed (%s); retaining measurement", type(error).__name__
            )

    async def warm(self) -> None:
        try:
            (await self.read()).model_dump_json()
        except Exception as error:
            _logger.warning("WORLD warm read failed (%s)", type(error).__name__)

    async def close(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._refresh_task
