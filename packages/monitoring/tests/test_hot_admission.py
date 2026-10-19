import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.monitoring.hot_admission import HotAdmissionReceiptService
from packages.monitoring.hot_window import HotWindowCollector
from packages.monitoring.run_service import classify_source_failure, fail_acquisition_run
from packages.monitoring.storage import models
from packages.shared.db import Base
from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    DiscoveryBatch,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
    SourceState,
)
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "nvd-cves-2"
)


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'receipts.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda connection: Base.metadata.create_all(
                connection,
                tables=[
                    Base.metadata.tables[SourceModel.__tablename__],
                    Base.metadata.tables[models.SourceStateModel.__tablename__],
                    Base.metadata.tables[models.AcquisitionRunModel.__tablename__],
                    Base.metadata.tables[models.HotAdmissionReceiptModel.__tablename__],
                ],
            )
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        await sync_source_definitions(session, [SOURCE])
        session.add(models.SourceStateModel(source_id=SOURCE.source_id, cursor={"old": True}))
        for run_id in ("first", "replay"):
            session.add(
                models.AcquisitionRunModel(
                    run_id=run_id,
                    source_id=SOURCE.source_id,
                    trigger="scheduled",
                    status="running",
                    created_at=NOW,
                    started_at=NOW,
                )
            )
    try:
        yield sessions
    finally:
        await engine.dispose()


def _envelope(object_id="CVE-2026-42424", revision="v1", run_id="first"):
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=SOURCE.source_id,
        external_object_id=object_id,
        payload={"cve": {"id": object_id, "descriptions": [], "references": []}},
        canonical_url=None,
        published_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(hours=1),
        external_revision=revision,
        observed_at=NOW - timedelta(seconds=2),
    )


def _ingress(cache):
    return HotBugIngress(cache, {"nvd": NVDHotBugNormalizer()}, ttl_seconds=600, now=lambda: NOW)


@pytest.mark.asyncio
async def test_replay_preserves_first_receipt_and_updates_keep_separate_versions(factory):
    service = HotAdmissionReceiptService(factory)
    redis = FakeRedis()
    try:
        ingress = _ingress(RedisHotBugCache(redis))
        first = _envelope()
        result = await ingress.accept(SOURCE, first)
        await service.record(
            SOURCE, first, result, cursor_in={}, cursor_out={"backfill_pending": True}
        )
        replay = first.model_copy(update={"acquisition_run_id": "replay", "observed_at": NOW})
        # Even supplied older clocks on replay must never backdate the retained receipt.
        for timestamp in (NOW + timedelta(hours=1), NOW - timedelta(days=2)):
            await service.record(
                SOURCE,
                replay,
                result.model_copy(update={"available_at": timestamp}),
                cursor_in={"backfill_pending": True},
                cursor_out={},
            )
        update = _envelope(revision="v2", run_id="replay")
        await service.record(
            SOURCE, update, await ingress.accept(SOURCE, update), cursor_in={}, cursor_out={}
        )
        async with factory() as session:
            receipts = list(await session.scalars(select(models.HotAdmissionReceiptModel)))
            assert len(receipts) == 2
            original = next(row for row in receipts if row.external_revision == "v1")
            assert original.acquisition_run_id == "first"
            assert original.available_at.replace(tzinfo=UTC) == NOW
            assert original.fetched_at.replace(tzinfo=UTC) == first.observed_at
            assert original.published_at.replace(tzinfo=UTC) == first.published_at
            assert original.updated_at.replace(tzinfo=UTC) == first.updated_at
            assert original.input_backfill_pending is False
            assert original.output_backfill_pending is True
            source = await session.get(SourceModel, SOURCE.source_id)
            assert original.source_definition_hash == source.definition_hash
            assert original.content_hash == first.content_hash
            assert original.trigger == "scheduled"
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_concurrent_hash_replays_are_idempotent_and_revision_identity_is_namespaced(factory):
    service = HotAdmissionReceiptService(factory)
    redis = FakeRedis()
    try:
        ingress = _ingress(RedisHotBugCache(redis))
        envelope = _envelope(revision=None)
        result = await ingress.accept(SOURCE, envelope)
        await asyncio.gather(
            *(
                service.record(SOURCE, envelope, result, cursor_in={}, cursor_out={})
                for _ in range(8)
            )
        )
        explicit = envelope.model_copy(update={"external_revision": envelope.content_hash})
        await service.record(
            SOURCE, explicit, await ingress.accept(SOURCE, explicit), cursor_in={}, cursor_out={}
        )
        changed = _envelope(revision=None).model_copy(update={"content_hash": "f" * 64})
        await service.record(
            SOURCE, changed, await ingress.accept(SOURCE, changed), cursor_in={}, cursor_out={}
        )
        async with factory() as session:
            receipts = list(await session.scalars(select(models.HotAdmissionReceiptModel)))
            assert len(receipts) == 3
            assert len({row.receipt_id for row in receipts}) == 3
    finally:
        await redis.aclose()


class FixtureAdapter:
    def __init__(self, *, fail_on=None):
        self.fail_on = fail_on
        self.fetched = []

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        return DiscoveryBatch(
            items=[DiscoveredRef(external_object_id=f"CVE-2026-4000{i}") for i in range(3)],
            next_cursor={"backfill_pending": True, "checkpoint": "new"},
        )

    async def fetch(self, source, ref, *, acquisition_run_id, trigger):
        self.fetched.append(ref.external_object_id)
        if self.fail_on == len(self.fetched) - 1:
            raise RuntimeError("provider failed after an admitted item")
        return _envelope(ref.external_object_id, run_id=acquisition_run_id)

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        raise NotImplementedError


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["fetch", "receipt"])
async def test_partial_failure_preserves_receipt_without_advancing_cursor(factory, failure):
    service = HotAdmissionReceiptService(factory)
    adapter = FixtureAdapter(fail_on=1 if failure == "fetch" else None)
    redis = FakeRedis()
    cache = RedisHotBugCache(redis)
    if failure == "receipt":
        async with factory() as session, session.begin():
            await session.execute(
                text("""
                CREATE TRIGGER reject_receipt BEFORE INSERT ON hot_admission_receipts
                WHEN NEW.external_object_id = 'CVE-2026-40001'
                BEGIN SELECT RAISE(ABORT, 'receipt storage failed'); END
            """)
            )
    state = SourceState(cursor={"old": True})
    try:
        with pytest.raises((RuntimeError, IntegrityError)) as failed:
            await HotWindowCollector(adapter, _ingress(cache), service).collect(
                SOURCE, state, acquisition_run_id="first"
            )
        async with factory() as session, session.begin():
            await fail_acquisition_run(session, "first", classify_source_failure(failed.value))
        async with factory() as session:
            receipts = list(await session.scalars(select(models.HotAdmissionReceiptModel)))
            assert len(receipts) == 1
            assert receipts[0].external_object_id == "CVE-2026-40000"
            assert receipts[0].output_backfill_pending is True
            stored_state = await session.get(models.SourceStateModel, SOURCE.source_id)
            run = await session.get(models.AcquisitionRunModel, "first")
            assert stored_state.cursor == {"old": True}
            assert run.status == "internal_error"
            assert run.cursor_out == {}
        assert state.cursor == {"old": True}
        assert len(adapter.fetched) == 2
        assert await cache.get(SOURCE.source_id, "CVE-2026-40000") is not None
        if failure == "receipt":
            assert await cache.get(SOURCE.source_id, "CVE-2026-40001") is not None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_receipt_rejects_ambiguous_naive_timestamps(factory):
    service = HotAdmissionReceiptService(factory)
    redis = FakeRedis()
    try:
        envelope = _envelope().model_copy(update={"published_at": NOW.replace(tzinfo=None)})
        result = await _ingress(RedisHotBugCache(redis)).accept(SOURCE, envelope)
        with pytest.raises(ValueError, match="timezone"):
            await service.record(SOURCE, envelope, result, cursor_in={}, cursor_out={})
    finally:
        await redis.aclose()
