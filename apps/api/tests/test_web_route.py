from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app


@pytest.mark.asyncio
async def test_operator_frontend_is_mounted_in_dev() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/app/")
        script = await client.get("/app/app.js")

    assert response.status_code == 200
    assert "SecFusion Console" in response.text
    assert script.status_code == 200
    assert "/api/v1/workbench/overview" in script.text
