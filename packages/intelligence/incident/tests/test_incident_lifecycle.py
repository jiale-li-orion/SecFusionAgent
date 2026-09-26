from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.intelligence.incident.contracts import (
    GenericNewsSignalExtractor,
    IncidentCandidate,
)
from packages.intelligence.incident.correlator import IncidentCorrelator
from packages.intelligence.incident.ingress import IncidentSignalIngress
from packages.intelligence.incident.promotion import (
    IncidentPromotionPolicy,
    IncidentPromotionService,
)
from packages.intelligence.incident.redis import RedisIncidentSignalStore
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.incident_models import (
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    RetentionMode,
    SourceDefinition,
    SourceRole,
)
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)


def _source(
    source_id: str,
    family: str,
    role: SourceRole,
    upstream: str | None = None,
) -> SourceDefinition:
    return SourceDefinition(
        source_id=source_id,
        adapter_type="generic_news",
        source_class="incident_news",
        authority_scope=["incident_signal"],
        source_role=role,
        source_family=family,
        upstream_source=upstream,
        access_mode="fixture",
        update_semantics="append",
        retention_mode=RetentionMode.INCIDENT_SIGNAL,
        schedule_policy={"enabled": True},
    )


def _envelope(
    source: SourceDefinition,
    run_id: str,
    external_id: str,
    *,
    upstream_source: str | None,
    title: str,
    cve: str,
    observed_at: datetime,
) -> IngestEnvelope:
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=run_id,
        trigger=AcquisitionTrigger.SCHEDULED,
        source_id=source.source_id,
        external_object_id=external_id,
        payload={
            "title": title,
            "summary": title,
            "incident_type": "vulnerability-exploitation",
            "upstream_source": upstream_source,
            "entity_hints": {"project": ["Example AI"]},
            "anchors": {"cve": [cve]},
            "unresolved_questions": ["root cause"],
            "event_type": "reported",
        },
        canonical_url=f"https://example.test/{external_id}",
        published_at=observed_at,
        updated_at=observed_at,
        external_revision=observed_at.isoformat(),
        observed_at=observed_at,
    )


@pytest.mark.asyncio
async def test_upstream_dependency_does_not_create_false_corroboration() -> None:
    redis_client = FakeRedis()
    store = RedisIncidentSignalStore(cast(Any, redis_client))
    correlator = IncidentCorrelator(store, now=lambda: NOW)
    ingress = IncidentSignalIngress(correlator, {"generic_news": GenericNewsSignalExtractor()})
    cve = "CVE-2026-42424"
    blockbeats = _source("blockbeats", "blockbeats", SourceRole.REFERENCE)
    foresight = _source("foresight", "foresight", SourceRole.REFERENCE)
    certik = _source("certik", "certik", SourceRole.FORENSIC)

    first = await ingress.accept(
        blockbeats,
        _envelope(
            blockbeats,
            "run-1",
            "news-1",
            upstream_source="lookonchain",
            title="Example AI vulnerability reportedly exploited",
            cve=cve,
            observed_at=NOW,
        ),
    )
    second = await ingress.accept(
        foresight,
        _envelope(
            foresight,
            "run-2",
            "news-2",
            upstream_source="lookonchain",
            title="Example AI incident update",
            cve=cve,
            observed_at=NOW,
        ),
    )
    candidate = await store.get_candidate(first.incident_candidate_id)
    assert candidate is not None
    assert second.incident_candidate_id == first.incident_candidate_id
    assert candidate.independent_source_count == 1
    signals = [
        item
        for signal_id in candidate.signal_ids
        if (item := await store.get_signal(signal_id)) is not None
    ]
    assert IncidentPromotionPolicy().decide(candidate, signals).eligible is False

    third = await ingress.accept(
        certik,
        _envelope(
            certik,
            "run-3",
            "analysis-1",
            upstream_source=None,
            title="Independent forensic analysis confirms exploitation",
            cve=cve,
            observed_at=NOW,
        ),
    )
    candidate = await store.get_candidate(third.incident_candidate_id)
    assert candidate is not None
    assert candidate.independent_source_count == 2
    signals = [
        item
        for signal_id in candidate.signal_ids
        if (item := await store.get_signal(signal_id)) is not None
    ]
    decision = IncidentPromotionPolicy().decide(candidate, signals)
    assert decision.eligible is True
    assert decision.reason == "independent_corroboration"
    await redis_client.aclose()


def test_independent_sources_on_different_anchors_do_not_corroborate() -> None:
    policy = IncidentPromotionPolicy()
    source_a = _source("source-a", "source-a", SourceRole.REFERENCE)
    source_b = _source("source-b", "source-b", SourceRole.FORENSIC)
    extractor = GenericNewsSignalExtractor()
    signal_a = extractor.extract(
        source_a,
        _envelope(
            source_a,
            "run-a",
            "signal-a",
            upstream_source=None,
            title="First report",
            cve="CVE-2026-42424",
            observed_at=NOW,
        ),
    )
    signal_b = extractor.extract(
        source_b,
        _envelope(
            source_b,
            "run-b",
            "signal-b",
            upstream_source=None,
            title="Different incident",
            cve="CVE-2026-99999",
            observed_at=NOW,
        ),
    )
    candidate = IncidentCandidate(
        candidate_id="candidate",
        incident_type="vulnerability-exploitation",
        anchor_set={"cve": ["CVE-2026-42424", "CVE-2026-99999"]},
        source_diversity=["source-a", "source-b"],
        independent_source_count=2,
        signal_ids=[signal_a.signal_id, signal_b.signal_id],
        last_material_change=NOW,
    )
    assert policy.decide(candidate, [signal_a, signal_b]).eligible is False


@pytest.mark.asyncio
async def test_incident_promotion_persists_selected_evidence_and_timeline() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = FakeRedis()
    store = RedisIncidentSignalStore(cast(Any, redis_client))
    correlator = IncidentCorrelator(store, now=lambda: NOW)
    ingress = IncidentSignalIngress(correlator, {"generic_news": GenericNewsSignalExtractor()})
    source_a = _source("media-a", "media-a", SourceRole.REFERENCE)
    source_b = _source("forensic-b", "forensic-b", SourceRole.FORENSIC)
    sources = {item.source_id: item for item in [source_a, source_b]}

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, list(sources.values()))
            for index, source in enumerate(sources.values(), start=1):
                session.add(
                    AcquisitionRunModel(
                        run_id=f"run-{index}",
                        source_id=source.source_id,
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

        first = await ingress.accept(
            source_a,
            _envelope(
                source_a,
                "run-1",
                "news-1",
                upstream_source=None,
                title="Incident first report",
                cve="CVE-2026-42424",
                observed_at=NOW,
            ),
        )
        await ingress.accept(
            source_b,
            _envelope(
                source_b,
                "run-2",
                "analysis-1",
                upstream_source=None,
                title="Forensic follow-up",
                cve="CVE-2026-42424",
                observed_at=NOW,
            ),
        )

        service = IncidentPromotionService(
            store,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            IncidentPromotionPolicy(),
            now=lambda: NOW,
        )
        async with factory() as session, session.begin():
            result = await service.promote(
                session,
                candidate_id=first.incident_candidate_id,
                sources=sources,
            )
        assert result.replay is False
        assert len(result.observation_ids) == 2
        assert len(result.timeline_event_ids) == 2

        async with factory() as session:
            incident = await session.get(SecurityIncidentModel, result.incident_id)
            assert incident is not None
            assert incident.lifecycle == "active"
            assert incident.promotion_reason == "independent_corroboration"
            assert await _count(session, IncidentTimelineEventModel) == 2
            assert await _count(session, IncidentSourceLinkModel) == 2

        async with factory() as session, session.begin():
            replay = await service.promote(
                session,
                candidate_id=first.incident_candidate_id,
                sources=sources,
            )
        assert replay.replay is True
        async with factory() as session:
            assert await _count(session, SecurityIncidentModel) == 1
            assert await _count(session, IncidentTimelineEventModel) == 2
        await redis_client.aclose()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_promoted_incident_appends_new_material_signal_idempotently() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = FakeRedis()
    store = RedisIncidentSignalStore(cast(Any, redis_client))
    correlator = IncidentCorrelator(store, now=lambda: NOW)
    ingress = IncidentSignalIngress(correlator, {"generic_news": GenericNewsSignalExtractor()})
    source_a = _source("media-a", "media-a", SourceRole.REFERENCE)
    source_b = _source("forensic-b", "forensic-b", SourceRole.FORENSIC)
    source_c = _source("primary-c", "primary-c", SourceRole.PRIMARY)
    sources = {item.source_id: item for item in [source_a, source_b, source_c]}

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, list(sources.values()))
            for index, source in enumerate(sources.values(), start=1):
                session.add(
                    AcquisitionRunModel(
                        run_id=f"append-run-{index}",
                        source_id=source.source_id,
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

        first = await ingress.accept(
            source_a,
            _envelope(
                source_a,
                "append-run-1",
                "news-a",
                upstream_source=None,
                title="Initial report",
                cve="CVE-2026-42424",
                observed_at=NOW,
            ),
        )
        await ingress.accept(
            source_b,
            _envelope(
                source_b,
                "append-run-2",
                "forensic-b",
                upstream_source=None,
                title="Independent forensic confirmation",
                cve="CVE-2026-42424",
                observed_at=NOW,
            ),
        )

        service = IncidentPromotionService(
            store,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            IncidentPromotionPolicy(),
            now=lambda: NOW,
        )
        async with factory() as session, session.begin():
            promoted = await service.promote(
                session,
                candidate_id=first.incident_candidate_id,
                sources=sources,
            )
        assert promoted.replay is False
        initial_revision = promoted.incident_revision

        followup_time = NOW.replace(hour=11)
        followup = await ingress.accept(
            source_c,
            _envelope(
                source_c,
                "append-run-3",
                "primary-update",
                upstream_source=None,
                title="Primary source confirms mitigation in progress",
                cve="CVE-2026-42424",
                observed_at=followup_time,
            ),
        )
        assert followup.material_change is True

        async with factory() as session, session.begin():
            appended = await service.promote(
                session,
                candidate_id=first.incident_candidate_id,
                sources=sources,
            )
        assert appended.replay is False
        assert appended.incident_revision > initial_revision
        assert len(appended.timeline_event_ids) == 1
        assert len(appended.observation_ids) == 1

        async with factory() as session:
            incident = await session.get(SecurityIncidentModel, promoted.incident_id)
            assert incident is not None
            assert incident.current_revision == appended.incident_revision
            assert incident.current_summary == "Primary source confirms mitigation in progress"
            assert await _count(session, IncidentTimelineEventModel) == 3
            assert await _count(session, IncidentSourceLinkModel) == 3

        async with factory() as session, session.begin():
            replay = await service.promote(
                session,
                candidate_id=first.incident_candidate_id,
                sources=sources,
            )
        assert replay.replay is True
        async with factory() as session:
            assert await _count(session, IncidentTimelineEventModel) == 3
            assert await _count(session, IncidentSourceLinkModel) == 3
        await redis_client.aclose()
    finally:
        await engine.dispose()


async def _count(session: AsyncSession, model: type[Any]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
