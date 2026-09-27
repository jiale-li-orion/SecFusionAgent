from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.ingestion.replay import ObservationEnvelopeLoader
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 27, 1, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "trailofbits-research"
)


@pytest.mark.asyncio
async def test_observation_replay_preserves_binary_and_request_metadata() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000000811"
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=SOURCE.source_id,
                    trigger="investigation",
                    parent_run_id=None,
                    query_spec={"filters": {"query": "agent security"}},
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
            trigger=AcquisitionTrigger.INVESTIGATION,
            source_id=SOURCE.source_id,
            external_object_id="report-1",
            body=b"fixed report bytes",
            media_type="text/plain",
            canonical_url="https://example.invalid/report-1",
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "Fixed report", "provider": "example"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            ack = await EvidenceIngress(store, now=lambda: NOW).accept(session, SOURCE, envelope)

        async with factory() as session:
            replay = await ObservationEnvelopeLoader(store).load(session, ack.observation_id)
        assert replay.metadata_complete is True
        assert replay.metadata_recovery is None
        assert replay.envelope.request_metadata == envelope.request_metadata
        assert replay.envelope.content_bytes() == envelope.content_bytes()
        assert replay.envelope.idempotency_key == envelope.idempotency_key
        assert replay.envelope.trigger is AcquisitionTrigger.INVESTIGATION
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_historical_observation_marks_missing_metadata_without_guessing() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = MemoryArtifactStore()
    run_id = "00000000-0000-0000-0000-000000000812"
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
            session.add(
                AcquisitionRunModel(
                    run_id=run_id,
                    source_id=SOURCE.source_id,
                    trigger="scheduled",
                    parent_run_id=None,
                    query_spec={"filters": {"query": "recoverable-query"}},
                    status="success",
                    cursor_in={},
                    cursor_out={},
                    attempt=1,
                    created_at=NOW,
                    started_at=NOW,
                    finished_at=NOW,
                )
            )
        envelope = IngestEnvelope.for_json_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="legacy-1",
            payload={"id": "legacy-1"},
            canonical_url=None,
            published_at=NOW,
            updated_at=NOW,
            external_revision="v1",
            request_metadata={"title": "lost after old schema"},
            observed_at=NOW,
        )
        async with factory() as session, session.begin():
            ack = await EvidenceIngress(store, now=lambda: NOW).accept(session, SOURCE, envelope)
            row = await session.get(ObservationModel, ack.observation_id)
            assert row is not None
            row.request_metadata = {}
            row.request_metadata_captured = False

        async with factory() as session:
            replay = await ObservationEnvelopeLoader(store).load(session, ack.observation_id)
        assert replay.metadata_complete is False
        assert replay.metadata_recovery == "historical_metadata_missing"
        assert "title" not in replay.envelope.request_metadata
        assert replay.envelope.request_metadata["_request_metadata_recovery"] == (
            "historical_metadata_missing"
        )
        assert "_recovered_acquisition_query_spec" not in replay.envelope.request_metadata
        assert replay.envelope.trigger is AcquisitionTrigger.SCHEDULED
    finally:
        await engine.dispose()
