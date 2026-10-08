from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, cast

from redis.asyncio import Redis

from packages.intelligence.hot_cache.contracts import HotBugCacheEntry, HotBugRecord


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

    async def get_entry(
        self,
        source_id: str,
        external_object_id: str,
    ) -> HotBugCacheEntry | None:
        key = _bug_key(source_id, external_object_id)
        pipeline = self._client.pipeline(transaction=False)
        pipeline.get(key)
        pipeline.zscore(self.ACCESS_KEY, key)
        pipeline.zscore(self.UPDATED_KEY, key)
        pipeline.sismember(self.ACTIVE_KEY, key)
        pipeline.sismember(self.PINNED_KEY, key)
        pipeline.ttl(key)
        payload, access, updated, active, pinned, ttl = await pipeline.execute()
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        ttl_value = int(ttl) if ttl is not None and int(ttl) >= 0 else None
        return HotBugCacheEntry(
            record=HotBugRecord.model_validate_json(payload),
            access_count=float(access or 0.0),
            updated_score=float(updated or 0.0),
            active=bool(active),
            pinned=bool(pinned),
            ttl_seconds=ttl_value,
        )

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


    async def list_ranked(self, *, limit: int = 24) -> list[HotBugCacheEntry]:
        if limit < 1:
            return []
        candidate_limit = max(limit * 4, limit)
        updated_keys = await cast(
            Awaitable[Any],
            self._client.zrevrange(self.UPDATED_KEY, 0, candidate_limit - 1),
        )
        access_keys = await cast(
            Awaitable[Any],
            self._client.zrevrange(self.ACCESS_KEY, 0, candidate_limit - 1),
        )
        active_keys = await cast(Awaitable[Any], self._client.smembers(self.ACTIVE_KEY))
        pinned_keys = await cast(Awaitable[Any], self._client.smembers(self.PINNED_KEY))

        candidates = {
            _as_text(key)
            for key in [*updated_keys, *access_keys, *active_keys, *pinned_keys]
        }
        if not candidates:
            return []

        ordered_keys = sorted(candidates)
        pipeline = self._client.pipeline(transaction=False)
        for key in ordered_keys:
            pipeline.get(key)
            pipeline.zscore(self.ACCESS_KEY, key)
            pipeline.zscore(self.UPDATED_KEY, key)
            pipeline.sismember(self.ACTIVE_KEY, key)
            pipeline.sismember(self.PINNED_KEY, key)
            pipeline.ttl(key)
        raw = await pipeline.execute()

        entries: list[HotBugCacheEntry] = []
        stride = 6
        for index, _key in enumerate(ordered_keys):
            payload, access, updated, active, pinned, ttl = raw[
                index * stride : (index + 1) * stride
            ]
            if payload is None:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            record = HotBugRecord.model_validate_json(payload)
            ttl_value = int(ttl) if ttl is not None and int(ttl) >= 0 else None
            entries.append(
                HotBugCacheEntry(
                    record=record,
                    access_count=float(access or 0.0),
                    updated_score=float(updated or 0.0),
                    active=bool(active),
                    pinned=bool(pinned),
                    ttl_seconds=ttl_value,
                )
            )

        entries.sort(
            key=lambda item: (
                item.pinned,
                item.active,
                item.access_count,
                item.updated_score,
                item.record.cache_key,
            ),
            reverse=True,
        )
        return entries[:limit]

    async def resident_count(self) -> int:
        """Count resident payloads; sorted-set membership can outlive a TTL."""
        count = 0
        cursor = 0
        seen: set[str] = set()
        metadata = {self.UPDATED_KEY, self.ACCESS_KEY, self.ACTIVE_KEY,
                    self.PINNED_KEY, self.TTL_KEY}
        while True:
            cursor, keys = await self._client.scan(cursor, match="bug:*", count=1000)
            records = {_as_text(key) for key in keys} - metadata - seen
            seen.update(records)
            if records:
                count += int(await self._client.exists(*records))
            if cursor == 0:
                return count

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


def _as_text(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _bug_key(source_id: str, external_object_id: str) -> str:
    return f"bug:{source_id}:{external_object_id}"
