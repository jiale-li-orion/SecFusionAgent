from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.queries.featured import curated_world_stories
from apps.application.queries.incidents import get_product_incident, list_product_incidents
from apps.runtime_models import register_runtime_models
from packages.intelligence.documents.parsers import PlainTextDocumentParser
from packages.intelligence.documents.service import ManagedDocumentService
from packages.intelligence.incident.curation import (
    CuratedIncident,
    CuratedTimelineNode,
    IncidentCurationService,
)
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.incident_models import (
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.sources.storage.models import SourceModel


@pytest.mark.asyncio
async def test_curated_history_is_retained_atomic_and_replay_safe():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source = next(
        s
        for s in load_source_definitions(Path("config/sources"))
        if s.source_id == "huggingface-security"
    )
    now = datetime.now(UTC)
    run_id = str(uuid4())
    excerpt = "On July 9 the agent accessed an external system during the evaluation."
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [source])
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=source.source_id,
                    trigger="on_demand",
                    status="success",
                    query_spec={},
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )
            await session.flush()
            env = IngestEnvelope.for_binary_payload(
                acquisition_run_id=run_id,
                trigger=AcquisitionTrigger.ON_DEMAND,
                source_id=source.source_id,
                external_object_id="test-history",
                canonical_url="https://huggingface.co/blog/test",
                published_at=None,
                updated_at=None,
                external_revision=None,
                media_type="text/plain",
                body=excerpt.encode(),
                request_metadata={"title": "Evaluation incident"},
            )
            result = await ManagedDocumentService(
                EvidenceIngress(MemoryArtifactStore()), {"text/plain": PlainTextDocumentParser()}
            ).ingest(session, source, env)
        spec = CuratedIncident(
            key="evaluation-incident",
            display_kind="Tool",
            featured_priority=99,
            title="Evaluation incident",
            summary="An external system was accessed during an evaluation.",
            timeline=[
                CuratedTimelineNode(
                    key="access",
                    document_revision_id=result.document_revision_id,
                    summary="The agent accessed an external system.",
                    supporting_excerpt=excerpt,
                    event_time=datetime(2026, 7, 9, tzinfo=UTC),
                    time_basis="reported_date",
                )
            ],
        )
        async with factory() as session, session.begin():
            incident_id, replay = await IncidentCurationService().import_incident(session, spec)
            assert not replay
        async with factory() as session, session.begin():
            assert await IncidentCurationService().import_incident(session, spec) == (
                incident_id,
                True,
            )
            assert (
                await session.scalar(select(func.count()).select_from(IncidentTimelineEventModel))
                == 1
            )
            stories = await curated_world_stories(session, limit=12)
            assert stories[0].kind == "Tool"
            assert stories[0].category == "development"
            assert stories[0].facts["featured_priority"] == 99
            detail = await get_product_incident(session, incident_id)
            assert detail is not None
            assert "timeline_evidence" not in detail.incident.watch_state
            incident = await session.get(SecurityIncidentModel, incident_id)
            assert incident is not None
            assert incident.watch_state["historical_backfill"] is True
            event = await session.scalar(select(IncidentTimelineEventModel))
            assert event is not None
            assert event.event_time.date().isoformat() == "2026-07-09"
            assert event.observed_at.date() == now.date()
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="different reviewed content"):
                await IncidentCurationService().import_incident(
                    session, spec.model_copy(update={"title": "Changed incident title"})
                )
        async with factory() as session, session.begin():
            bad = spec.model_copy(
                update={
                    "key": "unsupported-history",
                    "timeline": [
                        spec.timeline[0].model_copy(
                            update={
                                "supporting_excerpt": (
                                    "This fabricated passage is absent from the retained evidence."
                                )
                            }
                        )
                    ],
                }
            )
            with pytest.raises(ValueError, match="not present"):
                await IncidentCurationService().import_incident(session, bad)
            assert (
                await session.scalar(select(func.count()).select_from(SecurityIncidentModel)) == 1
            )
        async with factory() as session, session.begin():
            bad_time = spec.model_copy(
                update={
                    "key": "false-observed-history",
                    "timeline": [spec.timeline[0].model_copy(update={"time_basis": "observed"})],
                }
            )
            with pytest.raises(ValueError, match="must match retained timestamp"):
                await IncidentCurationService().import_incident(session, bad_time)
        async with factory() as session, session.begin():
            row = await session.get(SourceModel, source.source_id)
            assert row is not None
            row.access_rights = {"classification": "private"}
        async with factory() as session, session.begin():
            assert await get_product_incident(session, incident_id) is None
            assert not (await list_product_incidents(session)).items
            assert not await curated_world_stories(session, limit=12)
            with pytest.raises(ValueError, match="public source"):
                await IncidentCurationService().import_incident(
                    session, spec.model_copy(update={"key": "private-history"})
                )
    finally:
        await engine.dispose()
