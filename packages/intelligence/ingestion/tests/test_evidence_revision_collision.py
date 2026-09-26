from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "trailofbits-research"
)


@pytest.mark.asyncio
async def test_same_external_revision_with_changed_content_is_not_silently_replayed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = "00000000-0000-0000-0000-000000000701"
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

        first_envelope = IngestEnvelope.for_binary_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="mutable-advisory",
            body=b"revision body one",
            media_type="text/plain",
            canonical_url="https://example.invalid/advisory",
            published_at=NOW,
            updated_at=NOW,
            external_revision='"stale-etag"',
            observed_at=NOW,
        )
        second_envelope = IngestEnvelope.for_binary_payload(
            acquisition_run_id=run_id,
            trigger=AcquisitionTrigger.SCHEDULED,
            source_id=SOURCE.source_id,
            external_object_id="mutable-advisory",
            body=b"revision body two",
            media_type="text/plain",
            canonical_url="https://example.invalid/advisory",
            published_at=NOW,
            updated_at=NOW,
            external_revision='"stale-etag"',
            observed_at=NOW,
        )
        assert first_envelope.idempotency_key == second_envelope.idempotency_key
        assert first_envelope.content_hash != second_envelope.content_hash

        ingress = EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW)
        async with factory() as session, session.begin():
            first = await ingress.accept(session, SOURCE, first_envelope)
            second = await ingress.accept(session, SOURCE, second_envelope)
        assert first.replay is False
        assert second.replay is False
        assert first.observation_id != second.observation_id

        async with factory() as session, session.begin():
            replay = await ingress.accept(session, SOURCE, second_envelope)
        assert replay.replay is True
        assert replay.observation_id == second.observation_id

        async with factory() as session:
            observations = list(
                await session.scalars(
                    select(ObservationModel).where(
                        ObservationModel.source_id == SOURCE.source_id,
                        ObservationModel.external_object_id == "mutable-advisory",
                    )
                )
            )
            assert len(observations) == 2
            assert {item.content_hash for item in observations} == {
                first_envelope.content_hash,
                second_envelope.content_hash,
            }
            assert len({item.idempotency_key for item in observations}) == 2
            assert (await session.scalar(select(func.count()).select_from(ObservationModel))) == 2
    finally:
        await engine.dispose()
