from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.incident.evidence import IncidentEvidenceAttachmentService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.document_models import InsightCandidateModel
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 19, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "chainalysis-research"
)


@pytest.mark.asyncio
async def test_managed_forensic_document_attaches_to_incident_timeline_idempotently() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = "00000000-0000-0000-0000-000000000301"
    incident_id = "00000000-0000-0000-0000-000000000302"
    try:
        async with factory() as session, session.begin():
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
            initial_revision = IncidentRevisionModel(
                cause_observation_id=None,
                committed_at=NOW,
            )
            session.add(initial_revision)
            await session.flush()
            session.add(
                SecurityIncidentModel(
                    incident_id=incident_id,
                    candidate_id="00000000-0000-0000-0000-000000000303",
                    incident_type="security-incident",
                    lifecycle="active",
                    promotion_reason="analyst_pin",
                    current_summary="Initial report",
                    watch_state={},
                    created_revision=initial_revision.revision,
                    current_revision=initial_revision.revision,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )

        envelope = IngestEnvelope.for_binary_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="chainalysis-follow-up",
            body=(b"Forensic analysis confirms additional fund movement and response activity."),
            media_type="text/plain",
            canonical_url="https://example.invalid/forensic-follow-up",
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "Forensic follow-up"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            managed = await ManagedDocumentService(
                EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
                {"text/plain": PlainTextDocumentParser()},
                now=lambda: NOW,
            ).ingest(session, SOURCE, envelope)
            insight = await session.scalar(
                select(InsightCandidateModel).where(
                    InsightCandidateModel.document_revision_id == managed.document_revision_id
                )
            )
            assert insight is not None
            insight.related_claim_ids = ["claim-from-forensic-analysis"]

        service = IncidentEvidenceAttachmentService(now=lambda: NOW)
        async with factory() as session, session.begin():
            first = await service.attach_document(
                session,
                incident_id=incident_id,
                document_revision_id=managed.document_revision_id,
                event_type="forensic_update",
                summary="Forensic follow-up confirmed additional fund movement.",
            )
        assert first.replay is False

        async with factory() as session:
            incident = await session.get(SecurityIncidentModel, incident_id)
            assert incident is not None
            assert incident.current_revision == first.incident_revision
            link = await session.get(IncidentSourceLinkModel, first.source_link_id)
            assert link is not None
            assert link.source_id == SOURCE.source_id
            assert link.source_role == "forensic"
            event = await session.get(IncidentTimelineEventModel, first.timeline_event_id)
            assert event is not None
            assert event.event_type == "forensic_update"
            assert event.evidence_refs == [first.observation_id]
            assert event.claim_refs == ["claim-from-forensic-analysis"]
            assert await _count(session, IncidentSourceLinkModel) == 1
            assert await _count(session, IncidentTimelineEventModel) == 1
            assert await _count(session, OutboxEventModel) >= 2

        async with factory() as session, session.begin():
            replay = await service.attach_document(
                session,
                incident_id=incident_id,
                document_revision_id=managed.document_revision_id,
                event_type="forensic_update",
                summary="Forensic follow-up confirmed additional fund movement.",
            )
        assert replay.replay is True
        assert replay.timeline_event_id == first.timeline_event_id
        assert replay.source_link_id == first.source_link_id
        async with factory() as session:
            assert await _count(session, IncidentSourceLinkModel) == 1
            assert await _count(session, IncidentTimelineEventModel) == 1
            assert await _count(session, IncidentRevisionModel) == 2
    finally:
        await engine.dispose()


async def _count(session, model) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)
