from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.account_fixtures import account_headers, seed_test_accounts
from apps.application.question_sessions import QuestionSessionStore
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import (
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.reasoning.decision import DecisionResult
from packages.reasoning.storage import DecisionResultStore
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import transition_task_run

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
    await seed_test_accounts(factory)
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
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-1", **account_headers("test")},
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
        assert payload["session_id"]
        assert payload["turn_index"] == 1
        assert payload["execution_profile"] == "VERIFY"
        assert payload["decision"] is None
        assert payload["investigation"]["open_evidence_needs"][0]["required_source_roles"] == [
            "primary"
        ]
        assert response.headers["location"].endswith(payload["investigation"]["case_id"])
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_command_replay_keeps_one_case_and_one_session_turn() -> None:
    engine, factory = await _database()
    app = create_app()
    app.state.session_factory = factory

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    payload = {
        "question": "Which version first contains the fix?",
        "cve_id": "CVE-2026-61616",
        "task_kind": "verify_version_fix",
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            first = await client.post(
                "/api/v1/questions", headers={"Idempotency-Key": "question-one"}, json=payload
            )
            second = await client.post(
                "/api/v1/questions", headers={"Idempotency-Key": "question-one"}, json=payload
            )
            assert first.status_code == second.status_code == 202
            assert first.json() == second.json()
            history = await client.get(
                f"/api/v1/questions/sessions/{first.json()['session_id']}"
            )
            assert history.status_code == 200
            assert len(history.json()["turns"]) == 1
            changed = await client.post(
                "/api/v1/questions", headers={"Idempotency-Key": "question-one"},
                json={**payload, "question": "Different question"},
            )
            assert changed.status_code == 409
            assert changed.json()["code"] == "idempotency_conflict"
            stream = await client.post(
                "/api/v1/questions/stream",
                headers={"Idempotency-Key": "question-one"},
                json=payload,
            )
            assert stream.status_code == 200
            assert "event: result\n" in stream.text
            assert first.json()["session_id"] in stream.text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_stream_uses_authenticated_session_and_emits_durable_result() -> None:
    engine, factory = await _database()
    app = create_app()
    app.state.session_factory = factory

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            denied = await client.post(
                "/api/v1/questions/stream",
                json={"question": "Verify this CVE", "cve_id": "CVE-2026-61616"},
            )
            response = await client.post(
                "/api/v1/questions/stream",
                headers=account_headers(),
                json={
                    "question": "Verify this CVE",
                    "cve_id": "CVE-2026-61616",
                    "task_kind": "verify_version_fix",
                    "interactive_timeout_seconds": 90,
                },
            )
        assert denied.status_code == 401
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: status\n" in response.text
        assert "event: result\n" in response.text
        assert '"mode": "accepted"' in response.text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_question_session_lookup_accepts_active_case_without_target() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            first_response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-case-read-1"},
                json={
                    "question": "Investigate this vulnerability.",
                    "cve_id": "CVE-2026-61616",
                    "task_kind": "investigate_relation",
                },
            )
            assert first_response.status_code == 202, first_response.text
            first = first_response.json()
            second_response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-case-read-2"},
                json={
                    "session_id": first["session_id"],
                    "question": "What has this investigation confirmed so far?",
                    "task_kind": "lookup",
                },
            )
        # Transport/schema accepts session-only LOOKUP and reaches the model dependency.
        # Application tests cover the configured-provider Case-read execution itself.
        assert second_response.status_code == 503, second_response.text
        assert second_response.json()["code"] == "dependency_unavailable"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_question_session_continues_existing_investigation_case() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    settings = get_settings()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            first_response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-followup-1", **account_headers("test")},
                json={
                    "question": "Verify the fix evidence.",
                    "cve_id": "CVE-2026-61616",
                    "task_kind": "verify_version_fix",
                },
            )
        assert first_response.status_code == 202, first_response.text
        first = first_response.json()
        case_id = first["investigation"]["case_id"]

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            owned_case = await client.get(
                f"/api/v1/investigations/{case_id}",
                headers={**account_headers("test")},
            )
            foreign_case = await client.get(
                f"/api/v1/investigations/{case_id}",
                headers={**account_headers("other")},
            )
        assert owned_case.status_code == 200, owned_case.text
        assert owned_case.json()["continuation_session_id"] == first["session_id"]
        assert owned_case.json()["origin_scope"] == "product"
        assert owned_case.json()["can_cancel"] is True
        assert foreign_case.status_code == 404, foreign_case.text

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            history = await client.get(
                f"/api/v1/questions/sessions/{first['session_id']}",
                headers={**account_headers("test")},
            )
            forbidden_history = await client.get(
                f"/api/v1/questions/sessions/{first['session_id']}",
                headers={**account_headers("other")},
            )
            missing_history = await client.get("/api/v1/questions/sessions/missing-session")
        assert history.status_code == 200, history.text
        assert history.json()["turns"][0]["question"] == "Verify the fix evidence."
        assert history.json()["turns"][0]["investigation_ref"] == f"case:{case_id}"
        assert "principal" not in history.json()
        assert forbidden_history.status_code == 403
        assert missing_history.status_code == 404

        async with factory() as session, session.begin():
            run = await session.scalar(
                select(TaskRunModel).where(
                    TaskRunModel.case_id == case_id,
                    TaskRunModel.role_id == "InvestigationRole",
                )
            )
            assert run is not None
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref=f"test:{run.run_id}:running",
                idempotency_key=f"test-running:{run.run_id}",
                stream_name=settings.task_event_stream_name,
                producer="test",
            )
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.COMPLETED,
                payload_ref=f"test:{run.run_id}:completed",
                idempotency_key=f"test-completed:{run.run_id}",
                stream_name=settings.task_event_stream_name,
                producer="test",
                stop_reason="test_episode_complete",
            )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            second_response = await client.post(
                "/api/v1/questions",
                headers={"X-Request-ID": "question-http-followup-2", **account_headers("test")},
                json={
                    "session_id": first["session_id"],
                    "question": "Verify the remaining primary-source gap.",
                    "task_kind": "verify_version_fix",
                    "required_source_roles": ["primary"],
                },
            )
        assert second_response.status_code == 202, second_response.text
        second = second_response.json()
        assert second["session_id"] == first["session_id"]
        assert second["turn_index"] == 2
        assert second["investigation"]["case_id"] == case_id
        assert len(second["investigation"]["open_evidence_needs"]) == 2
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
        await QuestionSessionStore(now=lambda: NOW).append_turn(
            session,
            session_id="http-read-session",
            principal="user:test",
            request_id="http-read-request",
            question="Read the persisted answer.",
            task_kind="lookup",
            target_object_ids=["question-api-object"],
            knowledge_revision=None,
            context_id=None,
            decision_ref="decision:http-read-1",
            investigation_ref=None,
        )
    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
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
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
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
