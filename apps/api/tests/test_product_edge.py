from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.shared.db import Base


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_health_ready_checks_required_schema_and_health_reports_optional_model() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            live = await client.get("/health/live")
            ready = await client.get("/health/ready")
            health = await client.get("/health")
        assert live.status_code == 200
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}
        assert health.status_code == 200
        assert health.json()["overall"] in {"healthy", "degraded"}
        components = {item["component"]: item for item in health.json()["components"]}
        assert components["postgresql"]["status"] == "healthy"
        assert components["model_provider"]["status"] in {"healthy", "disabled"}
    finally:
        await engine.dispose()


def test_product_openapi_exposes_stable_investigation_contract() -> None:
    schema = create_app().openapi()
    assert "/api/v1/investigations" in schema["paths"]
    assert "/api/v1/investigations/{case_id}" in schema["paths"]
    assert "/api/v1/questions" in schema["paths"]
    assert "/api/v1/decisions/{decision_id}" in schema["paths"]
    post = schema["paths"]["/api/v1/investigations"]["post"]
    assert post["responses"]["202"]["content"]["application/json"]["schema"]
    assert post["responses"]["422"]["content"]["application/json"]["schema"]
    assert "ProblemDetail" in schema["components"]["schemas"]
    assert "InvestigationView" in schema["components"]["schemas"]
    assert "QuestionResultView" in schema["components"]["schemas"]
