from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.investigation.cases.service import CaseService
from packages.investigation.perception.audit import PerceptionAuditService
from packages.investigation.perception.contracts import Percept
from packages.investigation.perception.planner import PerceptionPlanner
from packages.investigation.perception.runtime import PerceptionRuntime
from packages.investigation.runtime.contracts import (
    DelegationAction,
    InvestigationActionKind,
    InvestigationDelegationPort,
    InvestigationFrame,
    InvestigationPlanner,
    PerceptionAction,
    StatePatchAction,
    StopAction,
    WaitAction,
)
from packages.investigation.runtime.tasks import InvestigationTaskDesiredState
from packages.investigation.state.contracts import EvidenceNeedStatus
from packages.investigation.state.service import InvestigationStateService
from packages.task_runtime.context.contracts import ContextRefresh
from packages.task_runtime.context.service import refresh_context
from packages.task_runtime.contracts.dependencies import task_dependency_reason
from packages.task_runtime.contracts.models import TaskEventType, TaskKind, TaskRunStatus
from packages.task_runtime.storage.service import (
    append_task_event,
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
    transition_task_run,
    update_task_context,
)


class InvestigationTaskResult(BaseModel):
    task_run_id: str
    case_id: str
    final_case_revision: int
    resolved_need_ids: list[str] = Field(default_factory=list)
    blocked_need_ids: list[str] = Field(default_factory=list)
    open_need_ids: list[str] = Field(default_factory=list)
    iterations: int
    stop_reason: str


class InvestigationRoleOutcome(BaseModel):
    run_status: TaskRunStatus
    result: InvestigationTaskResult


class InvestigationRoleRuntime:
    ROLE_ID = "InvestigationRole"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        planner: InvestigationPlanner,
        *,
        state_service: InvestigationStateService | None = None,
        perception_runtime: PerceptionRuntime | None = None,
        perception_planner: PerceptionPlanner | None = None,
        perception_audit: PerceptionAuditService | None = None,
        delegation_port: InvestigationDelegationPort | None = None,
        case_service: CaseService | None = None,
        stream_name: str = "secfusion:task-events",
        max_iterations: int = 8,
        no_progress_limit: int = 2,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if max_iterations < 1 or no_progress_limit < 1:
            raise ValueError("investigation loop bounds must be positive")
        self._session_factory = session_factory
        self._planner = planner
        self._state_service = state_service or InvestigationStateService()
        self._perception_runtime = perception_runtime or PerceptionRuntime()
        self._perception_planner = perception_planner or PerceptionPlanner()
        self._perception_audit = perception_audit or PerceptionAuditService(
            state_service=self._state_service
        )
        self._delegation_port = delegation_port
        self._case_service = case_service or CaseService(now=now)
        self._stream_name = stream_name
        self._max_iterations = max_iterations
        self._no_progress_limit = no_progress_limit
        self._now = now or (lambda: datetime.now(UTC))

    async def run(self, run_id: str) -> InvestigationRoleOutcome:
        await self._ensure_running(run_id)
        try:
            return await self._run_loop(run_id)
        except Exception as exc:
            await self._fail_unexpected(run_id, exc)
            raise

    async def _run_loop(self, run_id: str) -> InvestigationRoleOutcome:
        last_percept: Percept | None = None
        seen_percept_signal: str | None = None
        no_progress = 0

        for iteration in range(1, self._max_iterations + 1):
            frame = await self._load_frame(run_id, iteration, last_percept)
            await self._refresh_context_for_frame(run_id, frame)
            completion = await self._completion(run_id, frame)
            if completion is not None:
                return completion

            before_revision = frame.state.case_revision
            action = await self._planner.next_action(frame)

            if action.kind is InvestigationActionKind.PERCEIVE:
                assert isinstance(action, PerceptionAction)
                last_percept = await self._execute_perception(run_id, frame, action)
                percept_signal = _percept_signal(last_percept)
                if percept_signal == seen_percept_signal:
                    no_progress += 1
                else:
                    no_progress = 0
                    seen_percept_signal = percept_signal
            elif action.kind is InvestigationActionKind.DELEGATE:
                assert isinstance(action, DelegationAction)
                return await self._delegate(run_id, frame, action, iteration)
            elif action.kind is InvestigationActionKind.PATCH:
                assert isinstance(action, StatePatchAction)
                result = await self._apply_patch(run_id, frame, action)
                last_percept = None
                if result.state.case_revision > before_revision:
                    no_progress = 0
                else:
                    no_progress += 1
            elif action.kind is InvestigationActionKind.WAIT:
                assert isinstance(action, WaitAction)
                if not _desired_state(frame).allow_wait:
                    return await self._finish(
                        run_id,
                        frame,
                        TaskRunStatus.BLOCKED,
                        "waiting_not_allowed",
                        iteration,
                    )
                return await self._wait(run_id, frame, action.reason, iteration)
            else:
                assert isinstance(action, StopAction)
                reason = (
                    f"completion_predicate_unsatisfied:{action.reason}"
                    if action.reason in {"goal_satisfied", "evidence_sufficient"}
                    else action.reason
                )
                return await self._finish(
                    run_id,
                    frame,
                    TaskRunStatus.BLOCKED,
                    reason,
                    iteration,
                )

            if no_progress >= self._no_progress_limit:
                refreshed = await self._load_frame(run_id, iteration, last_percept)
                return await self._finish(
                    run_id,
                    refreshed,
                    TaskRunStatus.BLOCKED,
                    "no_progress",
                    iteration,
                )

        frame = await self._load_frame(run_id, self._max_iterations, last_percept)
        return await self._finish(
            run_id,
            frame,
            TaskRunStatus.BLOCKED,
            "budget_exhausted",
            self._max_iterations,
        )

    async def _ensure_running(self, run_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            contract = await get_task_contract_for_run(session, run_id)
            desired = InvestigationTaskDesiredState.model_validate(contract.desired_state)
            if run.role_id != self.ROLE_ID:
                raise ValueError(f"TaskRun role mismatch: {run.role_id}")
            if run.case_id != desired.case_id:
                raise ValueError("TaskRun case_id does not match TaskContract desired state")
            if run.status in {TaskRunStatus.WAITING_DEPENDENCY, TaskRunStatus.WAITING_INPUT}:
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.QUEUED,
                    payload_ref="queue:investigation-resume",
                    idempotency_key=f"investigation-resume:{run_id}:{run.status.value}",
                    stream_name=self._stream_name,
                    producer=self.ROLE_ID,
                    now=self._now(),
                )
                run = await get_task_run(session, run_id)
            if run.status is TaskRunStatus.SUBMITTED:
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.QUEUED,
                    payload_ref="queue:investigation",
                    idempotency_key=f"investigation-queued:{run_id}",
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
                    idempotency_key=f"investigation-started:{run_id}:{run.base_context_revision}",
                    stream_name=self._stream_name,
                    producer=self.ROLE_ID,
                    now=self._now(),
                )
                return
            if run.status is not TaskRunStatus.RUNNING:
                raise ValueError(f"InvestigationRole cannot run status={run.status.value}")

    async def _load_frame(
        self,
        run_id: str,
        iteration: int,
        last_percept: Percept | None,
    ) -> InvestigationFrame:
        async with self._session_factory() as session, session.begin():
            contract = await get_task_contract_for_run(session, run_id)
            desired = InvestigationTaskDesiredState.model_validate(contract.desired_state)
            state = await self._state_service.get_state(session, desired.case_id)
            needs = await self._state_service.list_evidence_needs(
                session,
                desired.case_id,
                statuses={EvidenceNeedStatus.OPEN, EvidenceNeedStatus.BLOCKED},
            )
            required = set(desired.required_need_ids)
            selected = next(
                (
                    need
                    for need in needs
                    if need.need_id in required and need.status is EvidenceNeedStatus.OPEN
                ),
                None,
            )
            return InvestigationFrame(
                task_run_id=run_id,
                task_contract=contract,
                state=state,
                selected_need=selected,
                iteration=iteration,
                last_percept=last_percept,
            )

    async def _refresh_context_for_frame(
        self,
        run_id: str,
        frame: InvestigationFrame,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            manifest = await get_task_context(session, run_id)
            world_revision = await current_knowledge_revision(session)
            state_ref = f"case:{frame.state.case_id}@{frame.state.case_revision}"
            if (
                manifest.knowledge_revision == world_revision
                and manifest.investigation_state_ref == state_ref
            ):
                return
            refreshed = refresh_context(
                manifest,
                ContextRefresh(
                    context_revision=manifest.context_revision + 1,
                    knowledge_revision=world_revision,
                    investigation_state_ref=state_ref,
                    cache_hint=None,
                ),
            )
            await update_task_context(
                session,
                run_id=run_id,
                manifest=refreshed,
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                now=self._now(),
            )

    async def _completion(
        self,
        run_id: str,
        frame: InvestigationFrame,
    ) -> InvestigationRoleOutcome | None:
        desired = _desired_state(frame)
        async with self._session_factory() as session:
            needs = [
                await self._state_service.get_evidence_need(session, need_id)
                for need_id in desired.required_need_ids
            ]
        if all(need.status is EvidenceNeedStatus.RESOLVED for need in needs):
            return await self._finish(
                run_id,
                frame,
                TaskRunStatus.COMPLETED,
                "evidence_sufficient",
                frame.iteration,
            )
        if not any(need.status is EvidenceNeedStatus.OPEN for need in needs):
            return await self._finish(
                run_id,
                frame,
                TaskRunStatus.BLOCKED,
                "required_evidence_need_unavailable",
                frame.iteration,
            )
        return None

    async def _execute_perception(
        self,
        run_id: str,
        frame: InvestigationFrame,
        action: PerceptionAction,
    ) -> Percept:
        if action.request.case_id not in {None, frame.state.case_id}:
            raise ValueError("PerceptionRequest case_id escapes Investigation Case")
        if frame.selected_need is not None and action.request.need_id not in {
            None,
            frame.selected_need.need_id,
        }:
            raise ValueError("PerceptionRequest need_id escapes selected EvidenceNeed")
        request = action.request.model_copy(
            update={
                "case_id": frame.state.case_id,
                "need_id": frame.selected_need.need_id if frame.selected_need else None,
            }
        )
        plan = self._perception_planner.plan(request)
        started_at = self._now()
        async with self._session_factory() as session:
            percept = await self._perception_runtime.execute(
                session,
                request=request,
                plan=plan,
                task_run_id=run_id,
            )
        finished_at = self._now()
        async with self._session_factory() as session, session.begin():
            await self._perception_audit.record(
                session,
                task_run_id=run_id,
                request=request,
                plan=plan,
                percept=percept,
                started_at=started_at,
                finished_at=finished_at,
            )
            run = await get_task_run(session, run_id)
            await append_task_event(
                session,
                task_run_id=run_id,
                event_type=TaskEventType.EVIDENCE_FOUND,
                producer=self.ROLE_ID,
                base_context_revision=run.base_context_revision,
                payload_ref=f"percept:{percept.percept_id}",
                idempotency_key=f"percept:{run_id}:{request.request_id}",
                stream_name=self._stream_name,
                now=self._now(),
            )
        return percept

    async def _delegate(
        self,
        run_id: str,
        frame: InvestigationFrame,
        action: DelegationAction,
        iteration: int,
    ) -> InvestigationRoleOutcome:
        if self._delegation_port is None:
            return await self._finish(
                run_id,
                frame,
                TaskRunStatus.BLOCKED,
                "delegation_unavailable",
                iteration,
            )
        if action.request.target_object_id not in set(frame.state.targets):
            raise ValueError("delegated enrichment target escapes Investigation Case")
        result = await self._delegation_port.delegate_enrichment(
            parent_run_id=run_id,
            request=action.request,
        )
        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            await append_task_event(
                session,
                task_run_id=run_id,
                event_type=TaskEventType.PROGRESS,
                producer=self.ROLE_ID,
                base_context_revision=run.base_context_revision,
                payload_ref=f"child-task:{result.child_run_id}",
                idempotency_key=(
                    f"investigation-delegated:{run_id}:{action.request.delegation_id}"
                ),
                stream_name=self._stream_name,
                now=self._now(),
            )
        return await self._wait(
            run_id,
            frame,
            task_dependency_reason(result.child_run_id),
            iteration,
        )

    async def _apply_patch(
        self,
        run_id: str,
        frame: InvestigationFrame,
        action: StatePatchAction,
    ):
        patch = action.patch
        if patch.case_id != frame.state.case_id:
            raise ValueError("StatePatch case_id escapes Investigation Case")
        if patch.base_case_revision != frame.state.case_revision:
            raise ValueError("Planner emitted StatePatch against stale frame revision")
        async with self._session_factory() as session, session.begin():
            result = await self._state_service.apply_patch(session, patch)
            run = await get_task_run(session, run_id)
            await append_task_event(
                session,
                task_run_id=run_id,
                event_type=TaskEventType.INVESTIGATION_STATE_CHANGED,
                producer=self.ROLE_ID,
                base_context_revision=run.base_context_revision,
                payload_ref=f"investigation-state:{frame.state.case_id}@{result.state.case_revision}",
                idempotency_key=f"investigation-state:{run_id}:{patch.patch_id}",
                stream_name=self._stream_name,
                now=self._now(),
            )
            return result

    async def _wait(
        self,
        run_id: str,
        frame: InvestigationFrame,
        reason: str,
        iteration: int,
    ) -> InvestigationRoleOutcome:
        if (
            frame.task_contract.task_kind is TaskKind.WATCH_INCIDENT
            and reason == "waiting_for_world_update"
        ):
            return await self._park_watch_episode(run_id, frame, reason, iteration)
        result = await self._result(frame, run_id, iteration, reason)
        async with self._session_factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.WAITING_DEPENDENCY,
                payload_ref=f"investigation-wait:{reason}",
                idempotency_key=f"investigation-wait:{run_id}:{frame.state.case_revision}:{reason}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                stop_reason=reason,
                now=self._now(),
            )
        return InvestigationRoleOutcome(
            run_status=TaskRunStatus.WAITING_DEPENDENCY,
            result=result,
        )

    async def _park_watch_episode(
        self,
        run_id: str,
        frame: InvestigationFrame,
        reason: str,
        iteration: int,
    ) -> InvestigationRoleOutcome:
        result = await self._result(frame, run_id, iteration, reason)
        result_ref = _result_ref(result)
        async with self._session_factory() as session, session.begin():
            await self._case_service.activate(session, frame.state.case_id)
            await self._case_service.wait(session, frame.state.case_id)
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.COMPLETED,
                payload_ref=result_ref,
                idempotency_key=f"watch-parked:{run_id}:{frame.state.case_revision}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                result_ref=result_ref,
                stop_reason=reason,
                now=self._now(),
            )
        return InvestigationRoleOutcome(
            run_status=TaskRunStatus.COMPLETED,
            result=result,
        )

    async def _finish(
        self,
        run_id: str,
        frame: InvestigationFrame,
        status: TaskRunStatus,
        reason: str,
        iteration: int,
    ) -> InvestigationRoleOutcome:
        result = await self._result(frame, run_id, iteration, reason)
        result_ref = _result_ref(result)
        async with self._session_factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=run_id,
                target=status,
                payload_ref=result_ref,
                idempotency_key=f"investigation-terminal:{run_id}:{status.value}:{reason}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                result_ref=result_ref,
                stop_reason=reason,
                now=self._now(),
            )
        return InvestigationRoleOutcome(run_status=status, result=result)

    async def _fail_unexpected(self, run_id: str, exc: Exception) -> None:
        async with self._session_factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            if run.status is not TaskRunStatus.RUNNING:
                return
            error_type = type(exc).__name__
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.FAILED,
                payload_ref=f"investigation-error:{error_type}",
                idempotency_key=f"investigation-failed:{run_id}:{error_type}",
                stream_name=self._stream_name,
                producer=self.ROLE_ID,
                stop_reason=f"unexpected_runtime_error:{error_type}",
                now=self._now(),
            )

    async def _result(
        self,
        frame: InvestigationFrame,
        run_id: str,
        iteration: int,
        reason: str,
    ) -> InvestigationTaskResult:
        desired = _desired_state(frame)
        async with self._session_factory() as session:
            needs = [
                await self._state_service.get_evidence_need(session, need_id)
                for need_id in desired.required_need_ids
            ]
        return InvestigationTaskResult(
            task_run_id=run_id,
            case_id=desired.case_id,
            final_case_revision=frame.state.case_revision,
            resolved_need_ids=[
                need.need_id for need in needs if need.status is EvidenceNeedStatus.RESOLVED
            ],
            blocked_need_ids=[
                need.need_id for need in needs if need.status is EvidenceNeedStatus.BLOCKED
            ],
            open_need_ids=[
                need.need_id for need in needs if need.status is EvidenceNeedStatus.OPEN
            ],
            iterations=iteration,
            stop_reason=reason,
        )


def _desired_state(frame: InvestigationFrame) -> InvestigationTaskDesiredState:
    return InvestigationTaskDesiredState.model_validate(frame.task_contract.desired_state)


def _percept_signal(percept: Percept) -> str:
    value = "|".join(
        [
            *sorted(percept.evidence_handles),
            *sorted(percept.independent_source_keys),
            *sorted(percept.unresolved),
        ]
    )
    return sha256(value.encode()).hexdigest()


def _result_ref(result: InvestigationTaskResult) -> str:
    digest = sha256(result.model_dump_json(exclude_none=True).encode()).hexdigest()[:24]
    return f"investigation-result:{result.task_run_id}:{digest}"
