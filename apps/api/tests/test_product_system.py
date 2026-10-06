from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import apps.api.routes.observatory as observatory_route
from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.shared.db import Base


class _RedisProbe:
    async def ping(self) -> bool:
        return True

    async def xpending(self, _stream_name: str, _group_name: str) -> dict[str, int]:
        return {"pending": 3}

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_system_overview_exposes_dependency_and_delivery_health(monkeypatch) -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(
        observatory_route.Redis,
        "from_url",
        lambda *_args, **_kwargs: _RedisProbe(),
    )

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/observatory/system")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["overall"] == "healthy"
        assert {item["component"] for item in body["dependencies"]} == {
            "postgresql",
            "redis_broker",
            "redis_hot_cache",
            "redis_task_bus",
        }
        assert all(item["status"] == "healthy" for item in body["dependencies"])
        assert body["outbox"]["pending_count"] == 0
        assert body["task_event_delivery"]["pending_count"] == 0
        assert body["task_event_stream_pending"] == 3
        assert body["runtime_policy_status"] == "healthy"
        assert body["measurement_boundaries"]["worker_process_health"] == (
            "unavailable_no_heartbeat_contract"
        )
    finally:
        await engine.dispose()
