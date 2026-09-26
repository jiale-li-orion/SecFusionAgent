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
        results = await self.rebuild_knowledge_object_views(
            session,
            object_id=object_id,
            upstream_revision=upstream_revision,
        )
        return results[0] if results else None

    async def rebuild_knowledge_object_views(
        self,
        session: AsyncSession,
        *,
        object_id: str,
        upstream_revision: int,
    ) -> list[ProjectionWriteResult]:
        obj = await session.get(ObjectModel, object_id)
        if obj is None:
            return []
        if obj.object_type == "Vulnerability":
            data = await _vulnerability_projection(session, obj)
            projection_key = _primary_identifier(data, "cve") or obj.canonical_key
            views = [
                ("current_vulnerability_view", data),
                ("current_affected_versions", _affected_versions_projection(data)),
                ("current_fix_status", _fix_status_projection(data)),
            ]
            return [
                await self._upsert(
                    session,
                    projection_type=projection_type,
                    subject_id=obj.object_id,
                    projection_key=projection_key,
                    data=view_data,
                    upstream_revision=upstream_revision,
                )
                for projection_type, view_data in views
            ]
        if obj.object_type == "Repo":
            data = await _repo_security_projection(session, obj)
            return [
                await self._upsert(
                    session,
                    projection_type="current_repo_security_state",
                    subject_id=obj.object_id,
                    projection_key=obj.canonical_key,
                    data=data,
                    upstream_revision=upstream_revision,
                )
            ]
        return []

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


def _affected_versions_projection(data: dict[str, object]) -> dict[str, object]:
    relations = data.get("relations")
    entries: list[dict[str, object]] = []
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict) or relation.get("type") != "affects-package":
                continue
            qualifier = relation.get("qualifier")
            entries.append(
                {
                    "relation_id": relation.get("relation_id"),
                    "target_id": relation.get("target_id"),
                    "target_key": relation.get("target_key"),
                    "target_properties": relation.get("target_properties", {}),
                    "qualifier": qualifier if isinstance(qualifier, dict) else {},
                    "revision": relation.get("revision"),
                }
            )
    return {
        "object_id": data.get("object_id"),
        "identifiers": data.get("identifiers", {}),
        "affected_entries": entries,
    }


def _fix_status_projection(data: dict[str, object]) -> dict[str, object]:
    relations = data.get("relations")
    fixed_versions: list[dict[str, object]] = []
    fixed_commits: list[dict[str, object]] = []
    fix_relations: list[dict[str, object]] = []
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            relation_type = relation.get("type")
            qualifier = relation.get("qualifier")
            qualifier_dict = qualifier if isinstance(qualifier, dict) else {}
            if relation_type == "affects-package":
                patched = qualifier_dict.get("first_patched_version")
                if isinstance(patched, str) and patched:
                    fixed_versions.append(
                        {
                            "version": patched,
                            "target_key": relation.get("target_key"),
                            "source_id": qualifier_dict.get("source_id"),
                            "relation_id": relation.get("relation_id"),
                        }
                    )
                ranges = qualifier_dict.get("ranges")
                if isinstance(ranges, list):
                    for range_item in ranges:
                        if not isinstance(range_item, dict):
                            continue
                        range_type = str(range_item.get("type", "")).upper()
                        events = range_item.get("events")
                        if not isinstance(events, list):
                            continue
                        for event in events:
                            if not isinstance(event, dict):
                                continue
                            fixed = event.get("fixed")
                            if not isinstance(fixed, str):
                                continue
                            if range_type == "GIT":
                                fixed_commits.append(
                                    {
                                        "sha": fixed,
                                        "repo": range_item.get("repo"),
                                        "target_key": relation.get("target_key"),
                                        "source_id": qualifier_dict.get("source_id"),
                                        "relation_id": relation.get("relation_id"),
                                    }
                                )
                            else:
                                fixed_versions.append(
                                    {
                                        "version": fixed,
                                        "target_key": relation.get("target_key"),
                                        "source_id": qualifier_dict.get("source_id"),
                                        "relation_id": relation.get("relation_id"),
                                    }
                                )
            if relation_type in {"fixed-by", "fixed-in-release", "contains-fix"}:
                fix_relations.append(relation)
                if relation_type == "fixed-by" and relation.get("target_type") == "Commit":
                    target_properties = relation.get("target_properties")
                    properties = target_properties if isinstance(target_properties, dict) else {}
                    sha = properties.get("sha")
                    if isinstance(sha, str) and sha:
                        fixed_commits.append(
                            {
                                "sha": sha,
                                "repo": qualifier_dict.get("repo_url"),
                                "target_key": relation.get("target_key"),
                                "source_id": qualifier_dict.get("source_id"),
                                "relation_id": relation.get("relation_id"),
                                "confirmed": True,
                            }
                        )
    fixed_versions = _dedupe_dicts(fixed_versions, ("version", "target_key", "source_id"))
    fixed_commits = _dedupe_dicts(fixed_commits, ("sha", "repo", "source_id"))
    versions_by_target: dict[str, set[str]] = {}
    for item in fixed_versions:
        value = item.get("version")
        target_key = item.get("target_key")
        if isinstance(value, str) and isinstance(target_key, str):
            versions_by_target.setdefault(target_key, set()).add(value)
    target_status = [
        {
            "target_key": target_key,
            "versions": sorted(versions),
            "conflict": len(versions) > 1,
        }
        for target_key, versions in sorted(versions_by_target.items())
    ]
    return {
        "object_id": data.get("object_id"),
        "identifiers": data.get("identifiers", {}),
        "status": "known" if fixed_versions or fixed_commits or fix_relations else "unknown",
        "fixed_versions": fixed_versions,
        "fixed_commits": fixed_commits,
        "targets": target_status,
        "version_conflict": any(item["conflict"] is True for item in target_status),
        "fix_relations": fix_relations,
    }


def _dedupe_dicts(
    items: list[dict[str, object]],
    keys: tuple[str, ...],
) -> list[dict[str, object]]:
    unique: dict[tuple[str, ...], dict[str, object]] = {}
    for item in items:
        fingerprint = tuple(str(item.get(key, "")) for key in keys)
        existing = unique.get(fingerprint)
        if existing is None or item.get("confirmed") is True:
            unique[fingerprint] = item
    return list(unique.values())


async def _repo_security_projection(
    session: AsyncSession,
    obj: ObjectModel,
) -> dict[str, object]:
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
    inbound = list(
        await session.scalars(
            select(RelationModel)
            .where(
                RelationModel.target_object_id == obj.object_id,
                RelationModel.lifecycle == "accepted",
                RelationModel.superseded_revision.is_(None),
            )
            .order_by(RelationModel.created_revision, RelationModel.relation_id)
        )
    )
    fields: dict[str, object] = {}
    for claim in claims:
        fields[claim.predicate] = {
            "claim_id": claim.claim_id,
            "value": claim.value,
            "qualifier": claim.qualifier,
            "revision": claim.created_revision,
        }
    development_objects: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    for relation in inbound:
        if relation.relation_type != "belongs-to-repo":
            continue
        source = await session.get(ObjectModel, relation.source_object_id)
        if source is None:
            continue
        counts[source.object_type] = counts.get(source.object_type, 0) + 1
        development_objects.append(
            {
                "object_id": source.object_id,
                "object_type": source.object_type,
                "canonical_key": source.canonical_key,
                "properties": source.properties,
                "relation_id": relation.relation_id,
                "revision": relation.created_revision,
            }
        )
    return {
        "object_id": obj.object_id,
        "canonical_key": obj.canonical_key,
        "properties": obj.properties,
        "fields": fields,
        "development_object_counts": counts,
        "development_objects": development_objects,
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
