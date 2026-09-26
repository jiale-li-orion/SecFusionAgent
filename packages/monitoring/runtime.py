from __future__ import annotations

import asyncio

import httpx
from redis.asyncio import Redis

from packages.intelligence.documents.parsers import (
    HTMLDocumentParser,
    PDFDocumentParser,
    PlainTextDocumentParser,
)
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.incident.correlator import IncidentCorrelator
from packages.intelligence.incident.factory import create_incident_signal_extractors
from packages.intelligence.incident.ingress import IncidentSignalIngress
from packages.intelligence.incident.promotion import (
    IncidentPromotionPolicy,
    IncidentPromotionService,
)
from packages.intelligence.incident.redis import RedisIncidentSignalStore
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.knowledge.write import EvidenceBackedKnowledgeWriter
from packages.intelligence.normalization.factory import create_hot_bug_normalizer
from packages.intelligence.normalization.hot_bug import HotBugIngress
from packages.intelligence.storage.factory import create_s3_artifact_store
from packages.intelligence.structured.github_repo import GitHubRepoMapper
from packages.intelligence.structured.service import StructuredIndexService
from packages.monitoring.hot_window import HotWindowCollector
from packages.monitoring.incident_signal import IncidentSignalCollector
from packages.monitoring.managed_content import ManagedContentCollector
from packages.monitoring.run_service import (
    classify_source_failure,
    complete_collection_run,
    complete_hot_window_run,
    fail_acquisition_run,
    start_acquisition_run,
)
from packages.monitoring.structured_index import StructuredIndexCollector
from packages.shared.config import Settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.adapters.factory import create_source_adapter
from packages.sources.contracts import RetentionMode
from packages.sources.errors import SourceFetchFailed
from packages.sources.registry.loader import load_source_definitions


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
        async with httpx.AsyncClient(timeout=30.0) as client:
            adapter = create_source_adapter(context.source, client, settings)
            try:
                async with asyncio.timeout(settings.collection_run_timeout_seconds):
                    if context.source.retention_mode is RetentionMode.HOT_WINDOW:
                        redis_client = Redis.from_url(settings.redis_hot_cache_url)
                        cache = RedisHotBugCache(redis_client)
                        normalizer = create_hot_bug_normalizer(context.source)
                        ingress = HotBugIngress(
                            cache,
                            {context.source.adapter_type: normalizer},
                            ttl_seconds=settings.hot_cache_ttl_seconds,
                        )
                        hot_result = await HotWindowCollector(adapter, ingress).collect(
                            context.source,
                            context.state,
                            acquisition_run_id=context.run_id,
                            trigger=context.trigger,
                        )
                        async with factory() as session, session.begin():
                            await complete_hot_window_run(session, run_id, hot_result)
                        return "success" if hot_result.accepted else "no_change"
                    if context.source.retention_mode is RetentionMode.DURABLE_MANAGED:
                        artifact_store = create_s3_artifact_store(settings)
                        await artifact_store.ensure_bucket()
                        managed_service = ManagedDocumentService(
                            EvidenceIngress(artifact_store),
                            {
                                "application/pdf": PDFDocumentParser(),
                                "text/plain": PlainTextDocumentParser(),
                                "text/yaml": PlainTextDocumentParser(),
                                "application/yaml": PlainTextDocumentParser(),
                                "application/x-yaml": PlainTextDocumentParser(),
                                "application/octet-stream": PlainTextDocumentParser(),
                                "text/html": HTMLDocumentParser(),
                                "application/xhtml+xml": HTMLDocumentParser(),
                            },
                        )
                        managed_result = await ManagedContentCollector(
                            adapter,
                            managed_service,
                            factory,
                        ).collect(
                            context.source,
                            context.state,
                            acquisition_run_id=context.run_id,
                            trigger=context.trigger,
                        )
                        async with factory() as session, session.begin():
                            await complete_collection_run(
                                session,
                                run_id,
                                next_cursor=dict(managed_result.next_cursor),
                                accepted_count=len(managed_result.accepted),
                                changed=any(not item.replay for item in managed_result.accepted),
                            )
                        return "success" if managed_result.accepted else "no_change"
                    if context.source.retention_mode is RetentionMode.SELECTIVE_INDEX:
                        artifact_store = create_s3_artifact_store(settings)
                        await artifact_store.ensure_bucket()
                        structured_service = StructuredIndexService(
                            EvidenceIngress(artifact_store),
                            EvidenceBackedKnowledgeWriter(),
                            {"github_repo": GitHubRepoMapper()},
                        )
                        structured_result = await StructuredIndexCollector(
                            adapter,
                            structured_service,
                            factory,
                        ).collect(
                            context.source,
                            context.state,
                            acquisition_run_id=context.run_id,
                            trigger=context.trigger,
                        )
                        async with factory() as session, session.begin():
                            await complete_collection_run(
                                session,
                                run_id,
                                next_cursor=dict(structured_result.next_cursor),
                                accepted_count=len(structured_result.accepted),
                                changed=any(not item.replay for item in structured_result.accepted),
                            )
                        return "success" if structured_result.accepted else "no_change"
                    if context.source.retention_mode is RetentionMode.INCIDENT_SIGNAL:
                        redis_client = Redis.from_url(settings.redis_hot_cache_url)
                        incident_store = RedisIncidentSignalStore(redis_client)
                        incident_ingress = IncidentSignalIngress(
                            IncidentCorrelator(
                                incident_store,
                                ttl_seconds=settings.incident_signal_ttl_seconds,
                            ),
                            create_incident_signal_extractors(),
                        )
                        artifact_store = create_s3_artifact_store(settings)
                        await artifact_store.ensure_bucket()
                        promotion = IncidentPromotionService(
                            incident_store,
                            EvidenceIngress(artifact_store),
                            IncidentPromotionPolicy(),
                        )
                        source_definitions = {
                            item.source_id: item
                            for item in load_source_definitions(settings.source_registry_path)
                        }
                        incident_result = await IncidentSignalCollector(
                            adapter,
                            incident_ingress,
                            promotion,
                            factory,
                            source_definitions,
                        ).collect(
                            context.source,
                            context.state,
                            acquisition_run_id=context.run_id,
                            trigger=context.trigger,
                        )
                        async with factory() as session, session.begin():
                            await complete_collection_run(
                                session,
                                run_id,
                                next_cursor=dict(incident_result.next_cursor),
                                accepted_count=len(incident_result.accepted),
                                changed=any(
                                    item.material_change for item in incident_result.accepted
                                ),
                            )
                        return "success" if incident_result.accepted else "no_change"
                    raise ValueError(
                        "collection runtime does not yet support retention_mode="
                        f"{context.source.retention_mode.value}"
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

        raise RuntimeError("collection runtime reached an invalid fallthrough")
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        await engine.dispose()
