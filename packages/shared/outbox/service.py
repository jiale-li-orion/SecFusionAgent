from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.storage.models import OutboxEventModel

OutboxPublisher = Callable[[str, dict[str, object]], Awaitable[None]]


async def dispatch_pending_events(
    session: AsyncSession,
    publisher: OutboxPublisher,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Publish committed outbox events with at-least-once semantics.

    Publication happens while rows are locked. A broker success followed by a
    DB failure can produce a duplicate delivery; consumers must therefore be
    idempotent on the event/run identifier.
    """

    instant = now or datetime.now(UTC)
    statement = (
        select(OutboxEventModel)
        .where(
            OutboxEventModel.status == "pending",
            OutboxEventModel.available_at <= instant,
        )
        .order_by(OutboxEventModel.available_at, OutboxEventModel.event_id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = list(await session.scalars(statement))
    delivered = 0
    for event in events:
        try:
            await publisher(event.topic, event.payload)
        except Exception as exc:
            event.attempts += 1
            event.last_error = f"{type(exc).__name__}: {exc}"[:4000]
            continue
        event.status = "delivered"
        event.delivered_at = instant
        event.attempts += 1
        event.last_error = None
        delivered += 1
    return delivered
