from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import (
    KnowledgeChangeModel,
    KnowledgeRevisionModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 10, 7, 8, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_world_overview_exposes_live_product_data_plane_projection(monkeypatch) -> None:
    import apps.api.routes.world as world_route

    categories = {
        name: {"healthy": 1, "degraded": 0, "blocked": 0}
        for name in (
            "vulnerability",
            "development",
            "academic",
            "vendor",
            "independent",
            "normative",
            "assets",
            "incidents",
        )
    }
    live_payload = {
        "schema_version": "1",
        "generated_at": NOW.isoformat(),
        "source_health": {
            "counts": {"healthy": 8, "degraded": 0, "blocked": 0},
            "healthy_rate": 1.0,
            "overdue_sources": 0,
            "backfill_pending_sources": 0,
            "by_category": categories,
            "sources": [
                {
                    "source_id": "nvd-cves-2",
                    "measurement_category": "vulnerability",
                    "health": "healthy",
                    "latest_scheduled_status": "success",
                    "consecutive_failures": 0,
                    "backfill_pending": False,
                    "last_success_at": NOW.isoformat(),
                    "next_due_at": NOW.isoformat(),
                    "backoff_until": None,
                    "overdue": False,
                    "latest_error_code": None,
                }
            ],
        },
        "rolling_windows": {
            key: {
                "scheduled_monitoring": {
                    "observations": 3,
                    "fresh_external_changes": 2,
                    "canonical_writes": 11,
                    "document_chunks": 4,
                    "document_text_bytes": 128,
                    "fresh_contributing_sources": 1,
                    "fresh_contributing_categories": 1,
                    "fresh_top1_source_share": 1.0,
                    "evidence_integrity_rate": 1.0,
                }
            }
            for key in ("1h", "6h", "24h", "168h")
        },
        "hourly_series": [],
        "category_hourly_series": {},
        "pipeline_state": {
            "outbox": {"delivered": 4},
            "document_index": {"lexical_ready": 2},
        },
        "storage": {
            "artifact_store": {
                "status": "available",
                "public_epoch": {"integrity_rate": 1.0},
            }
        },
    }

    async def fake_data_plane_status() -> dict[str, object]:
        return live_payload

    world_route._world_overview_cache = None
    monkeypatch.setattr(world_route, "data_plane_status", fake_data_plane_status)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/world/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert set(payload["windows"]) >= {"1h", "6h", "24h", "168h"}
    assert payload["source_health"]["healthy"] >= 0
    assert {item["category"] for item in payload["categories"]} >= {
        "vulnerability",
        "development",
        "academic",
        "vendor",
        "independent",
        "normative",
        "assets",
        "incidents",
    }
    assert payload["sources"]
    source = payload["sources"][0]
    assert source["source_id"]
    assert source["measurement_category"] in {
        "vulnerability",
        "development",
        "academic",
        "vendor",
        "independent",
        "normative",
        "assets",
        "incidents",
    }
    assert source["health"] in {"healthy", "degraded", "blocked"}
    assert "last_success_at" in source
    assert "next_due_at" in source
    assert "latest_error_code" in source
    assert isinstance(payload["hourly_series"], list)
    assert "document_chunks" in payload["windows"]["1h"]
    assert "document_text_bytes" in payload["windows"]["1h"]
    assert "fresh_contributing_sources" in payload["windows"]["1h"]
    assert "fresh_contributing_categories" in payload["windows"]["1h"]
    assert "fresh_top1_source_share" in payload["windows"]["1h"]
    assert "evidence_integrity_rate" in payload["windows"]["1h"]
    if payload["hourly_series"]:
        latest = payload["hourly_series"][-1]
        assert "document_chunks" in latest
        assert "fresh_contributing_sources" in latest
        assert "fresh_top1_source_share" in latest


@pytest.mark.asyncio
async def test_world_hot_exposes_ranked_product_safe_hot_bug_view(monkeypatch) -> None:
    from datetime import UTC, datetime
    from typing import Any, cast

    from fakeredis.aioredis import FakeRedis

    import apps.api.routes.world as world_route
    from packages.intelligence.hot_cache.contracts import HotBugRecord
    from packages.intelligence.hot_cache.redis import RedisHotBugCache

    client = FakeRedis()
    cache = RedisHotBugCache(cast(Any, client))
    record = HotBugRecord(
        acquisition_run_id="run-hot",
        source_id="nvd-cves-2",
        external_object_id="CVE-2026-42424",
        external_revision="r2",
        canonical_url="https://example.invalid/CVE-2026-42424",
        fetched_at=datetime(2026, 10, 4, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 4, 8, 50, tzinfo=UTC),
        content_hash="hot-1",
        raw_payload={"private": "not exposed"},
        projection={
            "cve_id": "CVE-2026-42424",
            "description_en": "Example critical vulnerability",
            "cvss_score": 9.8,
            "cvss_severity": "CRITICAL",
        },
        changed_fields=["cvss_score"],
        priority_signals=["critical_severity"],
    )
    await cache.admit(record, ttl_seconds=600)
    await cache.touch(record.source_id, record.external_object_id)
    await cache.pin(record.source_id, record.external_object_id)

    monkeypatch.setattr(world_route.Redis, "from_url", lambda *_args, **_kwargs: client)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/api/v1/world/hot?limit=5")
        detail = await http.get(
            "/api/v1/world/hot/nvd-cves-2/CVE-2026-42424"
        )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["cve_id"] == "CVE-2026-42424"
    assert item["cvss_score"] == 9.8
    assert item["pinned"] is True
    assert item["access_count"] == 1.0
    assert item["priority_signals"] == ["critical_severity"]
    assert "raw_payload" not in item
    assert detail.status_code == 200, detail.text
    detail_item = detail.json()
    assert detail_item["external_object_id"] == "CVE-2026-42424"
    assert detail_item["pinned"] is True
    assert detail_item["access_count"] == 1.0
    assert "raw_payload" not in detail.text


@pytest.mark.asyncio
async def test_world_knowledge_changes_expose_durable_revision_coordinates() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(
            cause_processing_run_id="run-knowledge-1",
            cause_observation_id=None,
            committed_at=NOW,
        )
        session.add(revision)
        await session.flush()
        session.add(
            KnowledgeChangeModel(
                change_id="knowledge-change-product-1",
                revision=revision.revision,
                changed_ids={
                    "objects": ["object:1"],
                    "claims": ["claim:1", "claim:2"],
                    "relations": ["relation:1"],
                },
                cause_processing_run_id="run-knowledge-1",
                cause_observation_id=None,
                committed_at=NOW,
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
            response = await client.get("/api/v1/world/knowledge-changes?limit=4")

        assert response.status_code == 200, response.text
        item = response.json()["items"][0]
        assert item["revision"] == revision.revision
        assert item["object_ids"] == ["object:1"]
        assert item["claim_ids"] == ["claim:1", "claim:2"]
        assert item["relation_ids"] == ["relation:1"]
        assert item["cause_processing_run_id"] == "run-knowledge-1"
        assert item["committed_at"]
    finally:
        await engine.dispose()
