from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationSnapshotModel


class InvestigationSnapshot(BaseModel):
    snapshot_id: str
    case_id: str
    case_revision: int
    knowledge_revision: int | None = None
    incident_revision: str | None = None
    document_index_revision: str | None = None
    experience_revision: str | None = None
    policy_revision: str
    capability_registry_revision: str | None = None
    routing_query_planner_revision: str | None = None
    model_revision: str | None = None
    prompt_assembly_revision: str | None = None
    source_availability_snapshot: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class InvestigationSnapshotService:
    def __init__(self, *, state_service: InvestigationStateService | None = None) -> None:
        self._state_service = state_service or InvestigationStateService()

    async def create(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        policy_revision: str,
        knowledge_revision: int | None = None,
        incident_revision: str | None = None,
        document_index_revision: str | None = None,
        experience_revision: str | None = None,
        capability_registry_revision: str | None = None,
        routing_query_planner_revision: str | None = None,
        model_revision: str | None = None,
        prompt_assembly_revision: str | None = None,
        source_availability_snapshot: dict[str, object] | None = None,
        created_at: datetime | None = None,
    ) -> InvestigationSnapshot:
        if not policy_revision.strip():
            raise ValueError("InvestigationSnapshot policy_revision cannot be empty")
        state = await self._state_service.get_state(session, case_id)
        latest_world_revision = await current_knowledge_revision(session)
        pinned_world_revision = (
            latest_world_revision if knowledge_revision is None else knowledge_revision
        )
        if pinned_world_revision is not None:
            if pinned_world_revision < 0:
                raise ValueError("InvestigationSnapshot knowledge_revision cannot be negative")
            if latest_world_revision is not None and pinned_world_revision > latest_world_revision:
                raise ValueError("InvestigationSnapshot cannot pin a future knowledge revision")
        model = InvestigationSnapshotModel(
            snapshot_id=str(uuid4()),
            case_id=case_id,
            case_revision=state.case_revision,
            knowledge_revision=pinned_world_revision,
            incident_revision=incident_revision,
            document_index_revision=document_index_revision,
            experience_revision=experience_revision,
            policy_revision=policy_revision,
            capability_registry_revision=capability_registry_revision,
            routing_query_planner_revision=routing_query_planner_revision,
            model_revision=model_revision,
            prompt_assembly_revision=prompt_assembly_revision,
            source_availability_snapshot=dict(source_availability_snapshot or {}),
            created_at=(created_at or datetime.now(UTC)),
        )
        session.add(model)
        await session.flush()
        return _snapshot_view(model)

    async def get(self, session: AsyncSession, snapshot_id: str) -> InvestigationSnapshot:
        model = await session.get(InvestigationSnapshotModel, snapshot_id)
        if model is None:
            raise LookupError(f"investigation snapshot not found: {snapshot_id}")
        return _snapshot_view(model)


def _snapshot_view(model: InvestigationSnapshotModel) -> InvestigationSnapshot:
    return InvestigationSnapshot(
        snapshot_id=model.snapshot_id,
        case_id=model.case_id,
        case_revision=model.case_revision,
        knowledge_revision=model.knowledge_revision,
        incident_revision=model.incident_revision,
        document_index_revision=model.document_index_revision,
        experience_revision=model.experience_revision,
        policy_revision=model.policy_revision,
        capability_registry_revision=model.capability_registry_revision,
        routing_query_planner_revision=model.routing_query_planner_revision,
        model_revision=model.model_revision,
        prompt_assembly_revision=model.prompt_assembly_revision,
        source_availability_snapshot=dict(model.source_availability_snapshot),
        created_at=_utc_datetime(model.created_at),
    )


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
