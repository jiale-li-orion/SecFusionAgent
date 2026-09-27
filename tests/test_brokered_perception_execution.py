from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.observation_promotion import ObservationPromotionService
from apps.perception_execution import (
    BrokeredPhysicalObservationPort,
    ExternalPerceptionInvocation,
    ObservationPromotionBinding,
    SandboxPerceptionInvocation,
)
from apps.runtime_models import register_runtime_models
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.investigation.perception.contracts import (
    EvidenceRequirement,
    ObservedProposition,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
    PhysicalOperator,
    PhysicalPerceptionPlan,
    PhysicalPerceptionStep,
)
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.monitoring.storage.models import AcquisitionRunModel
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
from packages.shared.db import Base
from packages.sources.contracts import RetentionMode, SourceDefinition, SourceRole
from packages.sources.registry.service import sync_source_definitions
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
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 11, 30, tzinfo=UTC)

PROMOTION_SOURCE = SourceDefinition(
    source_id="fixture-primary-release-api-brokered",
    adapter_type="fixture",
    source_class="development_platform",
    authority_scope=["release_state", "fix_status"],
    source_role=SourceRole.PRIMARY,
    source_family="fixture-primary-release-api-brokered",
    access_mode="api",
    update_semantics="mutable",
    retention_mode=RetentionMode.TIME_BOUNDED,
)


class _CapabilityExecutor:
    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, timeout_seconds
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref="runtime:release-state",
            raw_artifact_ref="artifact:provider-release-state",
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=[
                {"statement": (f"Provider reports release {native_arguments['tag']} as current.")}
            ],
            provenance={"source_role": "primary"},
        )


class _PromotionCapabilityExecutor:
    def __init__(self, *, artifact_ref: str, acquisition_run_id: str) -> None:
        self._artifact_ref = artifact_ref
        self._acquisition_run_id = acquisition_run_id

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        del implementation, timeout_seconds
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            raw_artifact_ref=self._artifact_ref,
            consumed_budget={"tool_calls": Decimal("1")},
            extracted_candidates=[
                {
                    "statement": (
                        f"Provider reports release {native_arguments['tag']} contains the fix."
                    )
                }
            ],
            provenance={
                "acquisition_run_id": self._acquisition_run_id,
                "external_object_id": "release:v1.2.3",
                "external_revision": "v1.2.3",
                "canonical_url": "https://example.invalid/releases/v1.2.3",
                "published_at": NOW.isoformat(),
                "updated_at": NOW.isoformat(),
            },
        )


class _SandboxBackend:
    backend_id = "openshell"

    def __init__(self) -> None:
        self.create_calls = 0
        self.exec_calls = 0

    async def create(self, lease: SandboxLeaseSpec) -> str:
        self.create_calls += 1
        return f"secfusion-{lease.execution_id[-8:]}"

    async def exec(self, backend_handle_ref, request, *, timeout_seconds):
        self.exec_calls += 1
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


class _Resolver:
    def __init__(self, task: TaskContract) -> None:
        self._task = task

    async def resolve_external(self, *, task_run_id, request, step):
        del request, step
        return ExternalPerceptionInvocation(
            request=CapabilityRequest(
                request_id="capability:external-release",
                task_contract_id=self._task.task_contract_id,
                task_run_id=task_run_id,
                principal=self._task.principal,
                capability_id="repo.read_release",
                contract_revision=1,
                action="read",
                resource="repo:example/project",
                resource_type="repository.release",
                canonical_arguments={"tag": "v1.2.3"},
                intended_effect=EffectSemantics.OBSERVATION,
                evidence_purpose="verify_fix_boundary",
            ),
            estimated_budget={"tool_calls": Decimal("1")},
            grants=InvocationGrants(),
            healthy_refs={"health:fixture"},
            available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
        )

    async def resolve_sandbox(self, *, task_run_id, request, step):
        del request, step
        return SandboxPerceptionInvocation(
            request=CapabilityRequest(
                request_id="capability:sandbox-ancestry",
                task_contract_id=self._task.task_contract_id,
                task_run_id=task_run_id,
                principal=self._task.principal,
                capability_id="repo.git_ancestry",
                contract_revision=1,
                action="verify_ancestry",
                resource="repo:example/project",
                resource_type="repository.git",
                canonical_arguments={"release": "v1.2.3"},
                intended_effect=EffectSemantics.OBSERVATION,
                evidence_purpose="verify_fix_boundary",
            ),
            estimated_budget={"tool_calls": Decimal("1")},
            capability_grants=InvocationGrants(),
            healthy_refs={"health:sandbox-program"},
            available_execution_classes={ExecutionClass.RESTRICTED_PROCESS},
            create_request=SandboxCreateRequest(
                request_id="sandbox:create:verify-release",
                minimum_isolation=IsolationClass.PROCESS_RESTRICTED,
            ),
            exec_request=SandboxExecRequest(
                operation_id="sandbox:verify-release",
                program_ref="program:verify-release",
                arguments={"release": "v1.2.3"},
                requested_timeout_seconds=5,
            ),
            sandbox_grants=SandboxGrants(),
        )


class _PromotionResolver(_Resolver):
    def __init__(self, task: TaskContract, *, object_id: str) -> None:
        super().__init__(task)
        self._object_id = object_id

    async def resolve_external(self, *, task_run_id, request, step):
        resolved = await super().resolve_external(
            task_run_id=task_run_id,
            request=request,
            step=step,
        )
        return resolved.model_copy(
            update={
                "promotion": ObservationPromotionBinding(
                    source_id=PROMOTION_SOURCE.source_id,
                    target_kind="object",
                    target_id=self._object_id,
                    locator={"kind": "provider_release", "tag": "v1.2.3"},
                )
            }
        )


class _DeniedSandboxResolver(_Resolver):
    async def resolve_sandbox(self, *, task_run_id, request, step):
        resolved = await super().resolve_sandbox(
            task_run_id=task_run_id,
            request=request,
            step=step,
        )
        return resolved.model_copy(
            update={
                "request": resolved.request.model_copy(
                    update={"request_id": "capability:sandbox-ancestry-denied"}
                ),
                "create_request": resolved.create_request.model_copy(
                    update={"request_id": "sandbox:create:verify-release-denied"}
                ),
                "exec_request": resolved.exec_request.model_copy(
                    update={"operation_id": "sandbox:verify-release-denied"}
                ),
            }
        )


class _Interpreter:
    def capability(self, outcome):
        assert outcome.observation is not None
        return [
            ObservedProposition(
                statement=str(outcome.observation.extracted_candidates[0]["statement"]),
                support_refs=[f"observation:{outcome.observation.observation_id}"],
            )
        ]

    def sandbox(self, result, exported_artifact_refs):
        del exported_artifact_refs
        return [
            ObservedProposition(
                statement="Sandbox ancestry check completed successfully.",
                support_refs=[f"observation:sandbox:{result.sandbox_execution_id}"],
            )
        ]


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
    sandbox_input_schema: dict[str, JsonValue] = {"type": "object"}
    sandbox_output_schema: dict[str, JsonValue] = {"type": "object"}
    sandbox_schema_hash = native_schema_hash(sandbox_input_schema, sandbox_output_schema)
    sandbox_implementation = ToolImplementation(
        tool_impl_id="fixture-git-ancestry",
        implementation_revision=1,
        implementation_kind=ImplementationKind.SANDBOX_PROGRAM,
        native_name="program:verify-release",
        transport="sandbox",
        native_input_schema=sandbox_input_schema,
        native_output_schema=sandbox_output_schema,
        execution_backend="openshell",
        health_ref="health:sandbox-program",
        native_schema_hash=sandbox_schema_hash,
    )
    sandbox_contract = CapabilityContract(
        capability_id="repo.git_ancestry",
        contract_revision=1,
        action="verify_ancestry",
        applicable_resource_types=["repository.git"],
        canonical_input_schema=sandbox_input_schema,
        canonical_output_schema=sandbox_output_schema,
        observation_semantics="sandbox_git_ancestry_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["derived_local_analysis"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="task_artifact",
        data_egress_class="none",
        risk_class="medium",
    )
    sandbox_binding = CapabilityBinding(
        binding_id="fixture-git-ancestry-binding",
        binding_revision=1,
        capability_id=sandbox_contract.capability_id,
        contract_revision=1,
        tool_impl_id=sandbox_implementation.tool_impl_id,
        implementation_revision=1,
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="derived_local_analysis",
        execution_class=ExecutionClass.RESTRICTED_PROCESS,
        credential_profile="none",
        network_profile="deny",
        sandbox_profile="process_restricted",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        native_schema_hash=sandbox_schema_hash,
    )
    return CapabilityRegistry(
        revision="registry-test-v1",
        contracts=[contract, sandbox_contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(purpose="Read release state"),
            sandbox_contract.capability_id: CapabilityDescriptor(
                purpose="Verify git ancestry in a controlled sandbox"
            ),
        },
        implementations=[implementation, sandbox_implementation],
        bindings=[binding, sandbox_binding],
    )


def _promotion_policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="allow-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:test"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="allow-release-promotion",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.OBSERVATION_PROMOTION],
                principal_patterns=["user:test"],
                action_patterns=["promote_observation"],
                resource_patterns=[f"source:{PROMOTION_SOURCE.source_id}"],
                authorization=Authorization.PERMIT,
            ),
        ],
    )


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="allow-release-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:test"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="allow-git-ancestry",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:test"],
                action_patterns=["verify_ancestry"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="allow-sandbox",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.SANDBOX_SELECTION],
                principal_patterns=["user:test"],
                action_patterns=["sandbox.create"],
                resource_patterns=["sandbox-profile:*"],
                authorization=Authorization.PERMIT,
            ),
        ],
    )


def _deny_ancestry_invocation_policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="allow-release-read-only",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:test"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            )
        ],
    )


def _task(run_id: str) -> TaskContract:
    return TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:example/project"],
        desired_state={"goal": "verify release contains fix"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient_or_blocked"},
        policy_revision="policy-v1",
    )


@pytest.mark.asyncio
async def test_perception_external_and_sandbox_run_through_control_plane() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = str(uuid4())
    task = _task(run_id)
    budget_id = f"budget:{run_id}"
    execution_id = f"execution:{run_id}"
    envelope = ExecutionEnvelope(
        execution_id=execution_id,
        task_contract_id=task.task_contract_id,
        task_run_id=run_id,
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        capability_scope=["repo.read_release", "repo.git_ancestry"],
        deadline_at=NOW + timedelta(minutes=5),
        budget_ref=budget_id,
        policy_revision="policy-v1",
        identity_scope=["public"],
        network_policy="deny",
        side_effect_policy="read-only",
        sandbox_profile_revision="process_restricted@1",
    )
    budget = BudgetGovernor(now=lambda: NOW)
    execution_service = ExecutionRunService(now=lambda: NOW)
    try:
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
                    budget_ref=budget_id,
                ),
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=execution_id,
                stream_name="secfusion:task-events:test",
                run_id=run_id,
                now=NOW,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(quantities={"tool_calls": Decimal("2")}),
            )
            await execution_service.create(session, envelope)
            await execution_service.start(session, execution_id)

        capability_broker = CapabilityBroker(_registry(), _policy(), budget, now=lambda: NOW)
        sandbox_backend = _SandboxBackend()
        sandbox_broker = SandboxBroker(
            _policy(),
            {"openshell": sandbox_backend},
            available_backend_components={"openshell"},
            execution_service=execution_service,
            now=lambda: NOW,
        )
        port = BrokeredPhysicalObservationPort(
            capability_broker=capability_broker,
            capability_executor=_CapabilityExecutor(),
            sandbox_broker=sandbox_broker,
            resolver=_Resolver(task),
            interpreter=_Interpreter(),
            session_factory=factory,
            execution_service=execution_service,
        )
        runtime = PerceptionRuntime(port)

        external_request = PerceptionRequest(
            request_id="perception:external",
            operation=PerceptionOperation.OBSERVE_EXTERNAL,
            target=PerceptionTarget(source_ids=["github-repo-vllm"]),
            evidence_requirement=EvidenceRequirement(required_source_roles=["primary"]),
        )
        external_plan = PhysicalPerceptionPlan(
            request_id=external_request.request_id,
            steps=[
                PhysicalPerceptionStep(
                    step_id="external:0",
                    operator=PhysicalOperator.EXTERNAL,
                    expected_output_type="ephemeral_observation",
                    capability_requirement="external_observation",
                )
            ],
        )
        async with factory() as session:
            external = await runtime.execute(
                session,
                request=external_request,
                plan=external_plan,
                task_run_id=run_id,
            )
        assert external.observation_handles
        assert external.evidence_handles == []
        assert external.observed_propositions[0].statement.endswith("v1.2.3 as current.")
        assert "required_source_role_missing:primary" in external.unresolved

        sandbox_request = PerceptionRequest(
            request_id="perception:sandbox",
            operation=PerceptionOperation.TRACE,
            target=PerceptionTarget(object_id="commit:abc123"),
        )
        sandbox_plan = PhysicalPerceptionPlan(
            request_id=sandbox_request.request_id,
            steps=[
                PhysicalPerceptionStep(
                    step_id="sandbox:0",
                    operator=PhysicalOperator.SANDBOX,
                    input={"program_ref": "program:verify-release"},
                    expected_output_type="ephemeral_observation",
                    capability_requirement="git.ancestry_check",
                )
            ],
        )
        async with factory() as session:
            sandbox = await runtime.execute(
                session,
                request=sandbox_request,
                plan=sandbox_plan,
                task_run_id=run_id,
            )
        assert sandbox.observation_handles[0].startswith("observation:")
        assert sandbox.evidence_handles == []
        assert sandbox.observed_propositions[0].statement.startswith("Sandbox ancestry")
        assert sandbox.cost["sandbox:0:capability_calls"] == 1
        assert sandbox.cost["sandbox:0:sandbox_calls"] == 1
        assert sandbox_backend.create_calls == 1
        assert sandbox_backend.exec_calls == 1

        denied_port = BrokeredPhysicalObservationPort(
            capability_broker=CapabilityBroker(
                _registry(),
                _deny_ancestry_invocation_policy(),
                budget,
                now=lambda: NOW,
            ),
            capability_executor=_CapabilityExecutor(),
            sandbox_broker=sandbox_broker,
            resolver=_DeniedSandboxResolver(task),
            interpreter=_Interpreter(),
            session_factory=factory,
            execution_service=execution_service,
        )
        denied_request = PerceptionRequest(
            request_id="perception:sandbox-denied",
            operation=PerceptionOperation.TRACE,
            target=PerceptionTarget(object_id="commit:abc123"),
        )
        denied_plan = PhysicalPerceptionPlan(
            request_id=denied_request.request_id,
            steps=[
                PhysicalPerceptionStep(
                    step_id="sandbox:deny",
                    operator=PhysicalOperator.SANDBOX,
                    input={"program_ref": "program:verify-release"},
                    expected_output_type="ephemeral_observation",
                    capability_requirement="git.ancestry_check",
                )
            ],
        )
        async with factory() as session:
            denied = await PerceptionRuntime(denied_port).execute(
                session,
                request=denied_request,
                plan=denied_plan,
                task_run_id=run_id,
            )
        assert "capability_denied:policy_deny" in denied.unresolved
        assert denied.observation_handles == []
        assert sandbox_backend.create_calls == 1
        assert sandbox_backend.exec_calls == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_external_perception_can_promote_ephemeral_observation_into_durable_evidence() -> (
    None
):
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = str(uuid4())
    task = _task(run_id)
    budget_id = f"budget:{run_id}"
    execution_id = f"execution:{run_id}"
    acquisition_run_id = str(uuid4())
    object_id = str(uuid4())
    budget = BudgetGovernor(now=lambda: NOW)
    execution_service = ExecutionRunService(now=lambda: NOW)
    runtime_artifacts = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
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
        network_policy="proxied",
        side_effect_policy="read-only",
        sandbox_profile_revision="process_restricted@1",
    )
    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [PROMOTION_SOURCE])
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key=f"cve:CVE-2026-{run_id[:4]}",
                    properties={},
                    created_revision=1,
                )
            )
            await create_task_run(
                session,
                contract=task,
                manifest=ContextManifest(
                    context_id=f"context:{run_id}",
                    context_revision=1,
                    task_contract_ref=f"{task.task_contract_id}@1",
                    role_ref="InvestigationRole@1",
                    object_refs=[object_id],
                    policy_context_ref="policy-context:v1",
                    capability_envelope_ref="capability:verify:v1",
                    budget_ref=budget_id,
                ),
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=execution_id,
                stream_name="secfusion:task-events:promotion-composition-test",
                run_id=run_id,
                now=NOW,
            )
            await budget.create_account(
                session,
                account_id=budget_id,
                task_run_id=run_id,
                limits=BudgetLimits(quantities={"tool_calls": Decimal("2")}),
            )
            await execution_service.create(session, envelope)
            await execution_service.start(session, execution_id)
            session.add(
                AcquisitionRunModel(
                    run_id=acquisition_run_id,
                    source_id=PROMOTION_SOURCE.source_id,
                    trigger="investigation",
                    parent_run_id=None,
                    query_spec={"tag": "v1.2.3"},
                    status="success",
                    cursor_in={},
                    cursor_out={"result_count": 1},
                    attempt=1,
                    created_at=NOW,
                    started_at=NOW,
                    finished_at=NOW,
                )
            )
            artifact = await runtime_artifacts.write(
                session,
                execution_id=execution_id,
                producer_kind="capability",
                producer_ref="capability:repo.read_release",
                logical_name="release-v1.2.3.json",
                media_type="application/json",
                body=b'{"tag":"v1.2.3","contains_fix":true}',
            )

        policy = _promotion_policy()
        capability_broker = CapabilityBroker(_registry(), policy, budget, now=lambda: NOW)
        sandbox_broker = SandboxBroker(
            policy,
            {"openshell": _SandboxBackend()},
            available_backend_components={"openshell"},
            execution_service=execution_service,
            now=lambda: NOW,
        )
        promotion = ObservationPromotionService(
            factory,
            policy,
            runtime_artifacts,
            EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            {PROMOTION_SOURCE.source_id: PROMOTION_SOURCE},
        )
        port = BrokeredPhysicalObservationPort(
            capability_broker=capability_broker,
            capability_executor=_PromotionCapabilityExecutor(
                artifact_ref=artifact.artifact_ref,
                acquisition_run_id=acquisition_run_id,
            ),
            sandbox_broker=sandbox_broker,
            resolver=_PromotionResolver(task, object_id=object_id),
            session_factory=factory,
            promotion_port=promotion,
            execution_service=execution_service,
        )
        request = PerceptionRequest(
            request_id="perception:external-promoted",
            operation=PerceptionOperation.OBSERVE_EXTERNAL,
            target=PerceptionTarget(object_id=object_id),
            evidence_requirement=EvidenceRequirement(
                required_source_roles=["primary"],
                min_independent_sources=1,
            ),
        )
        plan = PhysicalPerceptionPlan(
            request_id=request.request_id,
            steps=[
                PhysicalPerceptionStep(
                    step_id="external:0",
                    operator=PhysicalOperator.EXTERNAL,
                    expected_output_type="ephemeral_observation",
                    capability_requirement="external_observation",
                )
            ],
        )
        async with factory() as session:
            percept = await PerceptionRuntime(port).execute(
                session,
                request=request,
                plan=plan,
                task_run_id=run_id,
            )

        assert len(percept.observation_handles) == 1
        assert len(percept.evidence_handles) == 1
        assert percept.source_roles == ["primary"]
        assert percept.independent_source_keys == [f"family:{PROMOTION_SOURCE.source_family}"]
        assert "required_source_role_missing:primary" not in percept.unresolved
        assert "no_candidates" not in percept.unresolved
        assert percept.cost["external:0:promotion_calls"] == 1
    finally:
        await engine.dispose()
