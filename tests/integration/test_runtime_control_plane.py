from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import JsonValue
from sqlalchemy import delete, select

from apps.runtime_models import register_runtime_models
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.capability.broker import (
    CapabilityBroker,
    InvocationGrants,
    NativeExecutionResult,
)
from packages.runtime.capability.contracts import (
    CapabilityBinding,
    CapabilityContract,
    CapabilityDescriptor,
    CapabilityRequest,
    CapabilityResultStatus,
    EffectSemantics,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
    native_schema_hash,
)
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.runtime.sandbox.broker import (
    SandboxBackendExecResult,
    SandboxBroker,
    SandboxCreateRequest,
    SandboxExecRequest,
    SandboxGrants,
    SandboxLeaseSpec,
)
from packages.runtime.sandbox.contracts import IsolationClass
from packages.runtime.storage.models import (
    BudgetAccountModel,
    BudgetReservationModel,
    CapabilityInvocationModel,
    ExecutionRunModel,
    RuntimeArtifactModel,
    SandboxExecutionModel,
    SandboxInstanceModel,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    ExecutionProfile,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import create_task_run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]

NOW = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


class _CapabilityExecutor:
    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, native_arguments, timeout_seconds
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref="result:release-state",
            raw_artifact_ref="artifact:release-state",
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=[{"tag": "v1.2.3"}],
        )


class _SandboxBackend:
    backend_id = "openshell"

    async def create(self, lease: SandboxLeaseSpec) -> str:
        return f"backend:{lease.execution_id}"

    async def exec(self, backend_handle_ref, request, *, timeout_seconds):
        del backend_handle_ref, request, timeout_seconds
        return SandboxBackendExecResult(
            status="succeeded",
            exit_code=0,
            stdout_artifact_ref="artifact:sandbox-stdout",
        )

    async def export(self, backend_handle_ref, relative_paths):
        del backend_handle_ref
        return [f"artifact:export:{path}" for path in relative_paths]

    async def destroy(self, backend_handle_ref):
        del backend_handle_ref


def _task(run_id: str) -> TaskContract:
    return TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:integration",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:example/project"],
        desired_state={"goal": "verify release state"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient_or_blocked"},
        policy_revision="policy-v1",
    )


def _registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {"type": "object"}
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    implementation = ToolImplementation(
        tool_impl_id="fixture-release-reader",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="fixture.release.read",
        transport="fixture",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        auth_class="none",
        health_ref="health:fixture",
        native_schema_hash=schema_hash,
    )
    contract = CapabilityContract(
        capability_id="repo.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["repository.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="provider_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_if_bound_source_is_primary"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        risk_class="low",
    )
    binding = CapabilityBinding(
        binding_id="fixture-release-binding",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="fixture",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="none",
        network_profile="none",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="registry-integration-v1",
        contracts=[contract],
        descriptors={contract.capability_id: CapabilityDescriptor(purpose="Read release state")},
        implementations=[implementation],
        bindings=[binding],
    )


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="allow-integration-capability",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:integration"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="allow-integration-sandbox",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.SANDBOX_SELECTION],
                principal_patterns=["user:integration"],
                action_patterns=["sandbox.create"],
                resource_patterns=["sandbox-profile:*"],
                authorization=Authorization.PERMIT,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_real_pg_runtime_control_plane_persists_execution_capability_and_sandbox() -> None:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    run_id = str(uuid4())
    context_id = f"context:{run_id}"
    budget_id = f"budget:{run_id}"
    execution_id = f"execution:{run_id}"
    task = _task(run_id)
    envelope = ExecutionEnvelope(
        execution_id=execution_id,
        task_contract_id=task.task_contract_id,
        task_run_id=run_id,
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        capability_scope=["repo.read_release"],
        deadline_at=NOW + timedelta(minutes=5),
        budget_ref=budget_id,
        policy_revision="policy-v1",
        identity_scope=["public"],
        network_policy="deny",
        side_effect_policy="read-only",
        sandbox_profile_revision="process_restricted@1",
    )
    budget = BudgetGovernor(now=lambda: NOW)
    execution = ExecutionRunService(now=lambda: NOW)
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            manifest = ContextManifest(
                context_id=context_id,
                context_revision=1,
                task_contract_ref=f"{task.task_contract_id}@1",
                role_ref="InvestigationRole@1",
                policy_context_ref="policy-context:v1",
                capability_envelope_ref="capability:integration:v1",
                budget_ref=budget_id,
            )
            await create_task_run(
                session,
                contract=task,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=execution_id,
                stream_name="secfusion:task-events:runtime-control-integration",
                run_id=run_id,
                now=NOW,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(quantities={"tool_calls": Decimal("3")}),
            )
            await execution.create(session, envelope)
            await execution.start(session, execution_id)
            artifact = await runtime_artifacts.write(
                session,
                execution_id=execution_id,
                producer_kind="capability",
                producer_ref="capability:repo.read_release",
                logical_name="release-state.json",
                media_type="application/json",
                body=b'{"tag":"v1.2.3"}',
            )
            assert artifact.artifact_ref.startswith("artifact:")

        broker = CapabilityBroker(_registry(), _policy(), budget, now=lambda: NOW)
        request = CapabilityRequest(
            request_id="capability-read-release",
            task_contract_id=task.task_contract_id,
            task_run_id=run_id,
            principal=task.principal,
            capability_id="repo.read_release",
            contract_revision=1,
            action="read",
            resource="repo:example/project",
            resource_type="repository.release",
            canonical_arguments={"tag": "v1.2.3"},
            intended_effect=EffectSemantics.OBSERVATION,
            evidence_purpose="verify_fix_boundary",
        )
        async with factory() as session, session.begin():
            outcome = await broker.invoke(
                session,
                task=task,
                envelope=envelope,
                request=request,
                executor=_CapabilityExecutor(),
                estimated_budget={"tool_calls": Decimal("1")},
                grants=InvocationGrants(),
                healthy_refs={"health:fixture"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
            )
            assert outcome.result.status is CapabilityResultStatus.SUCCEEDED
            assert outcome.observation is not None
            snapshot = await budget.snapshot(session, budget_id)
            assert snapshot.committed["tool_calls"] == Decimal("1.000000")

        sandbox = SandboxBroker(
            _policy(),
            {"openshell": _SandboxBackend()},
            available_backend_components={"openshell"},
            execution_service=execution,
            now=lambda: NOW,
        )
        async with factory() as session, session.begin():
            instance = await sandbox.create(
                session,
                task=task,
                envelope=envelope,
                request=SandboxCreateRequest(
                    request_id="sandbox-create",
                    minimum_isolation=IsolationClass.PROCESS_RESTRICTED,
                ),
                grants=SandboxGrants(),
            )
            result = await sandbox.exec(
                session,
                envelope=envelope,
                instance_id=instance.instance_id,
                request=SandboxExecRequest(
                    operation_id="inspect-release",
                    program_ref="program:verify-release",
                    requested_timeout_seconds=10,
                ),
            )
            assert result.status == "succeeded"
            replay = await sandbox.exec(
                session,
                envelope=envelope,
                instance_id=instance.instance_id,
                request=SandboxExecRequest(
                    operation_id="inspect-release",
                    program_ref="program:verify-release",
                    requested_timeout_seconds=10,
                ),
            )
            assert replay.replay is True
            await sandbox.destroy(session, instance.instance_id)
            await execution.finish(
                session,
                execution_id,
                status="completed",
                stop_reason="integration_complete",
            )

        async with factory() as session:
            invocation = await session.scalar(
                select(CapabilityInvocationModel).where(
                    CapabilityInvocationModel.task_run_id == run_id
                )
            )
            assert invocation is not None and invocation.status == "succeeded"
            execution_row = await session.get(ExecutionRunModel, execution_id)
            assert execution_row is not None and execution_row.status == "completed"
            runtime_artifact = await session.scalar(
                select(RuntimeArtifactModel).where(
                    RuntimeArtifactModel.execution_id == execution_id
                )
            )
            assert runtime_artifact is not None
            assert runtime_artifact.logical_name == "release-state.json"
            sandbox_row = await session.scalar(
                select(SandboxInstanceModel).where(SandboxInstanceModel.task_run_id == run_id)
            )
            assert sandbox_row is not None and sandbox_row.status == "destroyed"
            sandbox_exec = await session.scalar(
                select(SandboxExecutionModel).where(
                    SandboxExecutionModel.instance_id == sandbox_row.instance_id
                )
            )
            assert sandbox_exec is not None and sandbox_exec.status == "succeeded"
    finally:
        async with factory() as session, session.begin():
            instances = list(
                await session.scalars(
                    select(SandboxInstanceModel.instance_id).where(
                        SandboxInstanceModel.task_run_id == run_id
                    )
                )
            )
            if instances:
                await session.execute(
                    delete(SandboxExecutionModel).where(
                        SandboxExecutionModel.instance_id.in_(instances)
                    )
                )
            await session.execute(
                delete(SandboxInstanceModel).where(SandboxInstanceModel.task_run_id == run_id)
            )
            await session.execute(
                delete(CapabilityInvocationModel).where(
                    CapabilityInvocationModel.task_run_id == run_id
                )
            )
            await session.execute(
                delete(BudgetReservationModel).where(BudgetReservationModel.account_id == budget_id)
            )
            await session.execute(
                delete(BudgetAccountModel).where(BudgetAccountModel.account_id == budget_id)
            )
            await session.execute(
                delete(RuntimeArtifactModel).where(
                    RuntimeArtifactModel.execution_id == execution_id
                )
            )
            await session.execute(
                delete(ExecutionRunModel).where(ExecutionRunModel.execution_id == execution_id)
            )
            event_ids = list(
                await session.scalars(
                    select(TaskEventModel.event_id).where(TaskEventModel.task_run_id == run_id)
                )
            )
            if event_ids:
                await session.execute(
                    delete(TaskEventDeliveryModel).where(
                        TaskEventDeliveryModel.event_id.in_(event_ids)
                    )
                )
                await session.execute(
                    delete(TaskEventModel).where(TaskEventModel.event_id.in_(event_ids))
                )
            await session.execute(delete(TaskRunModel).where(TaskRunModel.run_id == run_id))
            await session.execute(
                delete(ContextManifestVersionModel).where(
                    ContextManifestVersionModel.context_id == context_id
                )
            )
            await session.execute(
                delete(TaskContractVersionModel).where(
                    TaskContractVersionModel.task_contract_id == task.task_contract_id
                )
            )
        await engine.dispose()
