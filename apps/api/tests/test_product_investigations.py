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
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        obj = ObjectModel(
            object_id="api-vuln-object",
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-51515",
            properties={"display_name": "CVE-2026-51515"},
            created_revision=revision.revision,
        )
        session.add(obj)
        session.add(
            ExternalIdentifierModel(
                external_identifier_id="api-vuln-cve-id",
                namespace="cve",
                value="CVE-2026-51515",
                object_id=obj.object_id,
            )
        )
    return engine, factory


@pytest.mark.asyncio
async def test_product_investigation_http_contract() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/investigations",
                headers={"X-Request-ID": "product-http-1", "X-Principal": "user:test"},
                json={
                    "cve_id": "CVE-2026-51515",
                    "goal": "Verify fix boundary",
                    "evidence_question": "Which version first contains the fix?",
                    "task_kind": "verify_version_fix",
                },
            )
            assert response.status_code == 202, response.text
            payload = response.json()
            assert payload["status"] == "active"
            assert payload["execution_profile"] == "VERIFY"
            assert response.headers["location"] == (f"/api/v1/investigations/{payload['case_id']}")
            assert response.headers["x-request-id"] == "product-http-1"

            detail = await client.get(
                response.headers["location"], headers={"X-Request-ID": "product-http-2"}
            )
            assert detail.status_code == 200
            assert detail.json()["case_id"] == payload["case_id"]

            page = await client.get("/api/v1/investigations", params={"limit": 1})
            assert page.status_code == 200
            assert page.json()["items"][0]["case_id"] == payload["case_id"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_validation_and_not_found_use_problem_detail() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid = await client.post(
                "/api/v1/investigations",
                headers={"X-Request-ID": "invalid-1"},
                json={"goal": "g", "evidence_question": "q"},
            )
            assert invalid.status_code == 422
            assert invalid.headers["content-type"].startswith("application/problem+json")
            assert invalid.json()["code"] == "validation_error"
            assert invalid.json()["request_id"] == "invalid-1"

            missing = await client.get(
                "/api/v1/investigations/missing-case",
                headers={"X-Request-ID": "missing-1"},
            )
            assert missing.status_code == 404
            assert missing.json()["code"] == "resource_not_found"
            assert missing.json()["request_id"] == "missing-1"
    finally:
        await engine.dispose()
