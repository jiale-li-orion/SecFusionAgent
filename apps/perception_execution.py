from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Protocol, cast

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.investigation.perception.contracts import (
    ObservedProposition,
    PerceptionRequest,
    PerceptionStepResult,
    PhysicalOperator,
    PhysicalPerceptionStep,
)
from packages.runtime.capability.broker import (
    CapabilityBroker,
    CapabilityDenied,
    CapabilityExecutor,
    CapabilityInvocationOutcome,
    InvocationGrants,
    NativeExecutionResult,
)
from packages.runtime.capability.contracts import (
    CapabilityRequest,
    CapabilityResultStatus,
    ExecutionClass,
    ImplementationKind,
    ToolImplementation,
)
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.sandbox.broker import (
    SandboxBroker,
    SandboxCreateRequest,
    SandboxExecRequest,
    SandboxExecResult,
    SandboxGrants,
    SandboxUnavailable,
)
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import TaskContract
from packages.task_runtime.storage.service import get_task_contract_for_run, get_task_run


class ObservationPromotionBinding(BaseModel):
    source_id: str
    target_kind: str
    target_id: str
    locator: dict[str, JsonValue] = Field(default_factory=dict)
    fulfilled_obligation_kinds: set[str] = Field(default_factory=set)


class ExternalPerceptionInvocation(BaseModel):
    request: CapabilityRequest
    estimated_budget: dict[str, Decimal] = Field(default_factory=dict)
    grants: InvocationGrants = Field(default_factory=InvocationGrants)
    healthy_refs: set[str] | None = None
    available_execution_classes: set[ExecutionClass] | None = None
    action_timeout_seconds: float = Field(default=30.0, gt=0)
    promotion: ObservationPromotionBinding | None = None


class SandboxPerceptionInvocation(BaseModel):
    request: CapabilityRequest
    estimated_budget: dict[str, Decimal] = Field(default_factory=dict)
    capability_grants: InvocationGrants = Field(default_factory=InvocationGrants)
    healthy_refs: set[str] | None = None
    available_execution_classes: set[ExecutionClass] | None = None
    action_timeout_seconds: float = Field(default=30.0, gt=0)
    create_request: SandboxCreateRequest
    exec_request: SandboxExecRequest
    sandbox_grants: SandboxGrants = Field(default_factory=SandboxGrants)
    export_paths: list[str] = Field(default_factory=list)


class ObservationPromotionPort(Protocol):
    async def promote(
        self,
        *,
        task_run_id: str,
        task: TaskContract,
        outcome: CapabilityInvocationOutcome,
        binding: ObservationPromotionBinding,
    ) -> PerceptionStepResult: ...


class PerceptionExecutionResolver(Protocol):
    async def resolve_external(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> ExternalPerceptionInvocation: ...

    async def resolve_sandbox(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> SandboxPerceptionInvocation: ...


class PhysicalObservationInterpreter(Protocol):
    def capability(
        self,
        outcome: CapabilityInvocationOutcome,
    ) -> list[ObservedProposition]: ...

    def sandbox(
        self,
        result: SandboxExecResult,
        exported_artifact_refs: list[str],
    ) -> list[ObservedProposition]: ...


class DefaultPhysicalObservationInterpreter:
    """Conservatively expose explicit statements only; never invent factual claims."""

    def capability(
        self,
        outcome: CapabilityInvocationOutcome,
    ) -> list[ObservedProposition]:
        observation = outcome.observation
        if observation is None:
            return []
        support_ref = f"observation:{observation.observation_id}"
        propositions: list[ObservedProposition] = []
        for item in observation.extracted_candidates:
            if not isinstance(item, dict):
                continue
            statement = item.get("statement")
            if not isinstance(statement, str) or not statement.strip():
                continue
            propositions.append(
                ObservedProposition(
                    statement=statement,
                    support_refs=[support_ref],
                    freshness={"observed_at": observation.observed_at.isoformat()},
                )
            )
        return propositions

    def sandbox(
        self,
        result: SandboxExecResult,
        exported_artifact_refs: list[str],
    ) -> list[ObservedProposition]:
        del result, exported_artifact_refs
        return []


class _SandboxCapabilityExecutor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        task: TaskContract,
        envelope: ExecutionEnvelope,
        sandbox_broker: SandboxBroker,
        invocation: SandboxPerceptionInvocation,
        interpreter: PhysicalObservationInterpreter,
    ) -> None:
        self._session = session
        self._task = task
        self._envelope = envelope
        self._sandbox_broker = sandbox_broker
        self._invocation = invocation
        self._interpreter = interpreter

    async def execute(
        self,
        implementation: ToolImplementation,
        *,
        native_arguments: dict[str, JsonValue],
        timeout_seconds: float,
    ) -> NativeExecutionResult:
        if implementation.implementation_kind is not ImplementationKind.SANDBOX_PROGRAM:
            raise ValueError("sandbox perception requires SANDBOX_PROGRAM implementation")
        instance = None
        try:
            instance = await self._sandbox_broker.create(
                self._session,
                task=self._task,
                envelope=self._envelope,
                request=self._invocation.create_request,
                grants=self._invocation.sandbox_grants,
            )
            exec_request = self._invocation.exec_request.model_copy(
                update={
                    "arguments": native_arguments,
                    "requested_timeout_seconds": min(
                        self._invocation.exec_request.requested_timeout_seconds,
                        timeout_seconds,
                    ),
                }
            )
            result = await self._sandbox_broker.exec(
                self._session,
                envelope=self._envelope,
                instance_id=instance.instance_id,
                request=exec_request,
            )
            exports = (
                await self._sandbox_broker.export(
                    self._session,
                    instance_id=instance.instance_id,
                    relative_paths=self._invocation.export_paths,
                )
                if self._invocation.export_paths
                else []
            )
            propositions = self._interpreter.sandbox(result, exports)
            succeeded = result.status == "succeeded"
            raw_artifact_ref = result.stdout_artifact_ref or (exports[0] if exports else None)
            return NativeExecutionResult(
                status=(
                    CapabilityResultStatus.SUCCEEDED if succeeded else CapabilityResultStatus.FAILED
                ),
                canonical_output_ref=f"sandbox-execution:{result.sandbox_execution_id}",
                raw_artifact_ref=raw_artifact_ref,
                provenance={
                    "sandbox_execution_id": result.sandbox_execution_id,
                    "sandbox_operation_id": result.operation_id,
                    "sandbox_status": result.status,
                    "sandbox_exit_code": result.exit_code,
                    "exported_artifact_refs": cast(JsonValue, exports),
                },
                cost={
                    "sandbox_calls": 1,
                    "sandbox_status": result.status,
                    "sandbox_timeout_seconds": result.timeout_seconds,
                },
                consumed_budget=dict(self._invocation.estimated_budget),
                failure_code=(result.failure_code or (None if succeeded else result.status)),
                extracted_candidates=[item.model_dump(mode="json") for item in propositions],
            )
        except SandboxUnavailable as exc:
            return NativeExecutionResult(
                status=CapabilityResultStatus.FAILED,
                consumed_budget=dict(self._invocation.estimated_budget),
                failure_code=f"sandbox_unavailable:{exc}",
                cost={"sandbox_calls": 0},
            )
        finally:
            if instance is not None:
                await self._sandbox_broker.destroy(self._session, instance.instance_id)


class BrokeredPhysicalObservationPort:
    def __init__(
        self,
        *,
        capability_broker: CapabilityBroker,
        capability_executor: CapabilityExecutor | None,
        sandbox_broker: SandboxBroker,
        resolver: PerceptionExecutionResolver,
        session_factory: async_sessionmaker[AsyncSession],
        promotion_port: ObservationPromotionPort | None = None,
        interpreter: PhysicalObservationInterpreter | None = None,
        execution_service: ExecutionRunService | None = None,
        capability_executor_factory: (
            Callable[[AsyncSession, TaskContract, ExecutionEnvelope], CapabilityExecutor] | None
        ) = None,
    ) -> None:
        self._capability_broker = capability_broker
        self._capability_executor = capability_executor
        self._capability_executor_factory = capability_executor_factory
        if capability_executor is None and capability_executor_factory is None:
            raise ValueError("physical observation requires a capability executor")
        self._sandbox_broker = sandbox_broker
        self._resolver = resolver
        self._session_factory = session_factory
        self._promotion_port = promotion_port
        self._interpreter = interpreter or DefaultPhysicalObservationInterpreter()
        self._execution_service = execution_service or ExecutionRunService()

    async def execute(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        if step.operator is PhysicalOperator.EXTERNAL:
            return await self._external(task_run_id=task_run_id, request=request, step=step)
        if step.operator is PhysicalOperator.SANDBOX:
            return await self._sandbox(task_run_id=task_run_id, request=request, step=step)
        raise ValueError(f"physical observation port cannot execute {step.operator.value}")

    async def _external(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        resolved = await self._resolver.resolve_external(
            task_run_id=task_run_id,
            request=request,
            step=step,
        )
        async with self._session_factory() as session:
            task, envelope = await self._load_execution(session, task_run_id)
            executor = (
                self._capability_executor_factory(session, task, envelope)
                if self._capability_executor_factory is not None
                else self._capability_executor
            )
            assert executor is not None
            if resolved.request.task_run_id != task_run_id:
                raise ValueError("resolved CapabilityRequest escapes perception TaskRun")
            try:
                outcome = await self._capability_broker.invoke(
                    session,
                    task=task,
                    envelope=envelope,
                    request=resolved.request,
                    executor=executor,
                    estimated_budget=resolved.estimated_budget,
                    grants=resolved.grants,
                    healthy_refs=resolved.healthy_refs,
                    available_execution_classes=resolved.available_execution_classes,
                    action_timeout_seconds=resolved.action_timeout_seconds,
                )
                await session.commit()
            except CapabilityDenied as exc:
                await session.rollback()
                return PerceptionStepResult(
                    unresolved=[f"capability_denied:{exc}"],
                    cost={"capability_calls": 0},
                )
        if outcome.observation is None:
            return PerceptionStepResult(
                unresolved=[
                    f"capability_no_observation:{outcome.result.status.value}:"
                    f"{outcome.result.failure_code or 'none'}"
                ],
                cost={"capability_calls": 1},
            )
        observation_ref = f"observation:{outcome.observation.observation_id}"
        result = PerceptionStepResult(
            observed_propositions=self._interpreter.capability(outcome),
            observation_handles=[observation_ref],
            cost={
                "capability_calls": 1,
                "capability_status": outcome.result.status.value,
                **outcome.result.cost,
            },
        )
        if resolved.promotion is None:
            return result
        if self._promotion_port is None:
            result.unresolved.append("observation_promotion_unavailable")
            return result
        promoted = await self._promotion_port.promote(
            task_run_id=task_run_id,
            task=task,
            outcome=outcome,
            binding=resolved.promotion,
        )
        return _merge_step_results(result, promoted)

    async def _sandbox(
        self,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        step: PhysicalPerceptionStep,
    ) -> PerceptionStepResult:
        resolved = await self._resolver.resolve_sandbox(
            task_run_id=task_run_id,
            request=request,
            step=step,
        )
        async with self._session_factory() as session:
            task, envelope = await self._load_execution(session, task_run_id)
            if resolved.request.task_run_id != task_run_id:
                raise ValueError("resolved sandbox CapabilityRequest escapes perception TaskRun")
            executor = _SandboxCapabilityExecutor(
                session=session,
                task=task,
                envelope=envelope,
                sandbox_broker=self._sandbox_broker,
                invocation=resolved,
                interpreter=self._interpreter,
            )
            try:
                outcome = await self._capability_broker.invoke(
                    session,
                    task=task,
                    envelope=envelope,
                    request=resolved.request,
                    executor=executor,
                    estimated_budget=resolved.estimated_budget,
                    grants=resolved.capability_grants,
                    healthy_refs=resolved.healthy_refs,
                    available_execution_classes=resolved.available_execution_classes,
                    action_timeout_seconds=resolved.action_timeout_seconds,
                )
                await session.commit()
            except CapabilityDenied as exc:
                await session.rollback()
                return PerceptionStepResult(
                    unresolved=[f"capability_denied:{exc}"],
                    cost={"capability_calls": 0},
                )
        if outcome.observation is None:
            return PerceptionStepResult(
                unresolved=[
                    f"capability_no_observation:{outcome.result.status.value}:"
                    f"{outcome.result.failure_code or 'none'}"
                ],
                cost={"capability_calls": 1, **outcome.result.cost},
            )
        observation_ref = f"observation:{outcome.observation.observation_id}"
        return PerceptionStepResult(
            observed_propositions=self._interpreter.capability(outcome),
            observation_handles=[observation_ref],
            cost={
                "capability_calls": 1,
                "capability_status": outcome.result.status.value,
                **outcome.result.cost,
            },
        )

    async def _load_execution(self, session: AsyncSession, task_run_id: str):
        run = await get_task_run(session, task_run_id)
        task = await get_task_contract_for_run(session, task_run_id)
        envelope = await self._execution_service.get(session, run.execution_envelope_ref)
        return task, envelope


def _merge_step_results(
    left: PerceptionStepResult,
    right: PerceptionStepResult,
) -> PerceptionStepResult:
    return PerceptionStepResult(
        candidates=[*left.candidates, *right.candidates],
        observed_propositions=[
            *left.observed_propositions,
            *right.observed_propositions,
        ],
        observation_handles=sorted(set([*left.observation_handles, *right.observation_handles])),
        unresolved=list(dict.fromkeys([*left.unresolved, *right.unresolved])),
        cost={**left.cost, **right.cost},
    )
