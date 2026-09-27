from __future__ import annotations

from datetime import datetime
from typing import cast

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.sources.storage.models import SourceModel


class ContextReadItem(BaseModel):
    kind: str
    source_ref: str
    source_revision: str
    content: JsonValue


class ContextWorldSlice(BaseModel):
    knowledge_revision: int = Field(ge=0)
    items: list[ContextReadItem] = Field(default_factory=list)


async def read_context_world_slice(
    session: AsyncSession,
    *,
    pinned_knowledge_revision: int | None,
    object_refs: list[str],
    relation_refs: list[str],
    evidence_refs: list[str],
) -> ContextWorldSlice:
    """Resolve ContextManifest Evidence World refs against the current read surface.

    Current object properties/identifiers are not historical row versions. Therefore an
    online caller may only materialize this read surface when its pinned revision equals
    the current Knowledge revision. Historical replay must use a dedicated snapshot/replay
    projection rather than reading newer current rows through this function.
    """

    current_revision = await current_knowledge_revision(session)
    if pinned_knowledge_revision is not None and pinned_knowledge_revision != current_revision:
        raise ValueError(
            "pinned knowledge_revision is stale and requires refresh/rebase: "
            f"pinned={pinned_knowledge_revision}, current={current_revision}"
        )

    items: list[ContextReadItem] = []
    revision = str(current_revision)
    for source_ref in sorted(set(object_refs)):
        object_id = _strip_ref_prefix(source_ref, "object")
        obj = await get_object_by_id(session, object_id)
        if obj is None:
            raise LookupError(f"context object_ref not found: {source_ref}")
        items.append(
            ContextReadItem(
                kind="knowledge_object",
                source_ref=source_ref,
                source_revision=revision,
                content=cast(JsonValue, obj.model_dump(mode="json")),
            )
        )

    for source_ref in sorted(set(relation_refs)):
        relation_id = _strip_ref_prefix(source_ref, "relation")
        relation = await session.get(RelationModel, relation_id)
        if (
            relation is None
            or relation.lifecycle != "accepted"
            or relation.superseded_revision is not None
        ):
            raise LookupError(f"context relation_ref not current: {source_ref}")
        source_obj = await session.get(ObjectModel, relation.source_object_id)
        target_obj = await session.get(ObjectModel, relation.target_object_id)
        if source_obj is None or target_obj is None:
            raise RuntimeError("relation references missing object")
        evidence_links = list(
            await session.scalars(
                select(EvidenceLinkModel).where(
                    EvidenceLinkModel.target_kind == "relation",
                    EvidenceLinkModel.target_id == relation_id,
                )
            )
        )
        items.append(
            ContextReadItem(
                kind="knowledge_relation",
                source_ref=source_ref,
                source_revision=str(relation.created_revision),
                content=cast(
                    JsonValue,
                    {
                        "relation_id": relation.relation_id,
                        "source_object_id": relation.source_object_id,
                        "source_object_type": source_obj.object_type,
                        "relation_type": relation.relation_type,
                        "target_object_id": relation.target_object_id,
                        "target_object_type": target_obj.object_type,
                        "qualifier": relation.qualifier,
                        "origin": relation.origin,
                        "created_revision": relation.created_revision,
                        "evidence_refs": sorted(item.evidence_link_id for item in evidence_links),
                    },
                ),
            )
        )

    for source_ref in sorted(set(evidence_refs)):
        evidence_id = _strip_ref_prefix(source_ref, "evidence")
        link = await session.get(EvidenceLinkModel, evidence_id)
        if link is None:
            raise LookupError(f"context evidence_ref not found: {source_ref}")
        observation = await session.get(ObservationModel, link.observation_id)
        if observation is None:
            raise RuntimeError("EvidenceLink references missing Observation")
        source = await session.get(SourceModel, observation.source_id)
        items.append(
            ContextReadItem(
                kind="evidence_reference",
                source_ref=source_ref,
                source_revision=observation.external_revision or observation.observation_id,
                content=cast(
                    JsonValue,
                    {
                        "evidence_ref": source_ref,
                        "target_kind": link.target_kind,
                        "target_id": link.target_id,
                        "observation_id": observation.observation_id,
                        "source_id": observation.source_id,
                        "source_role": source.source_role if source is not None else None,
                        "source_family": source.source_family if source is not None else None,
                        "external_object_id": observation.external_object_id,
                        "external_revision": observation.external_revision,
                        "canonical_url": observation.canonical_url,
                        "published_at": _iso(observation.published_at),
                        "updated_at": _iso(observation.updated_at),
                        "observed_at": _iso(observation.observed_at),
                        "artifact_ref": (
                            f"artifact:{link.artifact_id}" if link.artifact_id else None
                        ),
                        "locator": link.locator,
                    },
                ),
            )
        )

    return ContextWorldSlice(knowledge_revision=current_revision, items=items)


def _strip_ref_prefix(value: str, kind: str) -> str:
    prefix = f"{kind}:"
    return value[len(prefix) :] if value.startswith(prefix) else value


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
