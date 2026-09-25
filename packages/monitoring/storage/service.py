from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.storage.models import SourceStateModel
from packages.sources.storage.models import SourceModel


async def ensure_source_states(session: AsyncSession, source_ids: list[str]) -> None:
    """Create monitoring-owned runtime state without rewriting existing cursors."""

    now = datetime.now(UTC)
    for source_id in source_ids:
        state = await session.get(SourceStateModel, source_id)
        if state is None:
            source = await session.get(SourceModel, source_id)
            if source is None:
                raise ValueError(f"source definition missing for {source_id}")
            schedule_enabled = source.schedule_policy.get("enabled", True) is not False
            session.add(
                SourceStateModel(
                    source_id=source_id,
                    cursor={},
                    next_due_at=now if schedule_enabled else None,
                    consecutive_failures=0,
                    rate_limit_state={},
                )
            )
