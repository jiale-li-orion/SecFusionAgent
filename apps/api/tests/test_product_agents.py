from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.account_fixtures import account_headers, seed_test_accounts
from apps.runtime_models import register_runtime_models
from packages.investigation.skills.storage import SkillVersionModel
from packages.investigation.storage.models import (
    ExperienceModel,
    ExperienceSupportModel,
    ExperienceVersionModel,
    InvestigationCaseModel,
    InvestigationTrajectoryModel,
)
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
            manifest_json={
                "context_id": "context-1",
                "context_revision": 1,
                "task_contract_ref": "contract-1@1",
                "role_ref": "InvestigationRole@1",
                "case_ref": "case:test",
                "policy_context_ref": "policy-context:policy-v1",
                "capability_envelope_ref": "capability:fixture",
                "budget_ref": "budget:task-run-1",
            },
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
    await seed_test_accounts(factory)
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
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


@pytest.mark.asyncio
async def test_product_agent_task_detail_exposes_durable_delegation_neighbors() -> None:
    engine, factory = await _database()
    await seed_test_accounts(factory)
    async with factory() as session, session.begin():
        session.add(
            TaskRunModel(
                run_id="task-run-child",
                task_contract_version_id="contract-version-1",
                task_contract_id="contract-1",
                task_contract_revision=1,
                context_manifest_version_id="context-version-1",
                context_id="context-1",
                context_revision=1,
                case_id=None,
                parent_run_id="task-run-1",
                role_id="EnrichmentRole",
                role_version="1",
                status="waiting_dependency",
                base_context_revision=1,
                execution_envelope_ref="envelope:child",
                result_ref=None,
                stop_reason="awaiting_dependency",
                created_at=NOW,
                updated_at=NOW,
                finished_at=None,
            )
        )

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            root = await client.get("/api/v1/tasks/task-run-1")
            child = await client.get("/api/v1/tasks/task-run-child")

        assert root.status_code == 200, root.text
        root_body = root.json()
        assert root_body["parent"] is None
        assert [item["run_id"] for item in root_body["children"]] == ["task-run-child"]
        assert root_body["children"][0]["role_id"] == "EnrichmentRole"

        assert child.status_code == 200, child.text
        child_body = child.json()
        assert child_body["parent"]["run_id"] == "task-run-1"
        assert child_body["parent"]["role_id"] == "InvestigationRole"
        assert child_body["children"] == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_agent_learning_exposes_collection_and_exact_detail_reads() -> None:
    engine, factory = await _database()
    async with factory() as session, session.begin():
        session.add(
            SkillVersionModel(
                skill_version_id="skill-version-1",
                skill_id="VerifyFixBoundary",
                version=1,
                namespace="investigation",
                status="active",
                source_type="seed",
                manifest_json={
                    "task_patterns": ["verify_version_fix"],
                    "evidence_need_patterns": ["fix_remediation"],
                    "applicable_object_types": ["Vulnerability"],
                    "applicability_conditions": [],
                    "required_capability_classes": ["knowledge.read"],
                    "optional_capability_classes": [],
                    "expected_outcomes": ["decision_ready"],
                },
                procedure_json={
                    "steps": [{"kind": "inspect"}],
                    "evidence_expectations": ["fix evidence"],
                    "failure_guards": [],
                    "fallbacks": [],
                    "stop_conditions": ["decision_ready"],
                },
                provenance_json={"origin": "seed", "supporting_trajectory_refs": []},
                content_hash="1" * 64,
                validation_ref="validation:test",
                supersedes=None,
                created_at=NOW,
            )
        )
        session.add(
            ExperienceModel(
                experience_id="experience-1",
                name="Fix boundary recovery",
                task_signature="verify_version_fix",
                current_version_id="experience-version-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            ExperienceVersionModel(
                experience_version_id="experience-version-1",
                experience_id="experience-1",
                version=1,
                status="active",
                scope={},
                trigger_signals=["missing_fix"],
                applicable_conditions=[],
                recommended_actions=["delegate_enrichment"],
                evidence_expectation=["fix evidence"],
                failure_modes=[],
                stop_conditions=["decision_ready"],
                fallback_actions=[],
                validation_summary={},
                success_count=2,
                failure_count=0,
                partial_count=0,
                last_validated_at=NOW,
                supersedes_version_id=None,
                source_candidate_id=None,
                created_at=NOW,
                activated_at=NOW,
                deprecated_at=None,
            )
        )

    # Public learning requires a genuine system-owned support trajectory;
    # a bare experience registry row has no publication authority.
    async with factory() as session, session.begin():
        session.add(
            InvestigationCaseModel(
                case_id="learning-system-case",
                task_signature="verify_version_fix",
                target_object_ids=[],
                goal="platform validation",
                status="resolved",
                current_revision=0,
                created_at=NOW,
            )
        )
        contract = await session.get(TaskContractVersionModel, "contract-version-1")
        contract_values = {
            column.name: getattr(contract, column.name) for column in contract.__table__.columns
        }
        session.add(
            TaskContractVersionModel(
                **{
                    **contract_values,
                    "task_contract_version_id": "learning-contract-version",
                    "task_contract_id": "learning-contract",
                    "principal": "system:learning",
                    "on_behalf_of": None,
                }
            )
        )
        run = await session.get(TaskRunModel, "task-run-1")
        run_values = {column.name: getattr(run, column.name) for column in run.__table__.columns}
        session.add(
            TaskRunModel(
                **{
                    **run_values,
                    "run_id": "learning-system-run",
                    "task_contract_version_id": "learning-contract-version",
                    "task_contract_id": "learning-contract",
                    "case_id": "learning-system-case",
                    "status": "completed",
                }
            )
        )
        session.add(
            InvestigationTrajectoryModel(
                trajectory_id="learning-system-trajectory",
                case_id="learning-system-case",
                status="completed",
                outcome="success",
                started_at=NOW,
                finished_at=NOW,
            )
        )
        session.add(
            ExperienceSupportModel(
                support_id="learning-system-support",
                experience_version_id="experience-version-1",
                trajectory_id="learning-system-trajectory",
                outcome="success",
                evaluation={},
                evaluator="system:learning",
                created_at=NOW,
            )
        )

    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            skills = await client.get("/api/v1/agents/skills")
            skill = await client.get("/api/v1/agents/skills/skill:VerifyFixBoundary@1")
            experiences = await client.get("/api/v1/agents/experiences")
            experience = await client.get("/api/v1/agents/experiences/experience-version-1")
            missing = await client.get("/api/v1/agents/skills/skill:missing@1")

        assert skills.status_code == 200, skills.text
        assert [item["skill_ref"] for item in skills.json()] == ["skill:VerifyFixBoundary@1"]
        assert skill.status_code == 200, skill.text
        assert skill.json()["validation_ref"] == "validation:test"
        assert experiences.status_code == 200, experiences.text
        assert experiences.json()[0]["experience_id"] == "experience-1"
        assert experience.status_code == 200, experience.text
        assert experience.json()["recommended_actions"] == ["delegate_enrichment"]
        assert missing.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_agent_proof_uses_agent_runtime_controlled_benchmark() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/agents/proof")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suite_ref"].startswith("m5-agent-runtime-controlled-v1@")
    assert body["scope"] == "controlled_runtime_regression_not_live_external_agent_score"
    delegated = next(
        item for item in body["cases"] if item["case_id"] == "agent-delegated-enrichment-resume"
    )
    assert delegated["subsystem"] == (
        "InvestigationRole->EnrichmentRole->TaskEvent->DependencyWake->Perception->StatePatch"
    )
    assert len(delegated["task_run_ids"]) == 2
    assert delegated["metrics"]["agent.delegation_precision"] == 1.0
