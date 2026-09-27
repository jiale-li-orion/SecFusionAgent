from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.perception_routes import (
    ExternalObservationRoute,
    SandboxObservationRoute,
    StaticPerceptionExecutionResolver,
)
from apps.runtime_models import register_runtime_models
from packages.investigation.perception.contracts import (
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
    PhysicalOperator,
    PhysicalPerceptionStep,
)
from packages.runtime.capability.contracts import ExecutionClass
from packages.runtime.sandbox.contracts import IsolationClass
from packages.shared.db import Base
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_run(factory) -> tuple[str, TaskContract]:
    run_id = str(uuid4())
    task = TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"goal": "verify release containment"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient_or_blocked"},
        policy_revision="policy-v1",
    )
    async with factory() as session, session.begin():
        await create_task_run(
            session,
            contract=task,
            manifest=ContextManifest(
                context_id=f"context:{run_id}",
                context_revision=1,
                task_contract_ref=f"{task.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:verify:v1",
                budget_ref=f"budget:{run_id}",
            ),
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{run_id}",
            stream_name="secfusion:task-events:route-test",
            run_id=run_id,
            now=NOW,
        )
    return run_id, task


@pytest.mark.asyncio
async def test_static_resolver_binds_external_route_and_promotion_without_native_schema() -> None:
    engine, factory = await _database()
    try:
        run_id, task = await _seed_run(factory)
        resolver = StaticPerceptionExecutionResolver(
            factory,
            external_routes=[
                ExternalObservationRoute(
                    route_id="github-release-observation",
                    route_revision=1,
                    capability_requirement="github.release.read",
                    capability_id="repo.read_release",
                    contract_revision=1,
                    action="read",
                    resource_type="repository.release",
                    resource_input_key="repo_full_name",
                    resource_prefix="repo:",
                    argument_map={
                        "repo_full_name": "repo_full_name",
                        "tag": "release_tag",
                    },
                    estimated_budget={"tool_calls": Decimal("1")},
                    healthy_refs={"health:github"},
                    available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                    promotion_source_id="github-target-repos",
                    promote_request_target=True,
                )
            ],
        )
        request = PerceptionRequest(
            request_id="perception:release",
            case_id="case-1",
            need_id="need-release",
            operation=PerceptionOperation.OBSERVE_EXTERNAL,
            target=PerceptionTarget(object_id="vulnerability-1"),
        )
        step = PhysicalPerceptionStep(
            step_id="external:0",
            operator=PhysicalOperator.EXTERNAL,
            input={
                "repo_full_name": "vllm-project/vllm",
                "release_tag": "v0.22.0",
                "ignored_native_detail": "must-not-leak",
            },
            expected_output_type="ephemeral_observation",
            capability_requirement="github.release.read",
        )
        resolved = await resolver.resolve_external(
            task_run_id=run_id,
            request=request,
            step=step,
        )
        assert resolved.request.task_contract_id == task.task_contract_id
        assert resolved.request.principal == task.principal
        assert resolved.request.resource == "repo:vllm-project/vllm"
        assert resolved.request.canonical_arguments == {
            "repo_full_name": "vllm-project/vllm",
            "tag": "v0.22.0",
        }
        assert "ignored_native_detail" not in resolved.request.canonical_arguments
        assert resolved.request.evidence_purpose == "need-release"
        assert resolved.available_execution_classes == {ExecutionClass.PROXIED_PROVIDER_READ}
        assert resolved.promotion is not None
        assert resolved.promotion.source_id == "github-target-repos"
        assert resolved.promotion.target_id == "vulnerability-1"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_static_resolver_binds_sandbox_capability_but_leaves_native_args_to_binding() -> None:
    engine, factory = await _database()
    try:
        run_id, task = await _seed_run(factory)
        resolver = StaticPerceptionExecutionResolver(
            factory,
            sandbox_routes=[
                SandboxObservationRoute(
                    route_id="git-ancestry-v1",
                    route_revision=1,
                    capability_requirement="git.ancestry_check",
                    capability_id="repo.git_ancestry",
                    contract_revision=1,
                    action="verify_ancestry",
                    resource_type="repository.git",
                    resource_input_key="repo_full_name",
                    resource_prefix="repo:",
                    argument_map={
                        "repo_full_name": "repo_full_name",
                        "commit_sha": "commit_sha",
                        "release_tag": "release_tag",
                    },
                    estimated_budget={"tool_calls": Decimal("1")},
                    healthy_refs={"health:git-ancestry"},
                    available_execution_classes={ExecutionClass.RESTRICTED_PROCESS},
                    program_ref="program:git-ancestry-check",
                    minimum_isolation=IsolationClass.PROCESS_RESTRICTED,
                    requested_timeout_seconds=12,
                )
            ],
        )
        request = PerceptionRequest(
            request_id="perception:ancestry",
            case_id="case-1",
            need_id="need-release",
            operation=PerceptionOperation.TRACE,
            target=PerceptionTarget(object_id="commit-object"),
        )
        step = PhysicalPerceptionStep(
            step_id="sandbox:0",
            operator=PhysicalOperator.SANDBOX,
            input={
                "repo_full_name": "vllm-project/vllm",
                "commit_sha": "abc123",
                "release_tag": "v0.22.0",
            },
            expected_output_type="ephemeral_observation",
            capability_requirement="git.ancestry_check",
        )
        resolved = await resolver.resolve_sandbox(
            task_run_id=run_id,
            request=request,
            step=step,
        )
        assert resolved.request.task_contract_id == task.task_contract_id
        assert resolved.request.resource == "repo:vllm-project/vllm"
        assert resolved.request.canonical_arguments == {
            "repo_full_name": "vllm-project/vllm",
            "commit_sha": "abc123",
            "release_tag": "v0.22.0",
        }
        assert resolved.exec_request.program_ref == "program:git-ancestry-check"
        assert resolved.exec_request.arguments == {}
        assert resolved.exec_request.requested_timeout_seconds == 12
        assert resolved.create_request.minimum_isolation is IsolationClass.PROCESS_RESTRICTED
        assert resolved.available_execution_classes == {ExecutionClass.RESTRICTED_PROCESS}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_static_resolver_fails_closed_for_unrouted_requirement() -> None:
    engine, factory = await _database()
    try:
        run_id, _ = await _seed_run(factory)
        resolver = StaticPerceptionExecutionResolver(factory)
        request = PerceptionRequest(
            request_id="perception:unknown",
            operation=PerceptionOperation.OBSERVE_EXTERNAL,
            target=PerceptionTarget(query_text="unknown provider"),
        )
        step = PhysicalPerceptionStep(
            step_id="external:0",
            operator=PhysicalOperator.EXTERNAL,
            expected_output_type="ephemeral_observation",
            capability_requirement="unknown.provider",
        )
        with pytest.raises(LookupError, match="no perception capability route"):
            await resolver.resolve_external(
                task_run_id=run_id,
                request=request,
                step=step,
            )
    finally:
        await engine.dispose()


def test_static_resolver_rejects_duplicate_semantic_route_keys() -> None:
    route = ExternalObservationRoute(
        route_id="one",
        route_revision=1,
        capability_requirement="github.release.read",
        capability_id="repo.read_release",
        contract_revision=1,
        action="read",
        resource_type="repository.release",
        resource="repo:vllm-project/vllm",
    )
    with pytest.raises(ValueError, match="duplicate external capability route"):
        StaticPerceptionExecutionResolver(
            object(),  # type: ignore[arg-type]
            external_routes=[route, route.model_copy(update={"route_id": "two"})],
        )
