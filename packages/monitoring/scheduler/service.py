from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.storage.models import AcquisitionRunModel, SourceStateModel
from packages.shared.storage.models import OutboxEventModel
from packages.sources.storage.models import SourceModel

ACTIVE_RUN_STATUSES = ("queued", "running")


async def schedule_due_sources(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> list[str]:
    instant = now or datetime.now(UTC)
    active_run = exists().where(
        AcquisitionRunModel.source_id == SourceStateModel.source_id,
        AcquisitionRunModel.status.in_(ACTIVE_RUN_STATUSES),
    )
    statement = (
        select(SourceModel, SourceStateModel)
        .join(SourceStateModel, SourceStateModel.source_id == SourceModel.source_id)
        .where(
            SourceModel.enabled.is_(True),
            SourceStateModel.next_due_at <= instant,
            or_(
                SourceStateModel.backoff_until.is_(None),
                SourceStateModel.backoff_until <= instant,
            ),
            ~active_run,
        )
        .order_by(SourceStateModel.next_due_at, SourceModel.source_id)
        .limit(limit)
        .with_for_update(skip_locked=True, of=SourceStateModel)
    )
    rows = (await session.execute(statement)).all()
    run_ids: list[str] = []
    for source, state in rows:
        interval_seconds = _schedule_interval_seconds(source.schedule_policy)
        run_id = str(uuid4())
        event_id = str(uuid4())
        session.add(
            AcquisitionRunModel(
                run_id=run_id,
                source_id=source.source_id,
                trigger="scheduled",
                parent_run_id=None,
                query_spec={},
                status="queued",
                cursor_in=dict(state.cursor),
                cursor_out={},
                attempt=0,
                created_at=instant,
            )
        )
        session.add(
            OutboxEventModel(
                event_id=event_id,
                topic="collection.requested",
                aggregate_id=run_id,
                payload={"run_id": run_id},
                status="pending",
                attempts=0,
                available_at=instant,
            )
        )
        state.next_due_at = instant + timedelta(seconds=interval_seconds)
        run_ids.append(run_id)
    return run_ids


def _schedule_interval_seconds(policy: dict[str, Any]) -> int:
    value = policy.get("interval_seconds", 900)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("schedule_policy.interval_seconds must be numeric")
    interval = int(value)
    if interval <= 0:
        raise ValueError("schedule_policy.interval_seconds must be positive")
    return interval
