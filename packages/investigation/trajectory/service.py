from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.storage.models import (
    InvestigationCaseModel,
    InvestigationTrajectoryModel,
    TrajectoryEventModel,
)

TERMINAL_OUTCOMES = frozenset({"success", "failure", "partial"})


class TrajectoryEvent(BaseModel):
    event_id: str
    trajectory_id: str
    ordinal: int
    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    experience_version_refs: list[str] = Field(default_factory=list)
    artifact_uri: str | None = None
    occurred_at: datetime


class InvestigationTrajectory(BaseModel):
    trajectory_id: str
    case_id: str
    status: str
    outcome: str | None = None
    retrieved_experience_versions: list[str] = Field(default_factory=list)
    used_experience_versions: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None
    latency_ms: int | None = None
    tool_calls: int = 0
    cost: float | None = None
    outcome_summary: dict[str, object] = Field(default_factory=dict)


class TrajectoryService:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def start(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        retrieved_experience_versions: list[str] | None = None,
    ) -> InvestigationTrajectory:
        case = await session.get(InvestigationCaseModel, case_id)
        if case is None:
            raise LookupError(f"investigation case not found: {case_id}")
        if case.status == "closed":
            raise ValueError("cannot start a trajectory for a closed case")
        if case.status == "running":
            running = await session.scalar(
                select(InvestigationTrajectoryModel.trajectory_id).where(
                    InvestigationTrajectoryModel.case_id == case_id,
                    InvestigationTrajectoryModel.status == "running",
                )
            )
            if running is not None:
                raise ValueError("investigation case already has a running trajectory")
        case.status = "running"
        model = InvestigationTrajectoryModel(
            trajectory_id=str(uuid4()),
            case_id=case_id,
            status="running",
            outcome=None,
            retrieved_experience_versions=retrieved_experience_versions or [],
            used_experience_versions=[],
            started_at=self._now(),
            tool_calls=0,
            outcome_summary={},
        )
        session.add(model)
        await session.flush()
        return _trajectory_view(model)

    async def append_event(
        self,
        session: AsyncSession,
        *,
        trajectory_id: str,
        event_type: str,
        payload: dict[str, object] | None = None,
        evidence_refs: list[str] | None = None,
        experience_version_refs: list[str] | None = None,
        artifact_uri: str | None = None,
        occurred_at: datetime | None = None,
    ) -> TrajectoryEvent:
        trajectory = await session.scalar(
            select(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.trajectory_id == trajectory_id)
            .with_for_update()
        )
        if trajectory is None:
            raise LookupError(f"trajectory not found: {trajectory_id}")
        if trajectory.status != "running":
            raise ValueError("trajectory events are appendable only while running")
        last_ordinal = await session.scalar(
            select(func.max(TrajectoryEventModel.ordinal)).where(
                TrajectoryEventModel.trajectory_id == trajectory_id
            )
        )
        ordinal = int(last_ordinal or 0) + 1
        experience_refs = experience_version_refs or []
        event = TrajectoryEventModel(
            event_id=str(uuid4()),
            trajectory_id=trajectory_id,
            ordinal=ordinal,
            event_type=event_type,
            payload=payload or {},
            evidence_refs=evidence_refs or [],
            experience_version_refs=experience_refs,
            artifact_uri=artifact_uri,
            occurred_at=occurred_at or self._now(),
        )
        session.add(event)
        if event_type in {"tool_call", "provider_query"}:
            trajectory.tool_calls += 1
        if experience_refs:
            used = set(trajectory.used_experience_versions)
            used.update(experience_refs)
            trajectory.used_experience_versions = sorted(used)
        await session.flush()
        return _event_view(event)

    async def finish(
        self,
        session: AsyncSession,
        *,
        trajectory_id: str,
        outcome: str,
        outcome_summary: dict[str, object] | None = None,
        cost: float | None = None,
    ) -> InvestigationTrajectory:
        if outcome not in TERMINAL_OUTCOMES:
            raise ValueError(f"unsupported trajectory outcome: {outcome}")
        trajectory = await session.scalar(
            select(InvestigationTrajectoryModel)
            .where(InvestigationTrajectoryModel.trajectory_id == trajectory_id)
            .with_for_update()
        )
        if trajectory is None:
            raise LookupError(f"trajectory not found: {trajectory_id}")
        if trajectory.status == "completed":
            if trajectory.outcome != outcome:
                raise ValueError("completed trajectory outcome is immutable")
            return _trajectory_view(trajectory)
        if trajectory.status != "running":
            raise ValueError(f"trajectory cannot finish from status={trajectory.status}")
        finished_at = self._now()
        trajectory.status = "completed"
        trajectory.outcome = outcome
        trajectory.finished_at = finished_at
        trajectory.latency_ms = max(
            0,
            int((finished_at - _as_utc(trajectory.started_at)).total_seconds() * 1000),
        )
        trajectory.outcome_summary = outcome_summary or {}
        trajectory.cost = cost
        case = await session.get(InvestigationCaseModel, trajectory.case_id)
        if case is not None and case.status == "running":
            case.status = "open"
        await session.flush()
        return _trajectory_view(trajectory)


async def list_events(
    session: AsyncSession,
    trajectory_id: str,
) -> list[TrajectoryEvent]:
    models = list(
        await session.scalars(
            select(TrajectoryEventModel)
            .where(TrajectoryEventModel.trajectory_id == trajectory_id)
            .order_by(TrajectoryEventModel.ordinal)
        )
    )
    return [_event_view(model) for model in models]


def _trajectory_view(model: InvestigationTrajectoryModel) -> InvestigationTrajectory:
    return InvestigationTrajectory(
        trajectory_id=model.trajectory_id,
        case_id=model.case_id,
        status=model.status,
        outcome=model.outcome,
        retrieved_experience_versions=list(model.retrieved_experience_versions),
        used_experience_versions=list(model.used_experience_versions),
        started_at=model.started_at,
        finished_at=model.finished_at,
        latency_ms=model.latency_ms,
        tool_calls=model.tool_calls,
        cost=model.cost,
        outcome_summary=dict(model.outcome_summary),
    )


def _event_view(model: TrajectoryEventModel) -> TrajectoryEvent:
    return TrajectoryEvent(
        event_id=model.event_id,
        trajectory_id=model.trajectory_id,
        ordinal=model.ordinal,
        event_type=model.event_type,
        payload=dict(model.payload),
        evidence_refs=list(model.evidence_refs),
        experience_version_refs=list(model.experience_version_refs),
        artifact_uri=model.artifact_uri,
        occurred_at=model.occurred_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
