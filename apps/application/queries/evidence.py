from __future__ import annotations

from typing import cast

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.evidence import (
    EvidenceArtifactView,
    EvidenceDocumentPassageView,
    EvidenceObservationView,
    EvidenceSourceView,
    EvidenceTargetView,
    EvidenceView,
)
from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.sources.storage.models import SourceModel


async def get_evidence_by_ref(session: AsyncSession, evidence_ref: str) -> EvidenceView | None:
    evidence_id = evidence_ref.removeprefix("evidence:")
    link = await session.get(EvidenceLinkModel, evidence_id)
    if link is None:
        return None
    observation = await session.get(ObservationModel, link.observation_id)
    if observation is None:
        return None
    source = await session.get(SourceModel, observation.source_id)
    if source is None:
        return None
    artifact = (
        await session.get(EvidenceArtifactModel, link.artifact_id) if link.artifact_id else None
    )
    target = await _target_view(session, link)
    return EvidenceView(
        evidence_ref=f"evidence:{link.evidence_link_id}",
        source=EvidenceSourceView(
            source_id=source.source_id,
            source_class=source.source_class,
            source_role=source.source_role,
            source_family=source.source_family,
            authority_scope=list(source.authority_scope),
            retention_mode=source.retention_mode,
        ),
        observation=EvidenceObservationView(
            observation_id=observation.observation_id,
            acquisition_trigger=observation.acquisition_trigger,
            external_object_id=observation.external_object_id,
            external_revision=observation.external_revision,
            canonical_url=observation.canonical_url,
            published_at=observation.published_at,
            updated_at=observation.updated_at,
            observed_at=observation.observed_at,
            content_hash=observation.content_hash,
        ),
        target=target,
        locator=cast(dict[str, JsonValue], dict(link.locator)),
        artifact=(
            EvidenceArtifactView(
                artifact_id=artifact.artifact_id,
                media_type=artifact.media_type,
                content_hash=artifact.content_hash,
                trust_class=artifact.trust_class,
                created_at=artifact.created_at,
            )
            if artifact is not None
            else None
        ),
        document_passages=await _public_document_passages(
            session, observation.observation_id, source, artifact
        ),
    )


async def _public_document_passages(
    session: AsyncSession,
    observation_id: str,
    source: SourceModel,
    artifact: EvidenceArtifactModel | None,
) -> list[EvidenceDocumentPassageView]:
    if source.retention_mode != "durable_managed":
        return []
    if source.access_rights.get("classification") != "public":
        return []
    if artifact is not None and artifact.access_rights.get("classification") not in (
        None,
        "public",
    ):
        return []
    revision = await session.scalar(
        select(DocumentRevisionModel)
        .where(DocumentRevisionModel.observation_id == observation_id)
        .order_by(
            DocumentRevisionModel.created_at.desc(),
            DocumentRevisionModel.document_revision_id.desc(),
        )
        .limit(1)
    )
    if revision is None:
        return []
    chunks = list(
        await session.scalars(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_revision_id == revision.document_revision_id)
            .order_by(DocumentChunkModel.ordinal)
            .limit(6)
        )
    )
    return [
        EvidenceDocumentPassageView(
            chunk_ref=f"document-chunk:{chunk.chunk_id}@{revision.document_revision_id}",
            section=chunk.section,
            text=chunk.text[:320],
        )
        for chunk in chunks
    ]


async def _target_view(session: AsyncSession, link: EvidenceLinkModel) -> EvidenceTargetView:
    if link.target_kind == "claim":
        claim = await session.get(ClaimModel, link.target_id)
        if claim is not None:
            return EvidenceTargetView(
                target_kind="claim",
                target_id=claim.claim_id,
                label=claim.predicate,
                detail={
                    "value": cast(JsonValue, claim.value),
                    "origin": claim.origin,
                    "subject_id": claim.subject_id,
                },
            )
    if link.target_kind == "relation":
        relation = await session.get(RelationModel, link.target_id)
        if relation is not None:
            return EvidenceTargetView(
                target_kind="relation",
                target_id=relation.relation_id,
                label=relation.relation_type,
                detail={
                    "origin": relation.origin,
                    "source_object_id": relation.source_object_id,
                    "target_object_id": relation.target_object_id,
                },
            )
    if link.target_kind == "object":
        obj = await session.get(ObjectModel, link.target_id)
        if obj is not None:
            display = obj.properties.get("display_name") or obj.properties.get("title")
            return EvidenceTargetView(
                target_kind="object",
                target_id=obj.object_id,
                label=str(display) if display else obj.canonical_key,
                detail={"object_type": obj.object_type, "canonical_key": obj.canonical_key},
            )
    return EvidenceTargetView(
        target_kind=link.target_kind,
        target_id=link.target_id,
        label=link.target_kind,
    )
