from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.intelligence.hot_cache.contracts import HotNormalizationResult
from packages.monitoring.hot_window import HotWindowCollectionResult
from packages.monitoring.run_service import (
    complete_hot_window_run,
    recover_stale_acquisition_runs,
    start_acquisition_run,
)
from packages.monitoring.scheduler.service import schedule_due_sources
from packages.monitoring.storage.models import AcquisitionRunModel, SourceStateModel
from packages.monitoring.storage.service import ensure_source_states
from packages.shared.db import Base
from packages.shared.outbox.service import dispatch_pending_events
from packages.shared.storage.models import OutboxEventModel
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.sources.storage.models import SourceModel


async def _database() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_scheduler_outbox_and_cursor_commit_are_transactional() -> None:
    engine, factory = await _database()
    now = datetime(2026, 9, 25, 4, 0, tzinfo=UTC)
    definitions = load_source_definitions(Path("config/sources"))
    try:
        async with factory() as session, session.begin():
            source_ids = await sync_source_definitions(session, definitions)
            await ensure_source_states(session, source_ids)
        async with factory() as session, session.begin():
            state = await session.get(SourceStateModel, "nvd-cves-2")
            assert state is not None
            state.next_due_at = now - timedelta(seconds=1)

        async with factory() as session, session.begin():
            run_ids = await schedule_due_sources(session, now=now)
        assert len(run_ids) == 1
        run_id = run_ids[0]

        async with factory() as session:
            run = await session.get(AcquisitionRunModel, run_id)
            state = await session.get(SourceStateModel, "nvd-cves-2")
            outbox = await session.scalar(
                select(OutboxEventModel).where(OutboxEventModel.aggregate_id == run_id)
            )
            assert run is not None and run.status == "queued"
            assert run.started_at is None
            assert state is not None
            assert _as_utc(state.next_due_at) == now + timedelta(seconds=900)
            assert outbox is not None and outbox.status == "pending"

        published: list[tuple[str, dict[str, object]]] = []

        async def publisher(topic: str, payload: dict[str, object]) -> None:
            published.append((topic, payload))

        async with factory() as session, session.begin():
            delivered = await dispatch_pending_events(session, publisher, now=now)
        assert delivered == 1
        assert published == [("collection.requested", {"run_id": run_id})]

        async with factory() as session, session.begin():
            context = await start_acquisition_run(session, run_id, now=now + timedelta(seconds=1))
        assert context is not None
        assert context.state.cursor == {}

        result = HotWindowCollectionResult(
            source_id="nvd-cves-2",
            accepted=[
                HotNormalizationResult(
                    source_id="nvd-cves-2",
                    external_object_id="CVE-2026-42424",
                    external_revision="r1",
                    available_at=now + timedelta(seconds=2),
                    changed_fields=["cvss_score"],
                    current_projection_ref="bug:nvd-cves-2:CVE-2026-42424",
                    priority_signals=["material_update"],
                )
            ],
            next_cursor={"last_modified": "2026-09-25T04:00:00+00:00"},
        )
        async with factory() as session, session.begin():
            await complete_hot_window_run(
                session,
                run_id,
                result,
                now=now + timedelta(seconds=3),
            )

        async with factory() as session, session.begin():
            replay = await start_acquisition_run(session, run_id, now=now + timedelta(seconds=4))
            assert replay is None
        async with factory() as session:
            run = await session.get(AcquisitionRunModel, run_id)
            state = await session.get(SourceStateModel, "nvd-cves-2")
            assert run is not None and run.status == "success"
            assert run.cursor_out == {"last_modified": "2026-09-25T04:00:00+00:00"}
            assert state is not None
            assert state.cursor == {"last_modified": "2026-09-25T04:00:00+00:00"}
            assert _as_utc(state.last_change_at) == now + timedelta(seconds=3)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_running_run_is_requeued_with_new_outbox_event() -> None:
    engine, factory = await _database()
    now = datetime(2026, 9, 25, 5, 0, tzinfo=UTC)
    definitions = load_source_definitions(Path("config/sources"))
    try:
        async with factory() as session, session.begin():
            source_ids = await sync_source_definitions(session, definitions)
            await ensure_source_states(session, source_ids)
            source = await session.get(SourceModel, "nvd-cves-2")
            assert source is not None
            session.add(
                AcquisitionRunModel(
                    run_id="stale-run",
                    source_id=source.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={},
                    status="running",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now - timedelta(minutes=30),
                    started_at=now - timedelta(minutes=20),
                )
            )

        async with factory() as session, session.begin():
            recovered = await recover_stale_acquisition_runs(
                session,
                now=now,
                timeout_seconds=15 * 60,
            )
        assert recovered == ["stale-run"]
        async with factory() as session:
            run = await session.get(AcquisitionRunModel, "stale-run")
            events = list(
                await session.scalars(
                    select(OutboxEventModel).where(OutboxEventModel.aggregate_id == "stale-run")
                )
            )
            assert run is not None and run.status == "queued"
            assert run.started_at is None
            assert len(events) == 1
    finally:
        await engine.dispose()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@pytest.mark.asyncio
async def test_schedule_policy_toggle_reconciles_runtime_enabled_and_due_state() -> None:
    engine, factory = await _database()
    now = datetime(2026, 9, 26, 6, 0, tzinfo=UTC)
    definitions = load_source_definitions(Path("config/sources"))
    nvd = next(item for item in definitions if item.source_id == "nvd-cves-2")
    disabled = nvd.model_copy(update={"schedule_policy": {"enabled": False}})
    enabled = nvd.model_copy(update={"schedule_policy": {"enabled": True, "interval_seconds": 900}})
    try:
        async with factory() as session, session.begin():
            ids = await sync_source_definitions(session, [enabled])
            await ensure_source_states(session, ids, now=now)
        async with factory() as session:
            source = await session.get(SourceModel, nvd.source_id)
            state = await session.get(SourceStateModel, nvd.source_id)
            assert source is not None and source.enabled is True
            assert state is not None and _as_utc(state.next_due_at) == now

        async with factory() as session, session.begin():
            ids = await sync_source_definitions(session, [disabled])
            await ensure_source_states(session, ids, now=now + timedelta(minutes=1))
        async with factory() as session:
            source = await session.get(SourceModel, nvd.source_id)
            state = await session.get(SourceStateModel, nvd.source_id)
            assert source is not None and source.enabled is True
            assert state is not None and state.next_due_at is None
        async with factory() as session, session.begin():
            assert await schedule_due_sources(session, now=now + timedelta(hours=1)) == []

        resumed_at = now + timedelta(hours=2)
        async with factory() as session, session.begin():
            ids = await sync_source_definitions(session, [enabled])
            await ensure_source_states(session, ids, now=resumed_at)
        async with factory() as session:
            source = await session.get(SourceModel, nvd.source_id)
            state = await session.get(SourceStateModel, nvd.source_id)
            assert source is not None and source.enabled is True
            assert state is not None and _as_utc(state.next_due_at) == resumed_at
    finally:
        await engine.dispose()
