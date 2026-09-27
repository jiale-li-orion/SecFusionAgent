from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from apps.runtime_models import register_runtime_models
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.events.redis_stream import dispatch_pending_task_events

logger = logging.getLogger(__name__)


async def tick() -> int:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url)
    try:
        async with factory() as session, session.begin():
            return await dispatch_pending_task_events(session, redis)
    finally:
        await redis.aclose()
        await engine.dispose()


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            delivered = await tick()
            if delivered:
                logger.info("task event dispatcher delivered=%d", delivered)
        except Exception:
            logger.exception("task event dispatcher tick failed")
        await asyncio.sleep(settings.scheduler_tick_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_forever())
