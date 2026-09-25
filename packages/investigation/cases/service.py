from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.storage.models import (
    InvestigationCaseModel,
    InvestigationTrajectoryModel,
)


class InvestigationCase(BaseModel):
    case_id: str
    task_signature: str
    target_object_ids: list[str] = Field(default_factory=list)
    goal: str
    initial_knowledge_revision: int | None = None
    constraints: dict[str, object] = Field(default_factory=dict)
    rubric: dict[str, object] = Field(default_factory=dict)
    status: str
    created_at: datetime
    closed_at: datetime | None = None


class CaseService:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def create(
        self,
        session: AsyncSession,
        *,
        task_signature: str,
        target_object_ids: list[str],
        goal: str,
        initial_knowledge_revision: int | None,
        constraints: dict[str, object] | None = None,
        rubric: dict[str, object] | None = None,
    ) -> InvestigationCase:
        now = self._now()
        model = InvestigationCaseModel(
            case_id=str(uuid4()),
            task_signature=task_signature,
            target_object_ids=target_object_ids,
            goal=goal,
            initial_knowledge_revision=initial_knowledge_revision,
            constraints=constraints or {},
            rubric=rubric or {},
            status="open",
            created_at=now,
        )
        session.add(model)
        await session.flush()
        return _case_view(model)

    async def close(
        self,
        session: AsyncSession,
        case_id: str,
    ) -> InvestigationCase:
        model = await session.scalar(
            select(InvestigationCaseModel)
            .where(InvestigationCaseModel.case_id == case_id)
            .with_for_update()
        )
        if model is None:
            raise LookupError(f"investigation case not found: {case_id}")
        if model.status == "closed":
            return _case_view(model)
        running_trajectory = await session.scalar(
            select(InvestigationTrajectoryModel.trajectory_id).where(
                InvestigationTrajectoryModel.case_id == case_id,
                InvestigationTrajectoryModel.status == "running",
            )
        )
        if running_trajectory is not None:
            raise ValueError("cannot close an investigation case with a running trajectory")
        model.status = "closed"
        model.closed_at = self._now()
        await session.flush()
        return _case_view(model)


def _case_view(model: InvestigationCaseModel) -> InvestigationCase:
    return InvestigationCase(
        case_id=model.case_id,
        task_signature=model.task_signature,
        target_object_ids=list(model.target_object_ids),
        goal=model.goal,
        initial_knowledge_revision=model.initial_knowledge_revision,
        constraints=dict(model.constraints),
        rubric=dict(model.rubric),
        status=model.status,
        created_at=model.created_at,
        closed_at=model.closed_at,
    )
