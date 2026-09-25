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
