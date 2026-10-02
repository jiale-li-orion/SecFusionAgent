from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.capability.broker import (
    CapabilityBroker,
    CapabilityDenied,
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
from packages.runtime.policy.contracts import Authorization, PolicyDecisionPoint, PolicyObligation
from packages.runtime.policy.engine import RuntimePolicyRule, StaticPolicyEngine
from packages.runtime.storage.models import CapabilityInvocationModel
from packages.shared.db import Base
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

NOW = datetime(2026, 9, 27, 7, 30, tzinfo=UTC)


class FakeExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.last_arguments: dict[str, object] | None = None
        self.last_timeout: float | None = None

    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        self.calls += 1
        self.last_arguments = dict(native_arguments)
        self.last_timeout = timeout_seconds
        return NativeExecutionResult(
            status=CapabilityResultStatus.SUCCEEDED,
            canonical_output_ref="result:release-v0.21.0",
            raw_artifact_ref="artifact:github-release-v0.21.0",
            provenance={"http_status": 200},
            latency={"seconds": 0.12},
            cost={"external_cost": 0.25},
            consumed_budget={
                "tool_calls": Decimal("1"),
                "external_cost": Decimal("0.25"),
            },
            extracted_candidates=[{"tag": "v0.21.0", "commit": "abc123"}],
        )


class SelfTrustingExecutor(FakeExecutor):
    async def execute(self, implementation, *, native_arguments, timeout_seconds):
        result = await super().execute(
            implementation,
            native_arguments=native_arguments,
            timeout_seconds=timeout_seconds,
        )
        return result.model_copy(update={"trust_label": "trusted_by_tool"})


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _task(run_id: str) -> TaskContract:
    return TaskContract(
        task_contract_id=f"verify:{run_id}",
        contract_revision=1,
        principal="user:alice",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"goal": "verify release contains fix"},
        evidence_contract={"source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"freshness": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "evidence_sufficient"},
        policy_revision="policy-v1",
    )


def _registry() -> CapabilityRegistry:
    input_schema: dict[str, JsonValue] = {"type": "object", "required": ["repo", "tag"]}
    output_schema: dict[str, JsonValue] = {"type": "object"}
    schema_hash = native_schema_hash(input_schema, output_schema)
    implementation = ToolImplementation(
        tool_impl_id="github-api-release",
        implementation_revision=1,
        implementation_kind=ImplementationKind.PROVIDER_API,
        native_name="github.get_release",
        transport="https",
        native_input_schema=input_schema,
        native_output_schema=output_schema,
        server_identity="api.github.com",
        server_origin="https://api.github.com",
        auth_class="github-token",
        network_destinations=["api.github.com:443"],
        health_ref="health:github",
        native_schema_hash=schema_hash,
    )
    contract = CapabilityContract(
        capability_id="github.read_release",
        contract_revision=1,
        action="read",
        applicable_resource_types=["github.release"],
        canonical_input_schema=input_schema,
        canonical_output_schema=output_schema,
        observation_semantics="provider_observation",
        effect_semantics=EffectSemantics.OBSERVATION,
        authority_semantics=["primary_for(repository_release_state)"],
        idempotency="safe",
        reversibility="not_applicable",
        data_ingress_class="public",
        data_egress_class="none",
        failure_semantics=["provider_blocked", "rate_limited"],
        risk_class="low",
    )
    binding = CapabilityBinding(
        binding_id="github-release-api-v1",
        binding_revision=1,
        capability_id=contract.capability_id,
        contract_revision=1,
        tool_impl_id=implementation.tool_impl_id,
        implementation_revision=1,
        canonical_to_native_args={"repo": "repository", "tag": "tag"},
        resource_resolver="identity",
        effect_resolver="contract",
        authority_mapper="source-role:primary",
        execution_class=ExecutionClass.PROXIED_PROVIDER_READ,
        credential_profile="github:read",
        network_profile="github-api",
        sandbox_profile="none",
        health_requirement="healthy",
        cost_class="low",
        latency_class="interactive",
        native_schema_hash=schema_hash,
    )
    return CapabilityRegistry(
        revision="registry-v1",
        contracts=[contract],
        descriptors={
            contract.capability_id: CapabilityDescriptor(
                purpose="Read release metadata",
                obligation_hints=["audit", "network allowlist"],
            )
        },
        implementations=[implementation],
        bindings=[binding],
    )


def _policy() -> StaticPolicyEngine:
    return StaticPolicyEngine(
        policy_revision="policy-v1",
        rules=[
            RuntimePolicyRule(
                policy_id="allow-github-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:*"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                authorization=Authorization.PERMIT,
            ),
            RuntimePolicyRule(
                policy_id="control-github-read",
                policy_revision="policy-v1",
                decision_points=[PolicyDecisionPoint.CAPABILITY_INVOCATION],
                principal_patterns=["user:*"],
                action_patterns=["read"],
                resource_patterns=["repo:*"],
                obligations=[
                    PolicyObligation(kind="require_audit_log"),
                    PolicyObligation(kind="network_allowlist"),
                ],
            ),
        ],
    )


async def _seed_run_and_budget(session, run_id: str) -> tuple[TaskContract, ExecutionEnvelope]:
    task = _task(run_id)
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{task.task_contract_id}@1",
        role_ref="InvestigationRole@1",
        knowledge_revision=0,
        object_refs=["repo:vllm-project/vllm"],
        policy_context_ref="policy-context:policy-v1",
        capability_envelope_ref="capability:github-read-only",
        budget_ref=f"budget:{run_id}",
    )
    await create_task_run(
        session,
        contract=task,
        manifest=manifest,
        role=canonical_roles()["InvestigationRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name="secfusion:task-events:test",
        run_id=run_id,
        now=NOW,
    )
    await BudgetGovernor(now=lambda: NOW).create_account(
        session,
        account_id=f"budget:{run_id}",
        task_run_id=run_id,
        limits=BudgetLimits(
            quantities={
                "tool_calls": Decimal("3"),
                "external_cost": Decimal("2"),
            }
        ),
    )
    envelope = ExecutionEnvelope(
        execution_id=f"execution:{run_id}",
        task_contract_id=task.task_contract_id,
        task_run_id=run_id,
        role_revision="InvestigationRole@1",
        context_manifest_revision=1,
        execution_profile=ExecutionProfile.VERIFY,
        capability_scope=["github.read_release"],
        deadline_at=NOW + timedelta(minutes=5),
        budget_ref=f"budget:{run_id}",
        policy_revision="policy-v1",
        identity_scope=["github:public"],
        network_policy="github-api",
        side_effect_policy="read-only",
        sandbox_profile_revision="none@1",
    )
    return task, envelope


def _request(task: TaskContract, run_id: str, request_id: str = "req-1") -> CapabilityRequest:
    return CapabilityRequest(
        request_id=request_id,
        task_contract_id=task.task_contract_id,
        task_run_id=run_id,
        principal=task.principal,
        capability_id="github.read_release",
        contract_revision=1,
        action="read",
        resource="repo:vllm-project/vllm:release:v0.21.0",
        resource_type="github.release",
        canonical_arguments={"repo": "vllm-project/vllm", "tag": "v0.21.0"},
        intended_effect=EffectSemantics.OBSERVATION,
        evidence_purpose="verify_fix_boundary",
    )


@pytest.mark.asyncio
async def test_broker_executes_only_after_policy_and_budget_and_replays_without_side_effect() -> (
    None
):
    engine, factory = await _database()
    executor = FakeExecutor()
    budget = BudgetGovernor(now=lambda: NOW)
    broker = CapabilityBroker(_registry(), _policy(), budget, now=lambda: NOW)
    run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            task, envelope = await _seed_run_and_budget(session, run_id)

        async with factory() as session, session.begin():
            outcome = await broker.invoke(
                session,
                task=task,
                envelope=envelope,
                request=_request(task, run_id),
                executor=executor,
                estimated_budget={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("1"),
                },
                grants=InvocationGrants(
                    fulfilled_obligation_kinds={"require_audit_log", "network_allowlist"},
                    network_grant_ref="network-grant:github-api",
                ),
                healthy_refs={"health:github"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
            )
            assert outcome.result.status is CapabilityResultStatus.SUCCEEDED
            assert outcome.observation is not None
            assert outcome.observation.trust_label == "untrusted_tool_output"
            assert outcome.observation.raw_result_ref == "artifact:github-release-v0.21.0"
            assert executor.calls == 1
            assert executor.last_arguments == {
                "repository": "vllm-project/vllm",
                "tag": "v0.21.0",
            }
            assert executor.last_timeout == 30.0
            snapshot = await budget.snapshot(session, f"budget:{run_id}")
            assert snapshot.committed["tool_calls"] == Decimal("1.000000")
            assert snapshot.committed["external_cost"] == Decimal("0.250000")
            assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 0
            assert await session.scalar(select(func.count()).select_from(EvidenceLinkModel)) == 0
            audit = await session.scalar(select(CapabilityInvocationModel))
            assert audit is not None
            assert audit.status == "succeeded"
            assert audit.observation_json is not None
            assert audit.policy_decision_ref.startswith("policy-decision:policy-v1:")

        async with factory() as session, session.begin():
            replay = await broker.invoke(
                session,
                task=task,
                envelope=envelope,
                request=_request(task, run_id),
                executor=executor,
                estimated_budget={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("1"),
                },
                grants=InvocationGrants(
                    fulfilled_obligation_kinds={"require_audit_log", "network_allowlist"}
                ),
                healthy_refs={"health:github"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
            )
            assert replay.replay is True
            assert replay.observation is not None
            assert replay.observation.raw_result_ref == "artifact:github-release-v0.21.0"
            assert executor.calls == 1
            snapshot = await budget.snapshot(session, f"budget:{run_id}")
            assert snapshot.committed["tool_calls"] == Decimal("1.000000")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_broker_ignores_executor_attempt_to_upgrade_tool_output_trust() -> None:
    engine, factory = await _database()
    try:
        budget = BudgetGovernor(now=lambda: NOW)
        broker = CapabilityBroker(_registry(), _policy(), budget, now=lambda: NOW)
        run_id = str(uuid4())
        async with factory() as session, session.begin():
            task, envelope = await _seed_run_and_budget(session, run_id)
            outcome = await broker.invoke(
                session,
                task=task,
                envelope=envelope,
                request=_request(task, run_id, request_id="self-trusting-output"),
                executor=SelfTrustingExecutor(),
                estimated_budget={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("1"),
                },
                grants=InvocationGrants(
                    fulfilled_obligation_kinds={"require_audit_log", "network_allowlist"},
                    network_grant_ref="network-grant:github-api",
                ),
                healthy_refs={"health:github"},
                available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
            )
            assert outcome.observation is not None
            assert outcome.observation.trust_label == "untrusted_tool_output"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unsatisfied_policy_obligation_blocks_before_budget_and_execution() -> None:
    engine, factory = await _database()
    executor = FakeExecutor()
    budget = BudgetGovernor(now=lambda: NOW)
    broker = CapabilityBroker(_registry(), _policy(), budget, now=lambda: NOW)
    run_id = str(uuid4())
    try:
        async with factory() as session, session.begin():
            task, envelope = await _seed_run_and_budget(session, run_id)

        async with factory() as session, session.begin():
            with pytest.raises(CapabilityDenied, match="policy_obligation_unsatisfied"):
                await broker.invoke(
                    session,
                    task=task,
                    envelope=envelope,
                    request=_request(task, run_id),
                    executor=executor,
                    estimated_budget={"tool_calls": Decimal("1")},
                    grants=InvocationGrants(fulfilled_obligation_kinds={"require_audit_log"}),
                    healthy_refs={"health:github"},
                    available_execution_classes={ExecutionClass.PROXIED_PROVIDER_READ},
                )
            assert executor.calls == 0
            snapshot = await budget.snapshot(session, f"budget:{run_id}")
            assert snapshot.reserved == {}
            assert snapshot.committed == {}
            assert (
                await session.scalar(select(func.count()).select_from(CapabilityInvocationModel))
                == 0
            )
    finally:
        await engine.dispose()
