from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.incident_models import SecurityIncidentModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.sources.storage.models import SourceModel


class EvidenceSupportSummary(BaseModel):
    evidence_refs: list[str] = Field(default_factory=list)
    source_roles: list[str] = Field(default_factory=list)
    independent_source_keys: list[str] = Field(default_factory=list)
    supported_object_ids: list[str] = Field(default_factory=list)


class EvidenceDependency(BaseModel):
    evidence_ref: str
    target_kind: str
    target_id: str


async def current_knowledge_revision(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)


async def knowledge_revision_at(session: AsyncSession, instant: datetime) -> int:
    normalized = instant.replace(tzinfo=UTC) if instant.tzinfo is None else instant.astimezone(UTC)
    return int(
        await session.scalar(
            select(func.max(KnowledgeRevisionModel.revision)).where(
                KnowledgeRevisionModel.committed_at <= normalized
            )
        )
        or 0
    )


async def evidence_dependencies(
    session: AsyncSession,
    evidence_refs: list[str],
) -> list[EvidenceDependency]:
    if not evidence_refs:
        return []
    rows = list(
        await session.scalars(
            select(EvidenceLinkModel).where(EvidenceLinkModel.evidence_link_id.in_(evidence_refs))
        )
    )
    return [
        EvidenceDependency(
            evidence_ref=row.evidence_link_id,
            target_kind=row.target_kind,
            target_id=row.target_id,
        )
        for row in rows
    ]


async def validate_object_refs(session: AsyncSession, object_ids: list[str]) -> list[str]:
    missing: list[str] = []
    for object_id in object_ids:
        if await session.get(ObjectModel, object_id) is None:
            missing.append(object_id)
    return missing


async def validate_target_ref(session: AsyncSession, target_ref: str) -> bool:
    kind, separator, identity = target_ref.partition(":")
    if not separator or not identity:
        return False
    if kind == "object":
        return await session.get(ObjectModel, identity) is not None
    if kind == "incident":
        return await session.get(SecurityIncidentModel, identity) is not None
    return False


async def evidence_support_summary(
    session: AsyncSession,
    evidence_refs: list[str],
) -> EvidenceSupportSummary:
    if not evidence_refs:
        return EvidenceSupportSummary()
    rows = (
        await session.execute(
            select(EvidenceLinkModel, ObservationModel, SourceModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id == EvidenceLinkModel.observation_id,
            )
            .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
            .where(EvidenceLinkModel.evidence_link_id.in_(evidence_refs))
        )
    ).all()
    found = sorted({link.evidence_link_id for link, _, _ in rows})
    roles = sorted({source.source_role for _, _, source in rows})
    independence = sorted(
        {
            (
                f"upstream:{source.upstream_source}"
                if source.upstream_source
                else f"family:{source.source_family}"
                if source.source_family
                else f"source:{source.source_id}"
            )
            for _, _, source in rows
        }
    )
    supported_object_ids: set[str] = set()
    for link, _, _ in rows:
        if link.target_kind == "object":
            supported_object_ids.add(link.target_id)
        elif link.target_kind == "claim":
            claim = await session.get(ClaimModel, link.target_id)
            if claim is not None:
                supported_object_ids.add(claim.subject_id)
        elif link.target_kind == "relation":
            relation = await session.get(RelationModel, link.target_id)
            if relation is not None:
                supported_object_ids.add(relation.source_object_id)
                supported_object_ids.add(relation.target_object_id)
    return EvidenceSupportSummary(
        evidence_refs=found,
        source_roles=roles,
        independent_source_keys=independence,
        supported_object_ids=sorted(supported_object_ids),
    )
