from __future__ import annotations

import asyncio
import logging
import os
import socket

from redis.asyncio import Redis

from apps.runtime_models import register_runtime_models
from apps.worker.celery_app import celery_app
from packages.runtime.execution.recovery import (
    expire_stale_running_tasks,
    recover_queued_role_tasks,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.contracts.models import TaskEventType, TaskRunStatus
from packages.task_runtime.events.redis_stream import (
    ack_task_event_message,
    read_task_event_messages,
)
from packages.task_runtime.scheduler import DependencyWakeDisposition, DependencyWakeScheduler
from packages.task_runtime.storage.service import get_task_event, get_task_run

logger = logging.getLogger(__name__)


async def tick(*, consumer_name: str | None = None) -> tuple[int, int, int, int, int, int, int]:
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
    dispatched = 0
    try:
        retried_runs: list[str] = []
        closed_runs: list[str] = []
        expired_running: list[str] = []
        try:
            async with factory() as session, session.begin():
                retried_runs, closed_runs = await recover_queued_role_tasks(
                    session,
                    stream_name=settings.task_event_stream_name,
                )
                expired_running = await expire_stale_running_tasks(
                    session,
                    stream_name=settings.task_event_stream_name,
                )
        except Exception:
            logger.exception("queued Role recovery failed; continuing task event delivery")
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
                    role_dispatch = await _role_dispatch_for_event(session, event)
                if role_dispatch is not None:
                    task_name, run_id = role_dispatch
                    celery_app.send_task(
                        task_name,
                        args=[run_id],
                        task_id=f"role-run:{run_id}:{event.event_id}",
                    )
                    dispatched += 1
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
        return (
            consumed,
            queued,
            replayed,
            dispatched,
            len(retried_runs),
            len(closed_runs),
            len(expired_running),
        )
    finally:
        await redis.aclose()
        await engine.dispose()


async def run_forever() -> None:
    settings = get_settings()
    consumer_name = _consumer_name()
    while True:
        try:
            consumed, queued, replayed, dispatched, retried, closed, expired_running = await tick(
                consumer_name=consumer_name
            )
            if consumed or retried or closed or expired_running:
                logger.info(
                    "task event scheduler consumed=%d queued=%d replayed=%d "
                    "dispatched=%d recovered=%d queued_expired=%d running_expired=%d",
                    consumed,
                    queued,
                    replayed,
                    dispatched,
                    retried,
                    closed,
                    expired_running,
                )
        except Exception:
            logger.exception("task event scheduler tick failed")
        await asyncio.sleep(settings.scheduler_tick_seconds)


def _consumer_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def _role_dispatch_for_event(session, event) -> tuple[str, str] | None:
    initial_dispatch = event.event_type is TaskEventType.TASK_PATCHED
    recovery_dispatch = (
        event.event_type is TaskEventType.PROGRESS
        and event.producer == "task-runtime-recovery"
        and event.payload_ref == f"role-dispatch-recovery:{event.task_run_id}"
    )
    if not initial_dispatch and not recovery_dispatch:
        return None
    run = await get_task_run(session, event.task_run_id)
    if run.status is not TaskRunStatus.QUEUED:
        return None
    task_name = {
        "EnrichmentRole": "secfusion.enrichment.run",
        "InvestigationRole": "secfusion.investigation.run",
    }.get(run.role_id)
    if task_name is None:
        return None
    return task_name, run.run_id


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_forever())
