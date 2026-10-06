from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app


@pytest.mark.asyncio
async def test_world_overview_exposes_product_safe_data_plane_snapshot() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/world/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_at"]
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
