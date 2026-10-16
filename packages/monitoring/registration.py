"""Register source definitions together with their monitoring-owned schedule state."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.storage.service import ensure_source_states
from packages.sources.contracts import SourceDefinition
from packages.sources.registry.service import sync_source_definitions


async def synchronize_monitoring_sources(
    session: AsyncSession,
    definitions: list[SourceDefinition],
    *,
    now: datetime | None = None,
) -> list[str]:
    """Reconcile the complete configured registry in the caller's transaction.

    Existing cursor, health and backoff remain authoritative. PostgreSQL callers
    serialize registry synchronization so overlapping startup/CLI runs cannot
    race to create a new definition or schedule row.
    """
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(714208139026)"))
    source_ids = await sync_source_definitions(session, definitions)
    await session.flush()
    await ensure_source_states(session, source_ids, now=now)
    await session.flush()
    return source_ids
