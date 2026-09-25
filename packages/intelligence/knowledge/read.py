from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    ObjectModel,
)


class EvidenceRef(BaseModel):
    source_id: str
    external_revision: str | None = None
    observed_at: datetime
    canonical_url: str | None = None
    locator: dict[str, object] = Field(default_factory=dict)


class ClaimView(BaseModel):
    claim_id: str
    predicate: str
    value: object
    origin: str
    qualifier: dict[str, object] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class KnowledgeObjectView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    properties: dict[str, object] = Field(default_factory=dict)
    external_identifiers: dict[str, list[str]] = Field(default_factory=dict)
    claims: list[ClaimView] = Field(default_factory=list)


async def get_vulnerability_by_cve(
    session: AsyncSession,
    cve_id: str,
) -> KnowledgeObjectView | None:
    identifier = await session.scalar(
        select(ExternalIdentifierModel).where(
            ExternalIdentifierModel.namespace == "cve",
            ExternalIdentifierModel.value == cve_id.upper(),
        )
    )
    if identifier is None:
        return None
    obj = await session.get(ObjectModel, identifier.object_id)
    if obj is None:
        return None

    identifiers = list(
        await session.scalars(
            select(ExternalIdentifierModel).where(
                ExternalIdentifierModel.object_id == obj.object_id
            )
        )
    )
    claims = list(
        await session.scalars(
            select(ClaimModel).where(
                ClaimModel.subject_id == obj.object_id,
                ClaimModel.lifecycle == "accepted",
                ClaimModel.superseded_revision.is_(None),
            )
        )
    )
    claim_views: list[ClaimView] = []
    for claim in claims:
        links = list(
            await session.scalars(
                select(EvidenceLinkModel).where(
                    EvidenceLinkModel.target_kind == "claim",
                    EvidenceLinkModel.target_id == claim.claim_id,
                )
            )
        )
        evidence: list[EvidenceRef] = []
        for link in links:
            observation = await session.get(ObservationModel, link.observation_id)
            if observation is None:
                continue
            evidence.append(
                EvidenceRef(
                    source_id=observation.source_id,
                    external_revision=observation.external_revision,
                    observed_at=observation.observed_at,
                    canonical_url=observation.canonical_url,
                    locator=link.locator,
                )
            )
        claim_views.append(
            ClaimView(
                claim_id=claim.claim_id,
                predicate=claim.predicate,
                value=claim.value,
                origin=claim.origin,
                qualifier=claim.qualifier,
                evidence=evidence,
            )
        )

    grouped_ids: dict[str, list[str]] = {}
    for item in identifiers:
        grouped_ids.setdefault(item.namespace, []).append(item.value)
    return KnowledgeObjectView(
        object_id=obj.object_id,
        object_type=obj.object_type,
        canonical_key=obj.canonical_key,
        properties=obj.properties,
        external_identifiers=grouped_ids,
        claims=claim_views,
    )
