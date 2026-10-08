from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.enrichment.runtime.executor import (
    EnrichmentOperatorExecution,
    EnrichmentOperatorExecutor,
)
from packages.enrichment.runtime.operators import EnrichmentOperatorPlan, EnrichmentStatePlanner
from packages.enrichment.runtime.state import (
    EnrichmentAttempt,
    EnrichmentStateBuilder,
    EnrichmentStateSnapshot,
    EnrichmentStatus,
    record_enrichment_attempt,
)
from packages.enrichment.runtime.state_models import EnrichmentAttemptModel
from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.knowledge.vocabulary import EnrichmentDimension
from packages.task_runtime.contracts.models import (
    TaskContract,
    TaskEventType,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.storage.service import (
    append_task_event,
    get_task_contract_for_run,
    get_task_run,
    transition_task_run,
)


class EnrichmentTaskDesiredState(BaseModel):
    target_object_id: str
    cve_id: str
    required_dimensions: list[EnrichmentDimension]
    refresh_dimensions: list[EnrichmentDimension] = Field(default_factory=list)
    terminal_statuses: list[EnrichmentStatus] = Field(
        default_factory=lambda: [
            EnrichmentStatus.RESOLVED,
            EnrichmentStatus.CONFLICT,
            EnrichmentStatus.UNKNOWN,
        ]
    )

    @model_validator(mode="after")
    def validate_contract_shape(self) -> EnrichmentTaskDesiredState:
        if not self.target_object_id.strip():
            raise ValueError("enrichment target_object_id cannot be empty")
        if not self.cve_id.upper().startswith("CVE-"):
            raise ValueError("v1 EnrichmentRole requires a CVE identifier")
        if not self.required_dimensions:
            raise ValueError("enrichment task requires at least one dimension")
        if not set(self.refresh_dimensions) <= set(self.required_dimensions):
            raise ValueError("refresh dimensions must be required by the enrichment task")
        if EnrichmentStatus.MISSING in self.terminal_statuses:
            raise ValueError("missing cannot be a successful enrichment terminal status")
        return self


class EnrichmentTaskResult(BaseModel):
    task_run_id: str
    target_object_id: str
    cve_id: str
    final_world_revision: int
    dimension_status: dict[EnrichmentDimension, EnrichmentStatus]
    attempted_operators: list[str] = Field(default_factory=list)
    blocked_dimensions: list[EnrichmentDimension] = Field(default_factory=list)
    stop_reason: str


class EnrichmentRoleOutcome(BaseModel):
    run_status: TaskRunStatus
    result: EnrichmentTaskResult


@dataclass(frozen=True, slots=True)
class _PlanningFrame:
    contract: TaskContract
    desired: EnrichmentTaskDesiredState
    snapshot: EnrichmentStateSnapshot
    plans: tuple[EnrichmentOperatorPlan, ...]
    attempted_operator_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _ExecutionFrame:
    plan: EnrichmentOperatorPlan
    execution: EnrichmentOperatorExecution
    started_at: datetime
    finished_at: datetime


class EnrichmentRoleRuntime:
    """Closed, deterministic-first M3 enrichment loop on the shared Task Runtime."""

    ROLE_ID = "EnrichmentRole"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        executor: EnrichmentOperatorExecutor,
        *,
        state_builder: EnrichmentStateBuilder | None = None,
        planner: EnrichmentStatePlanner | None = None,
        stream_name: str = "secfusion:task-events",
        max_rounds: int = 8,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._session_factory = session_factory
        self._executor = executor
        self._state_builder = state_builder or EnrichmentStateBuilder()
        self._planner = planner or EnrichmentStatePlanner()
        self._stream_name = stream_name
        self._max_rounds = max_rounds
        self._now = now or (lambda: datetime.now(UTC))

    async def run(self, run_id: str) -> EnrichmentRoleOutcome:
        await self._ensure_running(run_id)

        for round_index in range(1, self._max_rounds + 1):
            frame = await self._plan_frame(run_id)
            completion = self._completion_status(frame)
            if completion is not None and not frame.plans:
                return await self._finish(
                    run_id,
                    frame,
                    target_status=TaskRunStatus.COMPLETED,
                    stop_reason="enrichment_goal_satisfied",
                )
            if not frame.plans:
                return await self._finish(
                    run_id,
                    frame,
                    target_status=TaskRunStatus.BLOCKED,
                    stop_reason="no_eligible_enrichment_operator",
                )

            executions: list[_ExecutionFrame] = []
            for plan in frame.plans:
                started_at = self._now()
                try:
                    execution = await self._executor.execute(
                        plan,
                        cve_id=frame.desired.cve_id,
                        parent_run_id=run_id,
                    )
                except Exception as exc:
                    await self._fail_unexpected(run_id, plan.operator_id, exc)
                    raise
                executions.append(
                    _ExecutionFrame(
                        plan=plan,
                        execution=execution,
                        started_at=started_at,
                        finished_at=self._now(),
                    )
                )

            changed = await self._commit_round(
                run_id,
                frame,
                executions,
                round_index=round_index,
            )
            if not changed:
                # The next planning frame excludes operators already attempted by this TaskRun.
                # It may reveal a newly-enabled deterministic operator; let the next round decide.
                continue

        frame = await self._plan_frame(run_id)
        return await self._finish(
            run_id,
            frame,
            target_status=TaskRunStatus.BLOCKED,
            stop_reason="enrichment_round_budget_exhausted",
        )

    async def _ensure_running(self, run_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            contract = await get_task_contract_for_run(session, run_id)
            _validate_enrichment_run(run.role_id, contract)
            if run.status is TaskRunStatus.SUBMITTED:
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.QUEUED,
                    payload_ref="queue:enrichment",
                    idempotency_key=f"enrichment-queued:{run_id}",
                    stream_name=self._stream_name,
                    producer=self.ROLE_ID,
                    now=self._now(),
                )
                run = await get_task_run(session, run_id)
            if run.status is TaskRunStatus.QUEUED:
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.RUNNING,
                    payload_ref=f"role:{self.ROLE_ID}",
                    idempotency_key=f"enrichment-started:{run_id}",
                    stream_name=self._stream_name,
                    producer=self.ROLE_ID,
                    now=self._now(),
                )
                return
            if run.status is not TaskRunStatus.RUNNING:
                raise ValueError(
                    f"EnrichmentRole cannot execute TaskRun in status={run.status.value}"
                )

    async def _plan_frame(self, run_id: str) -> _PlanningFrame:
        async with self._session_factory() as session, session.begin():
            contract = await get_task_contract_for_run(session, run_id)
            desired = _desired_state(contract)
            snapshot = await self._state_builder.build(
                session,
                desired.target_object_id,
                materialize=True,
                now=self._now(),
            )
            view = await get_object_by_id(session, desired.target_object_id)
            if view is None:
                raise LookupError(f"enrichment target object not found: {desired.target_object_id}")
            cve_identifiers = {item.upper() for item in view.external_identifiers.get("cve", [])}
            if desired.cve_id.upper() not in cve_identifiers:
                raise ValueError(
                    "enrichment target object does not match TaskContract cve_id: "
                    f"{desired.target_object_id} != {desired.cve_id}"
                )
            attempted = frozenset(
                await session.scalars(
                    select(EnrichmentAttemptModel.operator_id)
                    .where(EnrichmentAttemptModel.task_run_id == run_id)
                    .distinct()
                )
            )
            plans = tuple(
                self._planner.plan(
                    snapshot,
                    view,
                    cve_id=desired.cve_id,
                    target_dimensions=set(desired.required_dimensions),
                    refresh_dimensions=set(desired.refresh_dimensions),
                    attempted_operator_ids=set(attempted),
                )
            )
            return _PlanningFrame(
                contract=contract,
                desired=desired,
                snapshot=snapshot,
                plans=plans,
                attempted_operator_ids=attempted,
            )

    async def _commit_round(
        self,
        run_id: str,
        frame: _PlanningFrame,
        executions: list[_ExecutionFrame],
        *,
        round_index: int,
    ) -> bool:
        now = self._now()
        async with self._session_factory() as session, session.begin():
            attempt_ids: list[str] = []
            for item in executions:
                plan = item.plan
                execution = item.execution
                for dimension in plan.relevant_dimensions:
                    attempt_id = _attempt_id(run_id, plan.operator_id, dimension)
                    attempt_ids.append(attempt_id)
                    await record_enrichment_attempt(
                        session,
                        EnrichmentAttempt(
                            attempt_id=attempt_id,
                            target_object_id=frame.desired.target_object_id,
                            requirement_id=(f"enrichment-v1:Vulnerability:{dimension.value}"),
                            dimension=dimension,
                            operator_id=plan.operator_id,
                            task_run_id=run_id,
                            execution_status=execution.status,
                            semantic_outcome=execution.semantic_outcomes.get(dimension),
                            blocked_reason=execution.blocked_reason,
                            evidence_refs=list(execution.evidence_refs),
                            output_refs=list(execution.output_refs),
                            world_revision_before=frame.snapshot.world_revision,
                            world_revision_after=None,
                            started_at=item.started_at,
                            finished_at=item.finished_at,
                        ),
                    )
                await append_task_event(
                    session,
                    task_run_id=run_id,
                    event_type=TaskEventType.PROGRESS,
                    producer=self.ROLE_ID,
                    base_context_revision=(
                        await get_task_run(session, run_id)
                    ).base_context_revision,
                    payload_ref=(
                        f"enrichment-attempt:{plan.operator_id}:"
                        f"{execution.status.value}:round-{round_index}"
                    ),
                    idempotency_key=f"enrichment-attempt:{run_id}:{plan.operator_id}",
                    stream_name=self._stream_name,
                    now=now,
                )

            updated = await self._state_builder.build(
                session,
                frame.desired.target_object_id,
                materialize=True,
                now=now,
            )
            if attempt_ids:
                attempts = list(
                    await session.scalars(
                        select(EnrichmentAttemptModel).where(
                            EnrichmentAttemptModel.attempt_id.in_(attempt_ids)
                        )
                    )
                )
                for attempt in attempts:
                    attempt.world_revision_after = updated.world_revision
            before = _snapshot_signature(frame.snapshot, frame.desired.required_dimensions)
            after = _snapshot_signature(updated, frame.desired.required_dimensions)
            if after != before:
                run = await get_task_run(session, run_id)
                await append_task_event(
                    session,
                    task_run_id=run_id,
                    event_type=TaskEventType.ENRICHMENT_STATE_CHANGED,
                    producer=self.ROLE_ID,
                    base_context_revision=run.base_context_revision,
                    payload_ref=(
                        f"enrichment-state:{updated.target_object_id}@{updated.world_revision}"
                    ),
                    idempotency_key=(
                        f"enrichment-state:{run_id}:{updated.world_revision}:{after[:16]}"
                    ),
                    stream_name=self._stream_name,
                    now=now,
                )
            return after != before

    def _completion_status(self, frame: _PlanningFrame) -> EnrichmentStatus | None:
        states = frame.snapshot.by_dimension()
        allowed = set(frame.desired.terminal_statuses)
        if all(
            states[dimension].status in allowed for dimension in frame.desired.required_dimensions
        ):
            # Completion is per dimension; aggregate value is informational only.
            return EnrichmentStatus.RESOLVED
        return None

    async def _finish(
        self,
        run_id: str,
        frame: _PlanningFrame,
        *,
        target_status: TaskRunStatus,
        stop_reason: str,
    ) -> EnrichmentRoleOutcome:
        states = frame.snapshot.by_dimension()
        blocked = [
            dimension
            for dimension in frame.desired.required_dimensions
            if states[dimension].status is EnrichmentStatus.MISSING
        ]
        attempted = sorted(frame.attempted_operator_ids)
        result = EnrichmentTaskResult(
            task_run_id=run_id,
            target_object_id=frame.desired.target_object_id,
            cve_id=frame.desired.cve_id,
            final_world_revision=frame.snapshot.world_revision,
            dimension_status={
                dimension: states[dimension].status
                for dimension in frame.desired.required_dimensions
            },
            attempted_operators=attempted,
            blocked_dimensions=blocked,
            stop_reason=stop_reason,
        )
        result_ref = _result_ref(result)
        async with self._session_factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=run_id,
                target=target_status,
                payload_ref=result_ref,
                idempotency_key=f"enrichment-terminal:{run_id}:{target_status.value}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                result_ref=result_ref,
                stop_reason=stop_reason,
                now=self._now(),
            )
        return EnrichmentRoleOutcome(run_status=target_status, result=result)

    async def _fail_unexpected(
        self,
        run_id: str,
        operator_id: str,
        exc: Exception,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            if run.status is not TaskRunStatus.RUNNING:
                return
            error_type = type(exc).__name__
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.FAILED,
                payload_ref=f"enrichment-error:{operator_id}:{error_type}",
                idempotency_key=f"enrichment-failed:{run_id}:{operator_id}:{error_type}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                stop_reason=f"unexpected_operator_error:{error_type}",
                now=self._now(),
            )


def _validate_enrichment_run(role_id: str, contract: TaskContract) -> None:
    if role_id != EnrichmentRoleRuntime.ROLE_ID:
        raise ValueError(f"TaskRun role mismatch: expected EnrichmentRole, got {role_id}")
    if contract.task_kind is not TaskKind.ENRICHMENT:
        raise ValueError(f"EnrichmentRole requires ENRICHMENT task, got {contract.task_kind.value}")
    desired = _desired_state(contract)
    if f"object:{desired.target_object_id}" not in contract.target_resources:
        raise ValueError("enrichment TaskContract must scope the target object")
    if contract.completion_predicate.get("type") != "enrichment_dimensions_terminal":
        raise ValueError(
            "EnrichmentRole requires enrichment_dimensions_terminal completion predicate"
        )


def _desired_state(contract: TaskContract) -> EnrichmentTaskDesiredState:
    return EnrichmentTaskDesiredState.model_validate(contract.desired_state)


def _attempt_id(run_id: str, operator_id: str, dimension: EnrichmentDimension) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"secfusion:enrichment-attempt:{run_id}:{operator_id}:{dimension.value}",
        )
    )


def _snapshot_signature(
    snapshot: EnrichmentStateSnapshot,
    dimensions: Iterable[EnrichmentDimension],
) -> str:
    states = snapshot.by_dimension()
    value = "|".join(
        f"{dimension.value}:{states[dimension].status.value}:"
        f"{','.join(states[dimension].accepted_fact_refs)}:"
        f"{','.join(states[dimension].conflict_refs)}"
        for dimension in sorted(set(dimensions), key=lambda item: item.value)
    )
    return sha256(value.encode()).hexdigest()


def _result_ref(result: EnrichmentTaskResult) -> str:
    digest = sha256(result.model_dump_json(exclude_none=True).encode()).hexdigest()[:24]
    return f"enrichment-result:{result.task_run_id}:{digest}"
