from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.incident_models import (
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    ExternalIdentifierModel,
    ObjectModel,
    RelationModel,
)
from packages.intelligence.storage.projection_models import CurrentProjectionModel


class ProjectionWriteResult(BaseModel):
    projection_id: str
    projection_type: str
    subject_id: str
    upstream_revision: int
    changed: bool


class CurrentProjectionService:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def rebuild_knowledge_object(
        self,
        session: AsyncSession,
        *,
        object_id: str,
        upstream_revision: int,
    ) -> ProjectionWriteResult | None:
        obj = await session.get(ObjectModel, object_id)
        if obj is None or obj.object_type != "Vulnerability":
            return None
        projection_type = "current_vulnerability_view"
        data = await _vulnerability_projection(session, obj)
        projection_key = _primary_identifier(data, "cve") or obj.canonical_key
        return await self._upsert(
            session,
            projection_type=projection_type,
            subject_id=obj.object_id,
            projection_key=projection_key,
            data=data,
            upstream_revision=upstream_revision,
        )

    async def rebuild_incident(
        self,
        session: AsyncSession,
        *,
        incident_id: str,
        upstream_revision: int,
    ) -> ProjectionWriteResult | None:
        incident = await session.get(SecurityIncidentModel, incident_id)
        if incident is None:
            return None
        data = await _incident_projection(session, incident)
        return await self._upsert(
            session,
            projection_type="current_incident_view",
            subject_id=incident.incident_id,
            projection_key=incident.incident_id,
            data=data,
            upstream_revision=upstream_revision,
        )

    async def _upsert(
        self,
        session: AsyncSession,
        *,
        projection_type: str,
        subject_id: str,
        projection_key: str,
        data: dict[str, object],
        upstream_revision: int,
    ) -> ProjectionWriteResult:
        existing = await session.scalar(
            select(CurrentProjectionModel).where(
                CurrentProjectionModel.projection_type == projection_type,
                CurrentProjectionModel.subject_id == subject_id,
            )
        )
        if existing is not None and existing.upstream_revision >= upstream_revision:
            return ProjectionWriteResult(
                projection_id=existing.projection_id,
                projection_type=projection_type,
                subject_id=subject_id,
                upstream_revision=existing.upstream_revision,
                changed=False,
            )
        now = self._now()
        if existing is None:
            existing = CurrentProjectionModel(
                projection_id=_stable_id(f"projection:{projection_type}:{subject_id}"),
                projection_type=projection_type,
                subject_id=subject_id,
                projection_key=projection_key,
                data=data,
                upstream_revision=upstream_revision,
                updated_at=now,
            )
            session.add(existing)
        else:
            existing.projection_key = projection_key
            existing.data = data
            existing.upstream_revision = upstream_revision
            existing.updated_at = now
        await session.flush()
        return ProjectionWriteResult(
            projection_id=existing.projection_id,
            projection_type=projection_type,
            subject_id=subject_id,
            upstream_revision=upstream_revision,
            changed=True,
        )


async def get_current_projection(
    session: AsyncSession,
    *,
    projection_type: str,
    projection_key: str,
) -> CurrentProjectionModel | None:
    return await session.scalar(
        select(CurrentProjectionModel).where(
            CurrentProjectionModel.projection_type == projection_type,
            CurrentProjectionModel.projection_key == projection_key,
        )
    )


async def _vulnerability_projection(
    session: AsyncSession,
    obj: ObjectModel,
) -> dict[str, object]:
    identifiers = list(
        await session.scalars(
            select(ExternalIdentifierModel).where(
                ExternalIdentifierModel.object_id == obj.object_id
            )
        )
    )
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

    grouped_ids: dict[str, list[str]] = {}
    for identifier in identifiers:
        grouped_ids.setdefault(identifier.namespace, []).append(identifier.value)
    for values in grouped_ids.values():
        values.sort()

    by_predicate: dict[str, list[dict[str, object]]] = {}
    for claim in claims:
        entry = {
            "claim_id": claim.claim_id,
            "value": claim.value,
            "qualifier": claim.qualifier,
            "origin": claim.origin,
            "revision": claim.created_revision,
        }
        by_predicate.setdefault(claim.predicate, []).append(entry)

    fields: dict[str, object] = {}
    conflict_predicates: list[str] = []
    for predicate, entries in by_predicate.items():
        current = entries[-1]
        distinct_values = {_json_fingerprint(entry["value"]) for entry in entries}
        conflict = len(distinct_values) > 1
        if conflict:
            conflict_predicates.append(predicate)
        fields[predicate] = {
            **current,
            "conflict": conflict,
            "alternatives": entries if conflict else [],
        }

    relation_views: list[dict[str, object]] = []
    for relation in relations:
        target = await session.get(ObjectModel, relation.target_object_id)
        relation_views.append(
            {
                "relation_id": relation.relation_id,
                "type": relation.relation_type,
                "target_id": relation.target_object_id,
                "target_type": target.object_type if target is not None else None,
                "target_key": target.canonical_key if target is not None else None,
                "target_properties": target.properties if target is not None else {},
                "qualifier": relation.qualifier,
                "revision": relation.created_revision,
            }
        )
    return {
        "object_id": obj.object_id,
        "object_type": obj.object_type,
        "canonical_key": obj.canonical_key,
        "properties": obj.properties,
        "identifiers": grouped_ids,
        "fields": fields,
        "conflict_predicates": sorted(conflict_predicates),
        "relations": relation_views,
    }


async def _incident_projection(
    session: AsyncSession,
    incident: SecurityIncidentModel,
) -> dict[str, object]:
    timeline = list(
        await session.scalars(
            select(IncidentTimelineEventModel)
            .where(IncidentTimelineEventModel.incident_id == incident.incident_id)
            .order_by(
                IncidentTimelineEventModel.event_time,
                IncidentTimelineEventModel.event_id,
            )
        )
    )
    source_links = list(
        await session.scalars(
            select(IncidentSourceLinkModel).where(
                IncidentSourceLinkModel.incident_id == incident.incident_id
            )
        )
    )
    return {
        "incident_id": incident.incident_id,
        "candidate_id": incident.candidate_id,
        "incident_type": incident.incident_type,
        "lifecycle": incident.lifecycle,
        "promotion_reason": incident.promotion_reason,
        "current_summary": incident.current_summary,
        "watch_state": incident.watch_state,
        "source_diversity": sorted({link.independence_key for link in source_links}),
        "timeline": [
            {
                "event_id": event.event_id,
                "event_time": event.event_time.isoformat(),
                "observed_at": event.observed_at.isoformat(),
                "event_type": event.event_type,
                "summary": event.summary,
                "source_role": event.source_role,
                "evidence_refs": event.evidence_refs,
                "supersedes_event_id": event.supersedes_event_id,
            }
            for event in timeline
        ],
    }


def _primary_identifier(data: dict[str, object], namespace: str) -> str | None:
    identifiers = data.get("identifiers")
    if not isinstance(identifiers, dict):
        return None
    values = identifiers.get(namespace)
    if not isinstance(values, list) or not values:
        return None
    value = values[0]
    return value if isinstance(value, str) else None


def _json_fingerprint(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
