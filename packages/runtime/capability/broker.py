from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.budget.service import BudgetGovernor
from packages.runtime.capability.contracts import (
    CapabilityInvocation,
    CapabilityRequest,
    CapabilityResult,
    CapabilityResultStatus,
    ExecutionClass,
    InvocationPlan,
    ToolImplementation,
    canonical_arguments_digest,
    validate_capability_request,
)
from packages.runtime.capability.observations import EphemeralObservation
from packages.runtime.capability.registry import CapabilityRegistry
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyRequest,
)
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.runtime.storage.models import CapabilityInvocationModel
from packages.task_runtime.contracts.execution import ExecutionEnvelope, bounded_timeout_seconds
from packages.task_runtime.contracts.models import TaskContract


class CapabilityDenied(RuntimeError):
    pass


class NativeExecutionResult(BaseModel):
    status: CapabilityResultStatus
    canonical_output_ref: str | None = None
    raw_artifact_ref: str | None = None
    effect_receipt_ref: str | None = None
    observation_class: str = "ephemeral"
    provenance: dict[str, JsonValue] = Field(default_factory=dict)
    latency: dict[str, JsonValue] = Field(default_factory=dict)
    cost: dict[str, JsonValue] = Field(default_factory=dict)
    consumed_budget: dict[str, Decimal] = Field(default_factory=dict)
    failure_code: str | None = None
    failure_detail: str | None = None
    extracted_candidates: list[JsonValue] = Field(default_factory=list)
    trust_label: str = "untrusted_tool_output"
    observation_ttl_seconds: int = Field(default=900, gt=0)


class CapabilityExecutor(Protocol):
    async def execute(
        self,
        implementation: ToolImplementation,
        *,
        native_arguments: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> NativeExecutionResult: ...


class InvocationGrants(BaseModel):
    fulfilled_obligation_kinds: set[str] = Field(default_factory=set)
    credential_grant_ref: str | None = None
    network_grant_ref: str | None = None
    sandbox_instance_ref: str | None = None


class CapabilityInvocationOutcome(BaseModel):
    invocation: CapabilityInvocation
    plan: InvocationPlan
    policy_decision: PolicyDecision
    result: CapabilityResult
    observation: EphemeralObservation | None = None
    replay: bool = False


class CapabilityBroker:
    def __init__(
        self,
        registry: CapabilityRegistry,
        policy_engine: StaticPolicyEngine,
        budget_governor: BudgetGovernor,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy_engine
        self._budget = budget_governor
        self._now = now or (lambda: datetime.now(UTC))

    async def invoke(
        self,
        session: AsyncSession,
        *,
        task: TaskContract,
        envelope: ExecutionEnvelope,
        request: CapabilityRequest,
        executor: CapabilityExecutor,
        estimated_budget: dict[str, Decimal],
        grants: InvocationGrants,
        healthy_refs: set[str] | None = None,
        available_execution_classes: set[ExecutionClass] | None = None,
        action_timeout_seconds: float = 30.0,
    ) -> CapabilityInvocationOutcome:
        existing = await session.scalar(
            select(CapabilityInvocationModel).where(
                CapabilityInvocationModel.task_run_id == request.task_run_id,
                CapabilityInvocationModel.request_id == request.request_id,
            )
        )
        if existing is not None:
            return _replay_outcome(existing)

        if envelope.task_run_id != request.task_run_id:
            raise CapabilityDenied("execution_envelope_task_run_mismatch")
        if envelope.task_contract_id != request.task_contract_id:
            raise CapabilityDenied("execution_envelope_task_contract_mismatch")
        if envelope.case_id != request.case_id:
            raise CapabilityDenied("execution_envelope_case_mismatch")
        if envelope.policy_revision != self._policy.policy_revision:
            raise CapabilityDenied("execution_envelope_policy_revision_mismatch")
        if request.capability_id not in set(envelope.capability_scope):
            raise CapabilityDenied("capability_outside_execution_envelope_scope")
        if self._now() >= envelope.deadline_at:
            raise CapabilityDenied("execution_deadline_reached")

        contract = self._registry.contract(request.capability_id, request.contract_revision)
        request_errors = validate_capability_request(task, contract, request)
        if request_errors:
            raise CapabilityDenied(",".join(sorted(request_errors)))
        binding, implementation = self._registry.resolve_binding(
            contract,
            healthy_refs=healthy_refs,
            available_execution_classes=available_execution_classes,
        )
        native_arguments = _map_native_arguments(
            request.canonical_arguments, binding.canonical_to_native_args
        )
        args_digest = canonical_arguments_digest(request.canonical_arguments)
        reservation_group_id = f"capability:{request.task_run_id}:{request.request_id}"
        native_arguments_ref = f"native-args:{request.request_id}:{args_digest[:24]}"

        policy_request = PolicyRequest(
            decision_point=PolicyDecisionPoint.CAPABILITY_INVOCATION,
            principal=request.principal,
            action=request.action,
            resource=request.resource,
            context={
                "task_contract_id": request.task_contract_id,
                "task_run_id": request.task_run_id,
                "capability_id": request.capability_id,
                "arguments_digest": args_digest,
                "intended_effect": request.intended_effect.value,
                "evidence_purpose": request.evidence_purpose,
                "budget_ref": envelope.budget_ref,
            },
        )
        decision = self._policy.evaluate(policy_request)
        if decision.authorization is not Authorization.PERMIT:
            raise CapabilityDenied(f"policy_{decision.authorization.value}")
        required_grants = {item.kind for item in [*decision.constraints, *decision.obligations]}
        if not required_grants <= grants.fulfilled_obligation_kinds:
            missing = sorted(required_grants - grants.fulfilled_obligation_kinds)
            raise CapabilityDenied(f"policy_obligation_unsatisfied:{','.join(missing)}")

        await self._budget.reserve(
            session,
            account_id=envelope.budget_ref,
            reservation_group_id=reservation_group_id,
            quantities=estimated_budget,
        )
        plan = InvocationPlan(
            invocation_plan_id=_stable_id(
                f"invocation-plan:{request.task_run_id}:{request.request_id}:{binding.binding_id}"
            ),
            capability_request_ref=f"capability-request:{request.request_id}",
            binding_id=binding.binding_id,
            binding_revision=binding.binding_revision,
            resolved_resource=request.resource,
            resolved_effect=contract.effect_semantics,
            canonical_arguments_digest=args_digest,
            native_arguments_ref=native_arguments_ref,
            execution_class=binding.execution_class,
            credential_requirement=binding.credential_profile,
            network_requirement=binding.network_profile,
            sandbox_requirement=binding.sandbox_profile,
            deadline_at=envelope.deadline_at,
            budget_reservation_ref=f"budget-reservation:{reservation_group_id}",
        )
        started_at = self._now()
        policy_decision_ref = self._policy.decision_ref(policy_request, decision)
        invocation = CapabilityInvocation(
            invocation_id=_stable_id(
                f"capability-invocation:{request.task_run_id}:{request.request_id}"
            ),
            invocation_plan_id=plan.invocation_plan_id,
            policy_decision_ref=policy_decision_ref,
            credential_grant_ref=grants.credential_grant_ref,
            network_grant_ref=grants.network_grant_ref,
            sandbox_instance_ref=grants.sandbox_instance_ref,
            started_at=started_at,
        )
        audit = CapabilityInvocationModel(
            invocation_id=invocation.invocation_id,
            task_run_id=request.task_run_id,
            case_id=request.case_id,
            request_id=request.request_id,
            capability_id=contract.capability_id,
            contract_revision=contract.contract_revision,
            binding_id=binding.binding_id,
            binding_revision=binding.binding_revision,
            tool_impl_id=implementation.tool_impl_id,
            implementation_revision=implementation.implementation_revision,
            request_json=request.model_dump(mode="json"),
            plan_json=plan.model_dump(mode="json"),
            policy_decision_ref=policy_decision_ref,
            policy_decision_json=decision.model_dump(mode="json"),
            arguments_digest=args_digest,
            status="running",
            started_at=started_at,
        )
        session.add(audit)
        await session.flush()

        timeout = bounded_timeout_seconds(
            envelope,
            now=started_at,
            action_timeout_seconds=action_timeout_seconds,
        )
        try:
            native_result = await executor.execute(
                implementation,
                native_arguments=native_arguments,
                timeout_seconds=timeout,
            )
        except Exception as exc:
            await self._budget.commit(
                session,
                account_id=envelope.budget_ref,
                reservation_group_id=reservation_group_id,
                consumed=dict(estimated_budget),
            )
            failed = CapabilityResult(
                invocation_id=invocation.invocation_id,
                status=CapabilityResultStatus.FAILED,
                observation_class="none",
                failure_code="executor_exception",
                failure_detail=type(exc).__name__,
            )
            _finish_audit(audit, failed, None, self._now())
            await session.flush()
            return CapabilityInvocationOutcome(
                invocation=invocation,
                plan=plan,
                policy_decision=decision,
                result=failed,
            )

        await self._budget.commit(
            session,
            account_id=envelope.budget_ref,
            reservation_group_id=reservation_group_id,
            consumed=native_result.consumed_budget,
        )
        result = CapabilityResult(
            invocation_id=invocation.invocation_id,
            status=native_result.status,
            canonical_output_ref=native_result.canonical_output_ref,
            raw_artifact_ref=native_result.raw_artifact_ref,
            effect_receipt_ref=native_result.effect_receipt_ref,
            observation_class=native_result.observation_class,
            provenance=native_result.provenance,
            latency=native_result.latency,
            cost=native_result.cost,
            failure_code=native_result.failure_code,
            failure_detail=native_result.failure_detail,
        )
        observation = _ephemeral_observation(
            request=request,
            implementation=implementation,
            result=result,
            native_result=native_result,
            observed_at=self._now(),
        )
        _finish_audit(audit, result, observation, self._now())
        await session.flush()
        return CapabilityInvocationOutcome(
            invocation=invocation,
            plan=plan,
            policy_decision=decision,
            result=result,
            observation=observation,
        )


def _map_native_arguments(
    canonical: dict[str, JsonValue],
    mapping: dict[str, str],
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in canonical.items():
        result[mapping.get(key, key)] = value
    return result


def _ephemeral_observation(
    *,
    request: CapabilityRequest,
    implementation: ToolImplementation,
    result: CapabilityResult,
    native_result: NativeExecutionResult,
    observed_at: datetime,
) -> EphemeralObservation | None:
    if result.status not in {CapabilityResultStatus.SUCCEEDED, CapabilityResultStatus.PARTIAL}:
        return None
    raw_ref = result.raw_artifact_ref or result.canonical_output_ref
    if raw_ref is None:
        return None
    return EphemeralObservation(
        observation_id=_stable_id(
            f"ephemeral-observation:{request.task_run_id}:{request.request_id}"
        ),
        request_id=request.request_id,
        capability_id=request.capability_id,
        source=f"tool:{implementation.tool_impl_id}@{implementation.implementation_revision}",
        provenance={
            "implementation_kind": implementation.implementation_kind.value,
            "server_identity": implementation.server_identity,
            **native_result.provenance,
        },
        observed_at=observed_at,
        raw_result_ref=raw_ref,
        extracted_candidates=native_result.extracted_candidates,
        # Tool/provider output is never allowed to self-assign authority. The executor may
        # describe payload/provenance, but the broker owns the trust boundary: every external
        # capability result enters the Agent as untrusted EphemeralObservation and must pass
        # promotion/state gates before it can support durable confirmed state.
        trust_label="untrusted_tool_output",
        ttl_seconds=native_result.observation_ttl_seconds,
    )


def _finish_audit(
    audit: CapabilityInvocationModel,
    result: CapabilityResult,
    observation: EphemeralObservation | None,
    finished_at: datetime,
) -> None:
    audit.result_json = result.model_dump(mode="json")
    audit.observation_json = (
        observation.model_dump(mode="json") if observation is not None else None
    )
    audit.status = result.status.value
    audit.finished_at = finished_at
    audit.failure_code = result.failure_code
    audit.failure_detail = result.failure_detail


def _replay_outcome(model: CapabilityInvocationModel) -> CapabilityInvocationOutcome:
    if model.result_json is None or model.finished_at is None:
        raise RuntimeError("capability invocation is already running and cannot be replayed yet")
    plan = InvocationPlan.model_validate(model.plan_json)
    decision = PolicyDecision.model_validate(model.policy_decision_json)
    result = CapabilityResult.model_validate(model.result_json)
    invocation = CapabilityInvocation(
        invocation_id=model.invocation_id,
        invocation_plan_id=plan.invocation_plan_id,
        policy_decision_ref=model.policy_decision_ref,
        started_at=model.started_at,
    )
    observation = (
        EphemeralObservation.model_validate(model.observation_json)
        if model.observation_json is not None
        else None
    )
    return CapabilityInvocationOutcome(
        invocation=invocation,
        plan=plan,
        policy_decision=decision,
        result=result,
        observation=observation,
        replay=True,
    )


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
