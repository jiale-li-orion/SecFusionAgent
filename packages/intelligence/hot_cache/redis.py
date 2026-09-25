from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, cast

from redis.asyncio import Redis

from packages.intelligence.hot_cache.contracts import HotBugRecord


class RedisHotBugCache:
    UPDATED_KEY = "bug:updated"
    ACCESS_KEY = "bug:access"
    ACTIVE_KEY = "bug:active"
    PINNED_KEY = "bug:pinned"
    TTL_KEY = "bug:ttl"

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, source_id: str, external_object_id: str) -> HotBugRecord | None:
        key = _bug_key(source_id, external_object_id)
        payload = await self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return HotBugRecord.model_validate_json(payload)

    async def admit(self, record: HotBugRecord, *, ttl_seconds: int) -> None:
        updated_score = (record.updated_at or record.fetched_at).timestamp()
        pinned = await cast(
            Awaitable[Any], self._client.sismember(self.PINNED_KEY, record.cache_key)
        )
        pipeline = self._client.pipeline(transaction=True)
        if pinned:
            pipeline.set(record.cache_key, record.model_dump_json())
        else:
            pipeline.set(record.cache_key, record.model_dump_json(), ex=ttl_seconds)
        pipeline.zadd(self.UPDATED_KEY, {record.cache_key: updated_score})
        pipeline.zadd(self.ACCESS_KEY, {record.cache_key: 0.0}, nx=True)
        pipeline.hset(self.TTL_KEY, record.cache_key, str(ttl_seconds))
        await pipeline.execute()

    async def touch(self, source_id: str, external_object_id: str) -> None:
        key = _bug_key(source_id, external_object_id)
        await cast(Awaitable[Any], self._client.zincrby(self.ACCESS_KEY, 1.0, key))

    async def pin(self, source_id: str, external_object_id: str) -> None:
        key = _bug_key(source_id, external_object_id)
        pipeline = self._client.pipeline(transaction=True)
        pipeline.sadd(self.PINNED_KEY, key)
        pipeline.persist(key)
        await pipeline.execute()

    async def unpin(self, source_id: str, external_object_id: str) -> None:
        key = _bug_key(source_id, external_object_id)
        ttl = await cast(Awaitable[Any], self._client.hget(self.TTL_KEY, key))
        pipeline = self._client.pipeline(transaction=True)
        pipeline.srem(self.PINNED_KEY, key)
        if ttl is not None:
            pipeline.expire(key, int(ttl))
        await pipeline.execute()

    async def evict(self, source_id: str, external_object_id: str) -> None:
        key = _bug_key(source_id, external_object_id)
        pinned = await cast(Awaitable[Any], self._client.sismember(self.PINNED_KEY, key))
        if pinned:
            return
        pipeline = self._client.pipeline(transaction=True)
        pipeline.delete(key)
        pipeline.zrem(self.UPDATED_KEY, key)
        pipeline.zrem(self.ACCESS_KEY, key)
        pipeline.srem(self.ACTIVE_KEY, key)
        pipeline.hdel(self.TTL_KEY, key)
        await pipeline.execute()


def _bug_key(source_id: str, external_object_id: str) -> str:
    return f"bug:{source_id}:{external_object_id}"
