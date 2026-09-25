from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from redis.asyncio import Redis

from packages.intelligence.incident.contracts import IncidentCandidate, SignalItem


class RedisIncidentSignalStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_signal(self, signal_id: str) -> SignalItem | None:
        raw = await self._redis.get(f"incident:signal:{signal_id}")
        return SignalItem.model_validate_json(raw) if raw is not None else None

    async def put_signal(self, signal: SignalItem, *, ttl_seconds: int) -> None:
        await self._redis.set(
            f"incident:signal:{signal.signal_id}",
            signal.model_dump_json(),
            ex=ttl_seconds,
        )

    async def get_candidate(self, candidate_id: str) -> IncidentCandidate | None:
        raw = await self._redis.get(f"incident:cluster:{candidate_id}")
        return IncidentCandidate.model_validate_json(raw) if raw is not None else None

    async def put_candidate(self, candidate: IncidentCandidate, *, ttl_seconds: int) -> None:
        await self._redis.set(
            f"incident:cluster:{candidate.candidate_id}",
            candidate.model_dump_json(),
            ex=ttl_seconds,
        )

    async def candidate_ids_for_anchor(self, anchor_type: str, value: str) -> set[str]:
        members = cast(
            set[Any],
            await cast(Any, self._redis).smembers(_anchor_key(anchor_type, value)),
        )
        return {item.decode() if isinstance(item, bytes) else str(item) for item in members}

    async def index_candidate_anchor(
        self,
        candidate_id: str,
        anchor_type: str,
        value: str,
        *,
        ttl_seconds: int,
    ) -> None:
        key = _anchor_key(anchor_type, value)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.sadd(key, candidate_id)
            pipe.expire(key, ttl_seconds)
            await pipe.execute()

    async def schedule_watch(self, candidate_id: str, next_poll_at: datetime) -> None:
        await self._redis.zadd(
            "incident:watch",
            {candidate_id: next_poll_at.timestamp()},
        )


def _anchor_key(anchor_type: str, value: str) -> str:
    return f"incident:anchor:{anchor_type}:{value.strip().lower()}"
