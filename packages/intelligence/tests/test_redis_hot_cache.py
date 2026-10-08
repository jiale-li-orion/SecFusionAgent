from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fakeredis.aioredis import FakeRedis

from packages.intelligence.hot_cache.contracts import HotBugRecord
from packages.intelligence.hot_cache.redis import RedisHotBugCache


@pytest.mark.asyncio
async def test_redis_hot_cache_keeps_frequency_and_pin_separate_from_ttl() -> None:
    client = FakeRedis()
    cache = RedisHotBugCache(cast(Any, client))
    record = HotBugRecord(
        acquisition_run_id="run-1",
        source_id="nvd-cves-2",
        external_object_id="CVE-2026-42424",
        external_revision="r1",
        fetched_at=datetime(2026, 9, 25, 2, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 25, 1, 45, tzinfo=UTC),
        content_hash="abc",
        raw_payload={"cve": {"id": "CVE-2026-42424"}},
        projection={"cve_id": "CVE-2026-42424"},
    )

    await cache.admit(record, ttl_seconds=600)
    assert await cache.get(record.source_id, record.external_object_id) == record
    assert await client.ttl(record.cache_key) > 0
    assert await client.zscore(cache.ACCESS_KEY, record.cache_key) == 0.0

    await cache.touch(record.source_id, record.external_object_id)
    assert await client.zscore(cache.ACCESS_KEY, record.cache_key) == 1.0

    await cache.pin(record.source_id, record.external_object_id)
    assert await client.ttl(record.cache_key) == -1
    await cache.evict(record.source_id, record.external_object_id)
    assert await cache.get(record.source_id, record.external_object_id) == record

    await cache.unpin(record.source_id, record.external_object_id)
    assert await client.ttl(record.cache_key) > 0
    await cache.evict(record.source_id, record.external_object_id)
    assert await cache.get(record.source_id, record.external_object_id) is None

    await client.aclose()


@pytest.mark.asyncio
async def test_redis_hot_cache_ranked_read_uses_existing_hot_signals() -> None:
    client = FakeRedis()
    cache = RedisHotBugCache(cast(Any, client))

    def record(cve_id: str, *, hour: int) -> HotBugRecord:
        return HotBugRecord(
            acquisition_run_id=f"run-{cve_id}",
            source_id="nvd-cves-2",
            external_object_id=cve_id,
            fetched_at=datetime(2026, 9, 25, hour, 0, tzinfo=UTC),
            updated_at=datetime(2026, 9, 25, hour, 0, tzinfo=UTC),
            content_hash=cve_id,
            raw_payload={"cve": {"id": cve_id}},
            projection={"cve_id": cve_id, "cvss_score": 9.8},
        )

    first = record("CVE-2026-10001", hour=1)
    second = record("CVE-2026-10002", hour=2)
    third = record("CVE-2026-10003", hour=3)
    for item in (first, second, third):
        await cache.admit(item, ttl_seconds=600)

    await cache.touch(first.source_id, first.external_object_id)
    await cache.touch(first.source_id, first.external_object_id)
    # redis-py declares SADD as ``Awaitable[int] | int``, so mypy cannot prove
    # the fake client returns an awaitable. The fake is async at runtime.
    await cast(Any, client.sadd(cache.ACTIVE_KEY, second.cache_key))
    await cache.pin(third.source_id, third.external_object_id)

    entries = await cache.list_ranked(limit=3)

    assert [entry.record.external_object_id for entry in entries] == [
        "CVE-2026-10003",
        "CVE-2026-10002",
        "CVE-2026-10001",
    ]
    assert entries[0].pinned is True
    assert entries[1].active is True
    assert entries[2].access_count == 2.0

    await client.aclose()


@pytest.mark.asyncio
async def test_resident_count_excludes_metadata_and_expired_payloads() -> None:
    client = FakeRedis()
    cache = RedisHotBugCache(cast(Any, client))
    await client.set('bug:nvd:resident', '{}')
    await client.zadd(cache.UPDATED_KEY, {'bug:nvd:expired': 1, 'bug:nvd:resident': 2})
    await cast(Any, client).sadd(cache.PINNED_KEY, 'bug:nvd:expired')
    assert await cache.resident_count() == 1
    await cast(Any, client).delete('bug:nvd:resident')
    assert await cache.resident_count() == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_find_cve_reaches_resident_record_outside_ranked_window() -> None:
    client = FakeRedis()
    cache = RedisHotBugCache(cast(Any, client))

    def record(cve_id: str, source_id: str, hour: int) -> HotBugRecord:
        return HotBugRecord(
            acquisition_run_id=f"run-{source_id}-{cve_id}",
            source_id=source_id,
            external_object_id=cve_id,
            fetched_at=datetime(2026, 9, 25, hour, 0, tzinfo=UTC),
            updated_at=datetime(2026, 9, 25, hour, 0, tzinfo=UTC),
            content_hash=f"{source_id}-{cve_id}",
            raw_payload={"cve": {"id": cve_id}},
            projection={"cve_id": cve_id},
        )

    older = record("CVE-2026-42424", "nvd-cves-2", 1)
    newer = record("CVE-2026-42424", "cve-program", 2)
    latest = record("CVE-2026-99999", "nvd-cves-2", 3)
    for item in (older, newer, latest):
        await cache.admit(item, ttl_seconds=600)

    assert [entry.record.external_object_id for entry in await cache.list_ranked(limit=1)] == [
        latest.external_object_id
    ]
    found = await cache.find_cve("cve-2026-42424")
    assert [item.record.source_id for item in found] == ["cve-program", "nvd-cves-2"]
    assert await cache.find_cve("CVE-2026-99998") == []
    await client.aclose()
