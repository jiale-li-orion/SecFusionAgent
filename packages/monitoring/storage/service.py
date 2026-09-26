from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.storage.models import SourceStateModel
from packages.sources.storage.models import SourceModel


async def ensure_source_states(
    session: AsyncSession,
    source_ids: list[str],
    *,
    now: datetime | None = None,
) -> None:
    """Create/reconcile monitoring-owned scheduling state without rewriting cursors."""

    instant = now or datetime.now(UTC)
    for source_id in source_ids:
        state = await session.get(SourceStateModel, source_id)
        source = await session.get(SourceModel, source_id)
        if source is None:
            raise ValueError(f"source definition missing for {source_id}")
        schedule_enabled = source.schedule_policy.get("enabled", True) is not False
        if state is None:
            session.add(
                SourceStateModel(
                    source_id=source_id,
                    cursor={},
                    next_due_at=instant if schedule_enabled else None,
                    consecutive_failures=0,
                    rate_limit_state={},
                )
            )
            continue
        if not schedule_enabled:
            state.next_due_at = None
        elif state.next_due_at is None:
            state.next_due_at = instant
