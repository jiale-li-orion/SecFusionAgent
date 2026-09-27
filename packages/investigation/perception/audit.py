from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.investigation.perception.contracts import (
    Percept,
    PerceptionRequest,
    PhysicalPerceptionPlan,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import (
    EvidenceNeedModel,
    InvestigationCaseModel,
    PerceptionEventModel,
)
from packages.task_runtime.storage.models import TaskRunModel


class PerceptionEventRecord(BaseModel):
    perception_event_id: str
    case_id: str
    task_run_id: str
    request_id: str
    world_revision: int
    percept_ref: str
    replay: bool = False


class PerceptionAuditService:
    def __init__(
        self,
        *,
        state_service: InvestigationStateService | None = None,
    ) -> None:
        self._state_service = state_service or InvestigationStateService()

    async def record(
        self,
        session: AsyncSession,
        *,
        task_run_id: str,
        request: PerceptionRequest,
        plan: PhysicalPerceptionPlan,
        percept: Percept,
        started_at: datetime,
        finished_at: datetime,
        status: str = "completed",
        failure_class: str | None = None,
    ) -> PerceptionEventRecord:
        if request.request_id != plan.request_id or request.request_id != percept.request_id:
            raise ValueError("Perception request/plan/percept identities must match")
        run = await session.get(TaskRunModel, task_run_id)
        if run is None:
            raise LookupError(f"task run not found: {task_run_id}")
        if run.case_id is None:
            raise ValueError("PerceptionEvent requires a Case-bound TaskRun")
        if request.case_id not in {None, run.case_id}:
            raise ValueError("PerceptionRequest case_id escapes TaskRun Case")
        case = await session.get(InvestigationCaseModel, run.case_id)
        if case is None:
            raise RuntimeError("TaskRun references missing Investigation Case")
        if request.need_id is not None:
            need = await session.get(EvidenceNeedModel, request.need_id)
            if need is None or need.case_id != run.case_id:
                raise ValueError("PerceptionRequest need_id does not belong to TaskRun Case")

        existing = await session.scalar(
            select(PerceptionEventModel).where(
                PerceptionEventModel.task_run_id == task_run_id,
                PerceptionEventModel.request_id == request.request_id,
            )
        )
        if existing is not None:
            _require_replay_match(existing, request=request, plan=plan, percept=percept)
            await self._state_service.mark_perception(
                session,
                case_id=existing.case_id,
                perception_event_id=existing.perception_event_id,
                world_revision=existing.world_revision,
                perceived_at=existing.finished_at,
            )
            return _event_record(existing, replay=True)

        world_revision = await current_knowledge_revision(session)
        model = PerceptionEventModel(
            perception_event_id=str(uuid4()),
            case_id=run.case_id,
            task_run_id=task_run_id,
            request_id=request.request_id,
            need_id=request.need_id,
            request_json=request.model_dump(mode="json"),
            plan_json=plan.model_dump(mode="json"),
            percept_ref=f"percept:{percept.percept_id}",
            evidence_refs=sorted(set(percept.evidence_handles)),
            observation_refs=sorted(set(percept.observation_handles)),
            cost=percept.cost,
            world_revision=world_revision,
            status=status,
            failure_class=failure_class,
            started_at=started_at.astimezone(UTC),
            finished_at=finished_at.astimezone(UTC),
        )
        session.add(model)
        await session.flush()
        await self._state_service.mark_perception(
            session,
            case_id=run.case_id,
            perception_event_id=model.perception_event_id,
            world_revision=world_revision,
            perceived_at=model.finished_at,
        )
        return _event_record(model, replay=False)


def _require_replay_match(
    model: PerceptionEventModel,
    *,
    request: PerceptionRequest,
    plan: PhysicalPerceptionPlan,
    percept: Percept,
) -> None:
    expected = (
        request.model_dump(mode="json"),
        plan.model_dump(mode="json"),
        f"percept:{percept.percept_id}",
    )
    actual = (model.request_json, model.plan_json, model.percept_ref)
    if actual != expected:
        raise ValueError("PerceptionEvent replay identity changed payload")


def _event_record(model: PerceptionEventModel, *, replay: bool) -> PerceptionEventRecord:
    return PerceptionEventRecord(
        perception_event_id=model.perception_event_id,
        case_id=model.case_id,
        task_run_id=model.task_run_id,
        request_id=model.request_id,
        world_revision=model.world_revision,
        percept_ref=model.percept_ref,
        replay=replay,
    )
