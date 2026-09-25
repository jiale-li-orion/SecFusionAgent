from __future__ import annotations

import asyncio
import logging

from apps.worker.celery_app import celery_app
from packages.monitoring.run_service import recover_stale_acquisition_runs
from packages.monitoring.scheduler.service import schedule_due_sources
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.shared.outbox.service import dispatch_pending_events

logger = logging.getLogger(__name__)


async def _publish(topic: str, payload: dict[str, object]) -> None:
    task_name: str
    args: list[object]
    if topic == "collection.requested":
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("collection.requested payload requires run_id")
        task_name = "secfusion.collection.run"
        args = [run_id]
    elif topic == "knowledge.changed":
        task_name = "secfusion.projection.knowledge_changed"
        args = [payload]
    elif topic == "incident.changed":
        task_name = "secfusion.projection.incident_changed"
        args = [payload]
    elif topic == "enrichment.requested":
        task_name = "secfusion.enrichment.vulnerability"
        args = [payload]
    else:
        raise ValueError(f"unsupported outbox topic: {topic}")
    await asyncio.to_thread(
        celery_app.send_task,
        task_name,
        args=args,
    )


async def tick() -> tuple[int, int, int]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            recovered = await recover_stale_acquisition_runs(
                session,
                timeout_seconds=settings.collection_run_timeout_seconds,
            )
            scheduled = await schedule_due_sources(session)
        async with factory() as session, session.begin():
            delivered = await dispatch_pending_events(session, _publish)
        return len(scheduled), len(recovered), delivered
    finally:
        await engine.dispose()


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            scheduled, recovered, delivered = await tick()
            if scheduled or recovered or delivered:
                logger.info(
                    "scheduler tick scheduled=%d recovered=%d delivered=%d",
                    scheduled,
                    recovered,
                    delivered,
                )
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(settings.scheduler_tick_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_forever())
