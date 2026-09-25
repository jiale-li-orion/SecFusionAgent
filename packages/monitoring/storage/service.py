from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.storage.models import SourceStateModel


async def ensure_source_states(session: AsyncSession, source_ids: list[str]) -> None:
    """Create monitoring-owned runtime state without rewriting existing cursors."""

    now = datetime.now(UTC)
    for source_id in source_ids:
        state = await session.get(SourceStateModel, source_id)
        if state is None:
            session.add(
                SourceStateModel(
                    source_id=source_id,
                    cursor={},
                    next_due_at=now,
                    consecutive_failures=0,
                    rate_limit_state={},
                )
            )
