from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from packages.monitoring.registration import synchronize_monitoring_sources
from packages.monitoring.scheduler.service import schedule_due_sources
from packages.monitoring.storage.models import AcquisitionRunModel, SourceStateModel
from packages.monitoring.tests.test_scheduler_and_run_state import _database
from packages.sources.registry.loader import load_source_definitions


@pytest.mark.asyncio
async def test_registration_initializes_new_sources_and_preserves_existing_progress() -> None:
    engine, factory = await _database()
    now = datetime(2026, 10, 16, tzinfo=UTC)
    definitions = load_source_definitions(Path("config/sources"))
    chosen = [d for d in definitions if d.source_id in {"huggingface-security", "rea-project"}]
    try:
        async with factory() as session, session.begin():
            ids = await synchronize_monitoring_sources(session, chosen, now=now)
        assert set(ids) == {"huggingface-security", "rea-project"}
        async with factory() as session, session.begin():
            scheduled = await schedule_due_sources(session, now=now)
            assert len(scheduled) == 1
            run = await session.get(AcquisitionRunModel, scheduled[0])
            assert run is not None and run.source_id == "huggingface-security"
            state = await session.get(SourceStateModel, "huggingface-security")
            assert state is not None
            state.cursor = {"index_hash": "retained-progress"}
            state.consecutive_failures = 3
            state.backoff_until = now + timedelta(hours=1)
            state.last_success_at = now - timedelta(days=1)
            assert state.next_due_at is not None
            original_due = state.next_due_at.replace(tzinfo=UTC)
        async with factory() as session, session.begin():
            await synchronize_monitoring_sources(session, chosen, now=now + timedelta(minutes=1))
            assert await schedule_due_sources(session, now=now + timedelta(minutes=1)) == []
        async with factory() as session:
            states = {x.source_id: x for x in await session.scalars(select(SourceStateModel))}
            state = states["huggingface-security"]
            assert state.cursor == {"index_hash": "retained-progress"}
            assert state.consecutive_failures == 3
            assert state.backoff_until is not None
            assert state.backoff_until.replace(tzinfo=UTC) == now + timedelta(hours=1)
            assert state.next_due_at is not None
            assert state.next_due_at.replace(tzinfo=UTC) == original_due
            assert state.last_success_at is not None
            assert state.last_success_at.replace(tzinfo=UTC) == now - timedelta(days=1)
            assert states["rea-project"].next_due_at is None
    finally:
        await engine.dispose()
