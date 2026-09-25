from __future__ import annotations

import asyncio

import httpx
from redis.asyncio import Redis

from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.normalization.factory import create_hot_bug_normalizer
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.monitoring.hot_window import HotWindowCollector
from packages.monitoring.run_service import (
    classify_source_failure,
    complete_hot_window_run,
    fail_acquisition_run,
    start_acquisition_run,
)
from packages.shared.config import Settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import RetentionMode
from packages.sources.errors import SourceFetchFailed


async def execute_collection_run(run_id: str, settings: Settings) -> str:
    """Execute one durable acquisition run idempotently."""

    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis_client: Redis | None = None
    try:
        async with factory() as session, session.begin():
            context = await start_acquisition_run(session, run_id)
        if context is None:
            return "ignored"
        if context.source.retention_mode is not RetentionMode.HOT_WINDOW:
            failure = classify_source_failure(
                ValueError(
                    f"collection runtime does not yet support retention_mode="
                    f"{context.source.retention_mode.value}"
                )
            )
            async with factory() as session, session.begin():
                await fail_acquisition_run(session, run_id, failure)
            return failure.status

        redis_client = Redis.from_url(settings.redis_hot_cache_url)
        cache = RedisHotBugCache(redis_client)
        normalizer = create_hot_bug_normalizer(context.source)
        ingress = HotBugIngress(
            cache,
            {context.source.adapter_type: normalizer},
            ttl_seconds=settings.hot_cache_ttl_seconds,
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            adapter = create_source_adapter(context.source, client, settings)
            collector = HotWindowCollector(adapter, ingress)
            try:
                async with asyncio.timeout(settings.collection_run_timeout_seconds):
                    result = await collector.collect(
                        context.source,
                        context.state,
                        acquisition_run_id=context.run_id,
                        trigger=context.trigger,
                    )
            except TimeoutError:
                failure = classify_source_failure(
                    SourceFetchFailed("collection run exceeded its configured timeout"),
                    consecutive_failures=context.state.consecutive_failures,
                )
                async with factory() as session, session.begin():
                    await fail_acquisition_run(session, run_id, failure)
                return failure.status
            except Exception as exc:
                consecutive_failures = context.state.consecutive_failures
                failure = classify_source_failure(
                    exc,
                    consecutive_failures=consecutive_failures,
                )
                async with factory() as session, session.begin():
                    await fail_acquisition_run(session, run_id, failure)
                return failure.status

        async with factory() as session, session.begin():
            await complete_hot_window_run(session, run_id, result)
        return "success" if result.accepted else "no_change"
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()
