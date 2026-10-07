from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
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
from packages.task_runtime.storage.models import TaskContractVersionModel, TaskRunModel

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
            assert payload["origin_scope"] == "product"
            assert payload["can_cancel"] is True
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

            foreign_cancel = await client.post(
                f"/api/v1/investigations/{payload['case_id']}/cancel",
                headers={
                    "X-Request-ID": "product-http-foreign-cancel",
                    "X-Principal": "user:other",
                },
            )
            assert foreign_cancel.status_code == 403, foreign_cancel.text

            cancelled = await client.post(
                f"/api/v1/investigations/{payload['case_id']}/cancel",
                headers={
                    "X-Request-ID": "product-http-cancel",
                    "X-Principal": "user:test",
                },
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
            assert cancelled.json()["can_cancel"] is False

            # Product filtering must happen before pagination, not hide rows in the browser.
            benchmark = await client.post(
                "/api/v1/investigations",
                headers={"X-Principal": "user:test"},
                json={
                    "cve_id": "CVE-2026-51515",
                    "goal": "Internal benchmark",
                    "evidence_question": "Verify the fixture",
                    "task_kind": "verify_version_fix",
                },
            )
            assert benchmark.status_code == 202, benchmark.text
            async with factory() as fixture_session, fixture_session.begin():
                await fixture_session.execute(
                    update(TaskContractVersionModel)
                    .where(
                        TaskContractVersionModel.task_contract_version_id.in_(
                            select(TaskRunModel.task_contract_version_id).where(
                                TaskRunModel.case_id == benchmark.json()["case_id"]
                            )
                        )
                    )
                    .values(principal="system:benchmark:internal")
                )
            product_page = await client.get(
                "/api/v1/investigations", params={"limit": 1, "origin_scope": "product"}
            )
            assert product_page.status_code == 200, product_page.text
            assert [item["case_id"] for item in product_page.json()["items"]] == [
                payload["case_id"]
            ]
            assert product_page.json()["has_more"] is False
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


@pytest.mark.asyncio
async def test_product_runtime_activity_and_sse_replay_from_durable_events() -> None:
    engine, factory = await _database()
    app = create_app()
    app.state.session_factory = factory

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            started = await client.post(
                "/api/v1/investigations",
                headers={"X-Request-ID": "activity-start", "X-Principal": "user:test"},
                json={
                    "cve_id": "CVE-2026-51515",
                    "goal": "Verify fix boundary",
                    "evidence_question": "Which version first contains the fix?",
                    "task_kind": "verify_version_fix",
                },
            )
            assert started.status_code == 202, started.text
            case_id = started.json()["case_id"]

            activity = await client.get(f"/api/v1/investigations/{case_id}/activity")
            assert activity.status_code == 200, activity.text
            events = activity.json()["events"]
            assert events
            assert "started" in {item["event_type"] for item in events}
            assert "evidence_need_changed" in {item["event_type"] for item in events}
            assert "TaskCreated" in {item["technical_type"] for item in events}
            assert "payload_ref" not in activity.text
            assert "idempotency_key" not in activity.text

            stream = await client.get(f"/api/v1/investigations/{case_id}/events?follow=false")
            assert stream.status_code == 200, stream.text
            assert stream.headers["content-type"].startswith("text/event-stream")
            assert "event: started" in stream.text
            first_id = events[0]["event_id"]

            replay = await client.get(
                f"/api/v1/investigations/{case_id}/events?follow=false",
                headers={"Last-Event-ID": first_id},
            )
            assert replay.status_code == 200
            assert f"id: {first_id}" not in replay.text
    finally:
        await engine.dispose()
