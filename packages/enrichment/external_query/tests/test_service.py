from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.external_query.service import TimeBoundedEvidenceService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.monitoring.acquisition.service import AcquisitionService
from packages.shared.db import Base
from packages.sources.contracts import (
    AcquisitionTrigger,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
)
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 17, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "crossref-search"
)


class FakeQueryAdapter:
    async def discover(self, source, state):
        raise ValueError("query only")

    async def fetch(self, source, ref, *, acquisition_run_id, trigger):
        raise ValueError("query only")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        query = spec.filters.get("query")
        assert query == "agent security"
        return [
            IngestEnvelope.for_json_payload(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=source.source_id,
                external_object_id="doi:10.1234/example",
                payload={"DOI": "10.1234/example", "title": ["Agent Security"]},
                canonical_url="https://doi.org/10.1234/example",
                published_at=None,
                updated_at=None,
                external_revision=None,
                request_metadata={"provider": "crossref", "query": query},
                observed_at=NOW,
            )
        ]


@pytest.mark.asyncio
async def test_time_bounded_query_is_transient_until_explicitly_promoted() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])

        service = TimeBoundedEvidenceService(
            AcquisitionService(factory, now=lambda: NOW),
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
        )
        results = await service.query(
            SOURCE,
            FakeQueryAdapter(),
            QuerySpec(filters={"query": "agent security"}),
            parent_run_id=None,
        )
        assert len(results) == 1

        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 0

        async with factory() as session, session.begin():
            ack = await service.promote(session, SOURCE, results[0])
            assert ack.replay is False
        async with factory() as session:
            observation = await session.get(ObservationModel, ack.observation_id)
            assert observation is not None
            assert observation.source_id == SOURCE.source_id
            assert observation.external_object_id == "doi:10.1234/example"
    finally:
        await engine.dispose()
