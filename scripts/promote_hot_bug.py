from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from redis.asyncio import Redis

from apps.runtime_models import register_runtime_models
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.normalization.factory import create_durable_bug_normalizer
from packages.intelligence.promotion.service import PromotionService
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.registry.loader import load_source_definitions


async def main() -> None:
    register_runtime_models()
    parser = argparse.ArgumentParser(
        description="Promote one hot vulnerability into durable knowledge"
    )
    parser.add_argument("cve_id")
    parser.add_argument("--source-id", default="nvd-cves-2")
    args = parser.parse_args()

    settings = get_settings()
    sources = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}
    source = sources.get(args.source_id)
    if source is None:
        raise SystemExit(f"unknown source_id: {args.source_id}")

    redis = Redis.from_url(settings.redis_hot_cache_url)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = create_s3_artifact_store(settings)
    await store.ensure_bucket()
    service = PromotionService(
        RedisHotBugCache(redis),
        EvidenceIngress(store),
        {source.adapter_type: create_durable_bug_normalizer(source)},
    )
    try:
        async with factory() as session, session.begin():
            result = await service.promote_hot_bug(session, source, args.cve_id.upper())
        print(result.model_dump_json(indent=2))
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
