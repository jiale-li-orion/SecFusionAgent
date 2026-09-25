from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from redis.asyncio import Redis

from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.shared.config import get_settings
from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceState
from packages.sources.registry.loader import load_source_definitions


async def _run(limit: int) -> None:
    settings = get_settings()
    definitions = load_source_definitions(Path("config/sources"))
    source = next(item for item in definitions if item.adapter_type == "nvd")
    redis_client = Redis.from_url(settings.redis_hot_cache_url)
    cache = RedisHotBugCache(redis_client)
    ingress = HotBugIngress(
        cache,
        {"nvd": NVDHotBugNormalizer()},
        ttl_seconds=settings.hot_cache_ttl_seconds,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        adapter = NVDAdapter(client, api_key=settings.nvd_api_key)
        batch = await adapter.discover(source, SourceState())
        accepted = 0
        for ref in batch.items[:limit]:
            envelope = await adapter.fetch(
                source,
                ref,
                acquisition_run_id=str(uuid4()),
                trigger=AcquisitionTrigger.SCHEDULED,
            )
            result = await ingress.accept(source, envelope)
            print(
                result.external_object_id,
                result.external_revision,
                result.changed_fields,
                result.priority_signals,
            )
            accepted += 1
    await redis_client.aclose()
    print(f"accepted {accepted} NVD records into the hot working set")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe NVD -> Redis hot bug ingestion")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    main()
