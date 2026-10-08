from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)


class EvidenceRef(BaseModel):
    evidence_ref: str
    source_id: str
    observation_id: str
    artifact_id: str | None = None
    external_object_id: str
    external_revision: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    observed_at: datetime
    canonical_url: str | None = None
    locator: dict[str, object] = Field(default_factory=dict)


class ClaimView(BaseModel):
    claim_id: str
    predicate: str
    value: object
    origin: str
    qualifier: dict[str, object] = Field(default_factory=dict)
    created_revision: int
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RelationTargetView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    properties: dict[str, object] = Field(default_factory=dict)
    external_identifiers: dict[str, list[str]] = Field(default_factory=dict)


class RelationView(BaseModel):
    relation_id: str
    relation_type: str
    origin: str
    qualifier: dict[str, object] = Field(default_factory=dict)
    created_revision: int
    target: RelationTargetView
    evidence: list[EvidenceRef] = Field(default_factory=list)


class KnowledgeObjectView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    properties: dict[str, object] = Field(default_factory=dict)
    external_identifiers: dict[str, list[str]] = Field(default_factory=dict)
    claims: list[ClaimView] = Field(default_factory=list)
    relations: list[RelationView] = Field(default_factory=list)


async def get_vulnerability_by_cve(
    session: AsyncSession,
    cve_id: str,
) -> KnowledgeObjectView | None:
    return await get_object_by_identifier(session, "cve", cve_id.upper())


async def get_object_by_identifier(
    session: AsyncSession,
    namespace: str,
    value: str,
) -> KnowledgeObjectView | None:
    identifier = await session.scalar(
        select(ExternalIdentifierModel).where(
            ExternalIdentifierModel.namespace == namespace,
            ExternalIdentifierModel.value == value,
        )
    )
    if identifier is None:
        return None
    return await get_object_by_id(session, identifier.object_id)


async def get_object_by_id(
    session: AsyncSession,
    object_id: str,
) -> KnowledgeObjectView | None:
    obj = await session.get(ObjectModel, object_id)
    if obj is None:
        return None
    claims = list(
        await session.scalars(
            select(ClaimModel)
            .where(
                ClaimModel.subject_id == obj.object_id,
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
            )
            .order_by(ClaimModel.created_revision, ClaimModel.claim_id)
        )
    )
    relations = list(
        await session.scalars(
            select(RelationModel)
            .where(
                RelationModel.source_object_id == obj.object_id,
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
            )
            .order_by(RelationModel.created_revision, RelationModel.relation_id)
        )
    )

    target_ids = {relation.target_object_id for relation in relations}
    targets = (
        {
            target.object_id: target
            for target in await session.scalars(
                select(ObjectModel).where(ObjectModel.object_id.in_(target_ids))
            )
        }
        if target_ids
        else {}
    )
    identifiers = await _identifiers_for_objects(session, {obj.object_id, *target_ids})
    evidence = await _evidence_for_targets(
        session,
        {("claim", claim.claim_id) for claim in claims}
        | {("relation", relation.relation_id) for relation in relations},
    )

    claim_views = [
        ClaimView(
            claim_id=claim.claim_id,
            predicate=claim.predicate,
            value=claim.value,
            origin=claim.origin,
            qualifier=claim.qualifier,
            created_revision=claim.created_revision,
            evidence=evidence.get(("claim", claim.claim_id), []),
        )
        for claim in claims
    ]
    relation_views: list[RelationView] = []
    for relation in relations:
        target = targets.get(relation.target_object_id)
        if target is None:
            continue
        relation_views.append(
            RelationView(
                relation_id=relation.relation_id,
                relation_type=relation.relation_type,
                origin=relation.origin,
                qualifier=relation.qualifier,
                created_revision=relation.created_revision,
                target=RelationTargetView(
                    object_id=target.object_id,
                    object_type=target.object_type,
                    canonical_key=target.canonical_key,
                    properties=target.properties,
                    external_identifiers=identifiers.get(target.object_id, {}),
                ),
                evidence=evidence.get(("relation", relation.relation_id), []),
            )
        )

    return KnowledgeObjectView(
        object_id=obj.object_id,
        object_type=obj.object_type,
        canonical_key=obj.canonical_key,
        properties=obj.properties,
        external_identifiers=identifiers.get(obj.object_id, {}),
        claims=claim_views,
        relations=relation_views,
    )


async def _identifiers_for_objects(
    session: AsyncSession,
    object_ids: set[str],
) -> dict[str, dict[str, list[str]]]:
    identifiers = list(
        await session.scalars(
            select(ExternalIdentifierModel).where(ExternalIdentifierModel.object_id.in_(object_ids))
        )
    )
    grouped: dict[str, dict[str, list[str]]] = {}
    for item in identifiers:
        grouped.setdefault(item.object_id, {}).setdefault(item.namespace, []).append(item.value)
    for namespaces in grouped.values():
        for values in namespaces.values():
            values.sort()
    return grouped


async def _evidence_for_targets(
    session: AsyncSession,
    targets: set[tuple[str, str]],
) -> dict[tuple[str, str], list[EvidenceRef]]:
    if not targets:
        return {}
    links = list(
        await session.scalars(
            select(EvidenceLinkModel).where(
                tuple_(EvidenceLinkModel.target_kind, EvidenceLinkModel.target_id).in_(targets)
            )
        )
    )
    observations = (
        {
            observation.observation_id: observation
            for observation in await session.scalars(
                select(ObservationModel).where(
                    ObservationModel.observation_id.in_({link.observation_id for link in links})
                )
            )
        }
        if links
        else {}
    )
    evidence: dict[tuple[str, str], list[EvidenceRef]] = {}
    for link in links:
        observation = observations.get(link.observation_id)
        if observation is None:
            continue
        evidence.setdefault((link.target_kind, link.target_id), []).append(
            EvidenceRef(
                evidence_ref=f"evidence:{link.evidence_link_id}",
                source_id=observation.source_id,
                observation_id=observation.observation_id,
                artifact_id=link.artifact_id,
                external_object_id=observation.external_object_id,
                external_revision=observation.external_revision,
                published_at=observation.published_at,
                updated_at=observation.updated_at,
                observed_at=observation.observed_at,
                canonical_url=observation.canonical_url,
                locator=link.locator,
            )
        )
    for items in evidence.values():
        items.sort(key=lambda item: (item.observed_at, item.source_id, item.observation_id))
    return evidence
