from __future__ import annotations

import asyncio
import logging
import os
import socket

from redis.asyncio import Redis

from apps.runtime_models import register_runtime_models
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.events.redis_stream import (
    ack_task_event_message,
    read_task_event_messages,
)
from packages.task_runtime.scheduler import DependencyWakeDisposition, DependencyWakeScheduler
from packages.task_runtime.storage.service import get_task_event

logger = logging.getLogger(__name__)


async def tick(*, consumer_name: str | None = None) -> tuple[int, int, int]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    resolved_consumer = consumer_name or _consumer_name()
    scheduler = DependencyWakeScheduler(stream_name=settings.task_event_stream_name)
    consumed = 0
    queued = 0
    replayed = 0
    try:
        messages = await read_task_event_messages(
            redis,
            stream_name=settings.task_event_stream_name,
            group_name=settings.task_event_scheduler_group,
            consumer_name=resolved_consumer,
            claim_idle_ms=settings.task_event_claim_idle_ms,
        )
        for message in messages:
            try:
                async with factory() as session, session.begin():
                    event = await get_task_event(session, message.event_id)
                    result = await scheduler.process_event(session, event)
                await ack_task_event_message(
                    redis,
                    stream_name=settings.task_event_stream_name,
                    group_name=settings.task_event_scheduler_group,
                    message_id=message.message_id,
                )
            except Exception:
                logger.exception(
                    "task event scheduler failed event_id=%s message_id=%s",
                    message.event_id,
                    message.message_id,
                )
                continue
            consumed += 1
            queued += int(result.disposition is DependencyWakeDisposition.QUEUED)
            replayed += int(result.disposition is DependencyWakeDisposition.REPLAY)
        return consumed, queued, replayed
    finally:
        await redis.aclose()
        await engine.dispose()


async def run_forever() -> None:
    settings = get_settings()
    consumer_name = _consumer_name()
    while True:
        try:
            consumed, queued, replayed = await tick(consumer_name=consumer_name)
            if consumed:
                logger.info(
                    "task event scheduler consumed=%d queued=%d replayed=%d",
                    consumed,
                    queued,
                    replayed,
                )
        except Exception:
            logger.exception("task event scheduler tick failed")
        await asyncio.sleep(settings.scheduler_tick_seconds)


def _consumer_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_forever())
