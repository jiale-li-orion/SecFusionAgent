from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.routes.workbench import database_session, router
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.monitoring.storage.models import SourceStateModel
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session, session.begin():
        session.add(
            SourceModel(
                source_id="fixture-cve",
                adapter_type="fixture",
                source_class="vulnerability",
                authority_scope=["vulnerability"],
                source_role="authority",
                source_family="fixture",
                upstream_source=None,
                access_mode="fixture",
                update_semantics="append",
                discovery_method={},
                time_semantics={},
                identity_semantics={},
                auth_ref=None,
                rate_limit_policy={},
                access_rights={},
                retention_mode="hot_window",
                schedule_policy={"enabled": True},
                schema_version="1",
                definition_hash="fixture",
                managed_by="test",
                enabled=True,
                updated_at=NOW,
            )
        )
        session.add(
            SourceStateModel(
                source_id="fixture-cve",
                cursor={},
                last_attempt_at=NOW,
                last_success_at=NOW,
                last_change_at=NOW,
                next_due_at=NOW,
                consecutive_failures=0,
                backoff_until=None,
                rate_limit_state={},
            )
        )
        revision = KnowledgeRevisionModel(committed_at=NOW)
        session.add(revision)
        await session.flush()
        obj = ObjectModel(
            object_id="workbench-object",
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-42424",
            properties={"display_name": "CVE-2026-42424"},
            created_revision=revision.revision,
        )
        session.add(obj)
        session.add(
            ExternalIdentifierModel(
                external_identifier_id="workbench-cve-id",
                namespace="cve",
                value="CVE-2026-42424",
                object_id=obj.object_id,
            )
        )
    return "workbench-object"


@pytest.mark.asyncio
async def test_workbench_exposes_runtime_state_and_creates_admitted_investigation_run() -> None:
    engine, factory = await _database()
    object_id = await _seed(factory)
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview = await client.get("/api/v1/workbench/overview")
            assert overview.status_code == 200
            assert overview.json()["source_count"] == 1
            assert overview.json()["object_count"] == 1

            sources = await client.get("/api/v1/workbench/sources")
            assert sources.status_code == 200
            assert sources.json()[0]["source_id"] == "fixture-cve"

            created = await client.post(
                "/api/v1/workbench/cases",
                json={
                    "object_id": object_id,
                    "goal": "Verify the affected and fixed boundary.",
                    "evidence_question": "Which version first contains the fix?",
                    "purpose": "verify_fix_release",
                    "required_source_roles": ["primary"],
                },
            )
            assert created.status_code == 201, created.text
            case_id = created.json()["case"]["case_id"]
            need_id = created.json()["evidence_need"]["need_id"]

            case_detail = await client.get(f"/api/v1/workbench/cases/{case_id}")
            assert case_detail.status_code == 200
            assert case_detail.json()["state"]["case_revision"] == 1
            assert case_detail.json()["evidence_needs"][0]["need_id"] == need_id

            created_run = await client.post(
                f"/api/v1/workbench/cases/{case_id}/runs",
                json={
                    "task_kind": "verify_version_fix",
                    "required_need_ids": [need_id],
                    "timeout_seconds": 120,
                },
            )
            assert created_run.status_code == 201, created_run.text
            assert created_run.json()["admission"]["policy_authorization"] == "permit"
            run_id = created_run.json()["run"]["run_id"]
            assert created_run.json()["run"]["status"] == "queued"

            detail = await client.get(f"/api/v1/workbench/tasks/{run_id}")
            assert detail.status_code == 200
            assert detail.json()["contract"]["task_kind"] == "verify_version_fix"
            assert [event["event_type"] for event in detail.json()["events"]] == [
                "TaskCreated",
                "TaskPatched",
            ]

            tasks = await client.get("/api/v1/workbench/tasks", params={"case_id": case_id})
            assert tasks.status_code == 200
            assert tasks.json()[0]["run_id"] == run_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_workbench_source_coverage_is_executable_competition_view() -> None:
    engine, factory = await _database()
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/workbench/evaluation/source-coverage")
        assert response.status_code == 200
        assert len(response.json()["supported_source_categories"]) == 8
        assert response.json()["unsupported_source_categories"] == []
    finally:
        await engine.dispose()
