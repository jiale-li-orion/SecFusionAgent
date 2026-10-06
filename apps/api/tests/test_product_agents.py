from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.runtime.model.storage import ModelAttemptModel, ModelRequestModel
from packages.runtime.storage.models import BudgetAccountModel
from packages.shared.db import Base
from packages.task_runtime.contracts.models import TaskEventType
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskEventModel,
    TaskRunModel,
)

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        contract = TaskContractVersionModel(
            task_contract_version_id="contract-version-1",
            task_contract_id="contract-1",
            contract_revision=1,
            principal="user:test",
            on_behalf_of=None,
            task_kind="verify_version_fix",
            effect_ceiling="read_only",
            policy_revision="policy-v1",
            contract_json={"test": True},
            content_hash="a" * 64,
            created_at=NOW,
        )
        session.add(contract)
        context = ContextManifestVersionModel(
            context_manifest_version_id="context-version-1",
            context_id="context-1",
            context_revision=1,
            parent_context_id=None,
            task_contract_version_id=contract.task_contract_version_id,
            role_ref="InvestigationRole@1",
            case_ref="case:test",
            knowledge_revision=None,
            manifest_json={},
            content_hash="b" * 64,
            created_at=NOW,
        )
        session.add(context)
        run = TaskRunModel(
            run_id="task-run-1",
            task_contract_version_id=contract.task_contract_version_id,
            task_contract_id=contract.task_contract_id,
            task_contract_revision=1,
            context_manifest_version_id=context.context_manifest_version_id,
            context_id=context.context_id,
            context_revision=1,
            case_id=None,
            parent_run_id=None,
            role_id="InvestigationRole",
            role_version="1",
            status="running",
            base_context_revision=1,
            execution_envelope_ref="envelope:test",
            result_ref=None,
            stop_reason=None,
            created_at=NOW,
            updated_at=NOW,
            finished_at=None,
        )
        session.add(run)
        session.add(
            BudgetAccountModel(
                account_id="budget:task-run-1",
                parent_account_id=None,
                task_run_id=run.run_id,
                limits={"wall_seconds": "300", "agent_turns": "8", "tool_calls": "12"},
                status="active",
                created_at=NOW,
                closed_at=None,
            )
        )
        session.add(
            ModelRequestModel(
                model_request_id="model-request-1",
                purpose="investigation.planner",
                request_owner_ref="task:task-run-1",
                execution_id=None,
                task_run_id=run.run_id,
                case_id=None,
                processing_run_id=None,
                prompt_assembly_id=None,
                prompt_revision="prompt:test@1",
                request_schema_digest="c" * 64,
                request_digest="d" * 64,
                request_artifact_ref=None,
                requested_model="model:test",
                provider_policy_ref="provider-policy:test",
                budget_ref="budget:task-run-1",
                metadata_json={},
                created_at=NOW,
            )
        )
        session.add_all(
            [
                ModelAttemptModel(
                    model_attempt_id="model-attempt-1",
                    model_request_id="model-request-1",
                    ordinal=1,
                    provider="test-provider",
                    adapter_revision="adapter:test@1",
                    actual_model="model:test",
                    provider_request_id="provider-request-1",
                    started_at=NOW,
                    finished_at=NOW,
                    status="failed",
                    failure_class="transient",
                    failure_detail="fixture",
                    response_schema_digest="e" * 64,
                    response_artifact_ref=None,
                    usage_json={},
                    cost_json={},
                    cache_usage_json={},
                    response_metadata_json={
                        "retryable": True,
                        "retry_scheduled": True,
                        "retry_delay_seconds": 0,
                    },
                    latency_ms=120,
                ),
                ModelAttemptModel(
                    model_attempt_id="model-attempt-2",
                    model_request_id="model-request-1",
                    ordinal=2,
                    provider="test-provider",
                    adapter_revision="adapter:test@1",
                    actual_model="model:test",
                    provider_request_id="provider-request-2",
                    started_at=NOW,
                    finished_at=NOW,
                    status="succeeded",
                    failure_class=None,
                    failure_detail=None,
                    response_schema_digest="f" * 64,
                    response_artifact_ref="artifact:model-response",
                    usage_json={},
                    cost_json={},
                    cache_usage_json={},
                    response_metadata_json={},
                    latency_ms=180,
                ),
            ]
        )
        session.add(
            TaskEventModel(
                event_id="event-1",
                task_run_id=run.run_id,
                parent_run_id=None,
                seq=1,
                event_type=TaskEventType.TASK_STARTED.value,
                producer="test-runtime",
                base_context_revision=1,
                payload_ref="payload:test",
                idempotency_key="event-key-1",
                emitted_at=NOW,
            )
        )
    return engine, factory


@pytest.mark.asyncio
async def test_product_agent_runtime_exposes_roles_tasks_and_safe_event_summary() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview = await client.get("/api/v1/agents/runtime")
            detail = await client.get("/api/v1/tasks/task-run-1")
            task_page = await client.get(
                "/api/v1/tasks",
                params={"role_id": "InvestigationRole", "status": "running"},
            )
        assert overview.status_code == 200, overview.text
        body = overview.json()
        role = next(item for item in body["roles"] if item["role_id"] == "InvestigationRole")
        assert role["active_tasks"] == 1
        assert role["status_counts"] == {"running": 1}
        assert body["recent_tasks"][0]["task_kind"] == "verify_version_fix"
        assert body["recent_tasks"][0]["last_event_type"] == "TaskStarted"
        assert overview.json()["recent_capabilities"] == []
        assert body["model_runtime"]["request_count"] == 1
        assert body["model_runtime"]["attempt_count"] == 2
        assert body["model_runtime"]["retry_attempt_count"] == 1
        assert body["model_runtime"]["retry_scheduled_count"] == 1
        assert body["model_runtime"]["failed_attempt_count"] == 1
        assert body["model_runtime"]["p95_latency_ms"] == 180
        assert body["model_runtime"]["provider_counts"] == {"test-provider": 2}
        assert body["control_runtime"]["sampled_task_count"] == 1
        assert body["control_runtime"]["wake_latency_measurement"] == "unavailable"

        assert task_page.status_code == 200, task_page.text
        assert [item["run_id"] for item in task_page.json()["items"]] == ["task-run-1"]

        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["events"][0]["event_type"] == "TaskStarted"
        assert detail_body["budget"]["limits"] == {
            "agent_turns": 8.0,
            "tool_calls": 12.0,
            "wall_seconds": 300.0,
        }
        assert detail_body["budget"]["remaining"]["agent_turns"] == 8.0
        assert "payload_ref" not in detail.text
        assert "idempotency_key" not in detail.text
    finally:
        await engine.dispose()
