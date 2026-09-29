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
from packages.reasoning.decision import DecisionResult
from packages.reasoning.storage import DecisionResultStore
from packages.shared.db import Base

NOW = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)


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
        session.add(
            ObjectModel(
                object_id="question-api-object",
                object_type="Vulnerability",
                canonical_key="cve:CVE-2026-61616",
                properties={"display_name": "CVE-2026-61616"},
                created_revision=revision.revision,
            )
        )
        session.add(
            ExternalIdentifierModel(
                external_identifier_id="question-api-cve-id",
                namespace="cve",
                value="CVE-2026-61616",
                object_id="question-api-object",
            )
        )
    return engine, factory


@pytest.mark.asyncio
async def test_product_question_complex_route_returns_accepted_investigation() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-1", "X-Principal": "user:test"},
                json={
                    "question": "Which version first contains the fix?",
                    "cve_id": "CVE-2026-61616",
                    "task_kind": "verify_version_fix",
                    "required_source_roles": ["primary"],
                },
            )
        assert response.status_code == 202, response.text
        payload = response.json()
        assert payload["mode"] == "accepted"
        assert payload["execution_profile"] == "VERIFY"
        assert payload["decision"] is None
        assert payload["investigation"]["open_evidence_needs"][0]["required_source_roles"] == [
            "primary"
        ]
        assert response.headers["location"].endswith(payload["investigation"]["case_id"])
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_get_decision_reads_immutable_m6_result() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async with factory() as session, session.begin():
        await DecisionResultStore(now=lambda: NOW).persist(
            session,
            DecisionResult(
                decision_id="decision:http-read-1",
                case_id="question:http-read-1",
                case_revision=0,
                answer_payload={"answer": "persisted"},
                stop_reason="complete",
                model_prompt_revision="decision-model-v1",
            ),
        )
    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/decisions/decision:http-read-1")
            missing = await client.get("/api/v1/decisions/decision:missing")
        assert response.status_code == 200
        assert response.json()["decision_id"] == "decision:http-read-1"
        assert response.json()["answer"] == {"answer": "persisted"}
        assert missing.status_code == 404
        assert missing.json()["code"] == "resource_not_found"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_question_lookup_requires_configured_model_provider() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-2"},
                json={
                    "question": "What is the CVSS score?",
                    "cve_id": "CVE-2026-61616",
                    "task_kind": "lookup",
                },
            )
        assert response.status_code == 503
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "dependency_unavailable"
    finally:
        await engine.dispose()
