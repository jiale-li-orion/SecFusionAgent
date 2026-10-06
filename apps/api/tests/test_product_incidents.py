from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_product_incident_reads_durable_timeline_and_source_links() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        revision = IncidentRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        incident = SecurityIncidentModel(
            incident_id="incident-product-1",
            candidate_id="candidate-product-1",
            incident_type="supply-chain-compromise",
            lifecycle="active",
            promotion_reason="independent_corroboration",
            current_summary="Maintainer account compromise linked to malicious release.",
            watch_state={"watch_priority": 90, "next_poll": "2026-10-05T13:00:00+00:00"},
            created_revision=revision.revision,
            current_revision=revision.revision,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(incident)
        session.add(
            IncidentTimelineEventModel(
                event_id="incident-event-1",
                incident_id=incident.incident_id,
                signal_id="signal-1",
                event_time=NOW,
                observed_at=NOW,
                event_type="malicious-release",
                summary="Package release contained malicious payload.",
                source_role="forensic",
                claim_refs=["claim:test"],
                evidence_refs=["evidence:test"],
                supersedes_event_id=None,
                created_revision=revision.revision,
            )
        )
        session.add(
            IncidentSourceLinkModel(
                source_link_id="incident-source-1",
                incident_id=incident.incident_id,
                observation_id="observation-test-1",
                source_id="forensic-feed",
                source_family="forensic",
                upstream_source="upstream-a",
                independence_key="forensic-feed",
                source_role="forensic",
                created_revision=revision.revision,
            )
        )

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            listing = await client.get("/api/v1/incidents?limit=10")
            detail = await client.get("/api/v1/incidents/incident-product-1")
        assert listing.status_code == 200, listing.text
        assert detail.status_code == 200, detail.text
        listed = listing.json()["items"][0]
        assert listed["incident_id"] == "incident-product-1"
        assert listed["timeline_event_count"] == 1
        assert listed["source_link_count"] == 1
        assert listed["source_diversity_count"] == 1
        body = detail.json()
        assert body["incident"]["promotion_reason"] == "independent_corroboration"
        assert body["timeline"][0]["event_type"] == "malicious-release"
        assert body["timeline"][0]["evidence_refs"] == ["evidence:test"]
        assert body["sources"][0]["source_id"] == "forensic-feed"
    finally:
        await engine.dispose()
