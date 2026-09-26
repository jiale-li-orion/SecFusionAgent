from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from celery.contrib.testing.worker import start_worker
from redis.asyncio import Redis
from sqlalchemy import delete, select, text

from apps.worker.celery_app import celery_app
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.hot_cache.contracts import HotBugRecord
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.retrieval.contracts import EmbeddingBatch
from packages.intelligence.retrieval.indexing import DocumentIndexService
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.intelligence.storage.projection_models import CurrentProjectionModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.shared.outbox.service import dispatch_pending_events
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "arxiv-ai-security"
)


class FixedEmbeddingProvider:
    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        return EmbeddingBatch(
            model="integration-fixed",
            version="1",
            dimensions=3,
            vectors=[[1.0, 0.0, float(index)] for index, _ in enumerate(texts)],
        )


@pytest.mark.asyncio
async def test_postgres_fts_pgvector_and_managed_document_roundtrip() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    run_id = str(uuid4())
    external_id = f"integration-{uuid4()}"
    try:
        async with factory() as session:
            await session.begin()
            try:
                await sync_source_definitions(session, [SOURCE])
                session.add(
                    AcquisitionRunModel(
                        run_id=run_id,
                        source_id=SOURCE.source_id,
                        trigger="scheduled",
                        parent_run_id=None,
                        query_spec={},
                        status="success",
                        cursor_in={},
                        cursor_out={},
                        attempt=1,
                        created_at=NOW,
                        started_at=NOW,
                        finished_at=NOW,
                    )
                )
                envelope = IngestEnvelope.for_binary_payload(
                    acquisition_run_id=run_id,
                    trigger=AcquisitionTrigger.SCHEDULED,
                    source_id=SOURCE.source_id,
                    external_object_id=external_id,
                    body=(
                        b"Authentication bypass evidence appears in this managed document. "
                        b"The mitigation requires explicit authentication."
                    ),
                    media_type="text/plain",
                    canonical_url=f"https://example.invalid/{external_id}",
                    published_at=NOW,
                    updated_at=NOW,
                    external_revision="v1",
                    request_metadata={"title": "Integration retrieval probe"},
                    observed_at=NOW,
                )
                managed = await ManagedDocumentService(
                    EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
                    {"text/plain": PlainTextDocumentParser()},
                    now=lambda: NOW,
                ).ingest(session, SOURCE, envelope)
                indexer = DocumentIndexService()
                lexical = await indexer.build_lexical_index(
                    session,
                    document_revision_id=managed.document_revision_id,
                )
                dense = await indexer.build_dense_index(
                    session,
                    document_revision_id=managed.document_revision_id,
                    provider=FixedEmbeddingProvider(),
                )
                assert lexical.indexed_chunk_ids == dense.indexed_chunk_ids

                fts_matches = await session.scalar(
                    text(
                        "SELECT count(*) FROM document_chunks "
                        "WHERE document_revision_id = :revision_id "
                        "AND to_tsvector('simple', coalesce(text, '')) "
                        "@@ plainto_tsquery('simple', 'authentication')"
                    ),
                    {"revision_id": managed.document_revision_id},
                )
                assert int(fts_matches or 0) >= 1

                distance = await session.scalar(
                    text(
                        "SELECT embedding <=> '[1,0,0]'::vector "
                        "FROM document_chunks WHERE document_revision_id = :revision_id "
                        "ORDER BY ordinal LIMIT 1"
                    ),
                    {"revision_id": managed.document_revision_id},
                )
                assert distance is not None
                assert float(distance) == pytest.approx(0.0)

                extension = await session.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                )
                assert extension is not None
            finally:
                await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_redis_hot_cache_and_failure_domains() -> None:
    settings = get_settings()
    hot_client = Redis.from_url(settings.redis_hot_cache_url, decode_responses=True)
    broker_client = Redis.from_url(settings.redis_broker_url, decode_responses=True)
    cache = RedisHotBugCache(hot_client)
    external_id = f"CVE-INTEGRATION-{uuid4()}"
    record = HotBugRecord(
        acquisition_run_id=str(uuid4()),
        source_id="integration-source",
        external_object_id=external_id,
        external_revision="v1",
        fetched_at=NOW,
        updated_at=NOW,
        content_hash="0" * 64,
        raw_payload={"id": external_id},
        projection={"id": external_id},
    )
    try:
        broker_policy = await broker_client.config_get("maxmemory-policy")
        hot_policy = await hot_client.config_get("maxmemory-policy")
        assert broker_policy.get("maxmemory-policy") == "noeviction"
        assert hot_policy.get("maxmemory-policy") == "allkeys-lfu"

        await cache.admit(record, ttl_seconds=30)
        assert await cache.get(record.source_id, external_id) is not None
        ttl = await hot_client.ttl(record.cache_key)
        assert 0 < ttl <= 30

        await cache.pin(record.source_id, external_id)
        assert await hot_client.ttl(record.cache_key) == -1
        await cache.unpin(record.source_id, external_id)
        ttl_after_unpin = await hot_client.ttl(record.cache_key)
        assert 0 < ttl_after_unpin <= 30

        await cache.evict(record.source_id, external_id)
        assert await cache.get(record.source_id, external_id) is None
    finally:
        await cache.evict(record.source_id, external_id)
        await hot_client.aclose()
        await broker_client.aclose()


@pytest.mark.asyncio
async def test_real_outbox_redis_celery_projection_roundtrip_and_retry() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    object_id = str(uuid4())
    event_id = str(uuid4())
    revision_id: int | None = None

    async def fail_publish(topic: str, payload: dict[str, object]) -> None:
        del topic, payload
        raise RuntimeError("integration broker failure before publish")

    async def celery_publish(topic: str, payload: dict[str, object]) -> None:
        if topic != "knowledge.changed":
            raise ValueError(f"unexpected integration topic: {topic}")
        await asyncio.to_thread(
            celery_app.send_task,
            "secfusion.projection.knowledge_changed",
            args=[payload],
        )

    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            revision_id = revision.revision
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Repo",
                    canonical_key=f"integration/repo/{object_id}",
                    properties={"full_name": "integration/test"},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            session.add(
                OutboxEventModel(
                    event_id=event_id,
                    topic="knowledge.changed",
                    aggregate_id=object_id,
                    payload={
                        "revision": revision.revision,
                        "object_ids": [object_id],
                        "claim_ids": [],
                        "relation_ids": [],
                    },
                    status="pending",
                    attempts=0,
                    available_at=NOW,
                )
            )

        async with factory() as session, session.begin():
            delivered = await dispatch_pending_events(session, fail_publish, now=NOW)
            assert delivered == 0
        async with factory() as session:
            event = await session.get(OutboxEventModel, event_id)
            assert event is not None
            assert event.status == "pending"
            assert event.attempts == 1
            assert event.last_error == "RuntimeError: integration broker failure before publish"

        celery_app.loader.import_default_modules()
        with start_worker(
            celery_app,
            perform_ping_check=False,
            queues=["indexing"],
            pool="solo",
            loglevel="WARNING",
        ):
            async with factory() as session, session.begin():
                delivered = await dispatch_pending_events(session, celery_publish, now=NOW)
                assert delivered == 1

            projection = None
            for _ in range(80):
                async with factory() as session:
                    projection = await session.scalar(
                        select(CurrentProjectionModel).where(
                            CurrentProjectionModel.projection_type == "current_repo_security_state",
                            CurrentProjectionModel.subject_id == object_id,
                        )
                    )
                if projection is not None:
                    break
                await asyncio.sleep(0.1)
            assert projection is not None
            assert projection.upstream_revision == revision_id

        async with factory() as session:
            event = await session.get(OutboxEventModel, event_id)
            assert event is not None
            assert event.status == "delivered"
            assert event.attempts == 2
            assert event.last_error is None
            assert event.delivered_at is not None
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                delete(CurrentProjectionModel).where(CurrentProjectionModel.subject_id == object_id)
            )
            await session.execute(
                delete(OutboxEventModel).where(OutboxEventModel.event_id == event_id)
            )
            await session.execute(delete(ObjectModel).where(ObjectModel.object_id == object_id))
            if revision_id is not None:
                await session.execute(
                    delete(KnowledgeRevisionModel).where(
                        KnowledgeRevisionModel.revision == revision_id
                    )
                )
        await engine.dispose()


@pytest.mark.asyncio
async def test_outbox_duplicate_delivery_is_idempotent_after_publish_commit_gap() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    object_id = str(uuid4())
    event_id = str(uuid4())
    revision_id: int | None = None

    async def publish_then_lose_ack(topic: str, payload: dict[str, object]) -> None:
        if topic != "knowledge.changed":
            raise ValueError(f"unexpected integration topic: {topic}")
        await asyncio.to_thread(
            celery_app.send_task,
            "secfusion.projection.knowledge_changed",
            args=[payload],
        )
        # Simulate the broker accepting the message while the dispatcher loses
        # the acknowledgement / DB transaction before marking the outbox row
        # delivered. The row must remain retryable and the consumer must absorb
        # the duplicate delivery.
        raise RuntimeError("integration crash after broker publish")

    async def publish_normally(topic: str, payload: dict[str, object]) -> None:
        if topic != "knowledge.changed":
            raise ValueError(f"unexpected integration topic: {topic}")
        await asyncio.to_thread(
            celery_app.send_task,
            "secfusion.projection.knowledge_changed",
            args=[payload],
        )

    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            revision_id = revision.revision
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Repo",
                    canonical_key=f"integration/duplicate/{object_id}",
                    properties={"full_name": "integration/duplicate"},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            session.add(
                OutboxEventModel(
                    event_id=event_id,
                    topic="knowledge.changed",
                    aggregate_id=object_id,
                    payload={
                        "revision": revision.revision,
                        "object_ids": [object_id],
                        "claim_ids": [],
                        "relation_ids": [],
                    },
                    status="pending",
                    attempts=0,
                    available_at=NOW,
                )
            )

        celery_app.loader.import_default_modules()
        with start_worker(
            celery_app,
            perform_ping_check=False,
            queues=["indexing"],
            pool="solo",
            loglevel="WARNING",
        ):
            async with factory() as session, session.begin():
                delivered = await dispatch_pending_events(
                    session,
                    publish_then_lose_ack,
                    now=NOW,
                )
                assert delivered == 0

            first_projection = None
            for _ in range(80):
                async with factory() as session:
                    first_projection = await session.scalar(
                        select(CurrentProjectionModel).where(
                            CurrentProjectionModel.projection_type == "current_repo_security_state",
                            CurrentProjectionModel.subject_id == object_id,
                        )
                    )
                if first_projection is not None:
                    break
                await asyncio.sleep(0.1)
            assert first_projection is not None
            first_updated_at = first_projection.updated_at
            assert first_projection.upstream_revision == revision_id

            async with factory() as session:
                event = await session.get(OutboxEventModel, event_id)
                assert event is not None
                assert event.status == "pending"
                assert event.attempts == 1
                assert event.last_error == "RuntimeError: integration crash after broker publish"

            async with factory() as session, session.begin():
                delivered = await dispatch_pending_events(session, publish_normally, now=NOW)
                assert delivered == 1

            for _ in range(30):
                await asyncio.sleep(0.1)
                async with factory() as session:
                    event = await session.get(OutboxEventModel, event_id)
                    if event is not None and event.status == "delivered":
                        break
            async with factory() as session:
                event = await session.get(OutboxEventModel, event_id)
                assert event is not None
                assert event.status == "delivered"
                assert event.attempts == 2
                assert event.last_error is None

                projections = list(
                    await session.scalars(
                        select(CurrentProjectionModel).where(
                            CurrentProjectionModel.projection_type == "current_repo_security_state",
                            CurrentProjectionModel.subject_id == object_id,
                        )
                    )
                )
                assert len(projections) == 1
                assert projections[0].upstream_revision == revision_id
                assert projections[0].updated_at == first_updated_at
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                delete(CurrentProjectionModel).where(CurrentProjectionModel.subject_id == object_id)
            )
            await session.execute(
                delete(OutboxEventModel).where(OutboxEventModel.event_id == event_id)
            )
            await session.execute(delete(ObjectModel).where(ObjectModel.object_id == object_id))
            if revision_id is not None:
                await session.execute(
                    delete(KnowledgeRevisionModel).where(
                        KnowledgeRevisionModel.revision == revision_id
                    )
                )
        await engine.dispose()
