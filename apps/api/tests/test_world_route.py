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
    assert isinstance(payload["hourly_series"], list)
