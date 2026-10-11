"""Bounded, bidirectional canonical subgraphs with relation-lifetime replay metadata."""

from __future__ import annotations

import base64
import json
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.knowledge.read import EvidenceRef, _evidence_for_targets
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)

HISTORY_SCOPE = (
    "Stored accepted relation lifetimes in the loaded subgraph only; object labels and evidence "
    "use current stored metadata, which is not fully versioned. Not a complete historical snapshot."
)


class NetworkNodeView(BaseModel):
    object_id: str
    object_type: str
    label: str
    canonical_key: str
    created_revision: int
    created_at: datetime
    evidence_ref: str | None = None
    canonical_object_id: str | None = None
    event_time: datetime | None = None


class NetworkEdgeView(BaseModel):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    origin: str
    qualifier: dict[str, object] = Field(default_factory=dict)
    created_revision: int
    superseded_revision: int | None
    created_at: datetime
    superseded_at: datetime | None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class NetworkView(BaseModel):
    center_id: str
    revision_domain: str = "knowledge"
    nodes: list[NetworkNodeView]
    edges: list[NetworkEdgeView]
    snapshot_revision: int
    next_cursor: str | None = None
    remaining_count: int = 0
    history_scope: str = HISTORY_SCOPE


def _encode_cursor(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _decode_cursor(cursor: str, center: str, focus: str) -> dict[str, object]:
    try:
        if len(cursor) > 2048:
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(cursor))
        if (
            not isinstance(data, dict)
            or data.get("center") != center
            or data.get("focus") != focus
            or not isinstance(data.get("snapshot"), int)
            or data["snapshot"] < 1
            or not isinstance(data.get("score"), int)
            or not isinstance(data.get("newest"), int)
            or not isinstance(data.get("id"), str)
        ):
            raise ValueError
        return data
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid network cursor") from exc


async def get_object_network(
    session: AsyncSession,
    object_id: str,
    *,
    focus_id: str | None = None,
    existing_ids: list[str] | None = None,
    limit: int = 40,
    revision: int | None = None,
    cursor: str | None = None,
) -> NetworkView | None:
    """Page neighbors by evidence count, newest relation revision, then stable object ID.

    The page limit includes center/focus; supplied existing nodes are additional (max 200).
    Every returned edge has both ends in that union. Historical accepted relations remain
    present, allowing local filtering by their creation and supersession revisions.
    """
    focus = focus_id or object_id
    existing = set(existing_ids or [])
    if not 2 <= limit <= 80 or len(existing) > 200:
        raise ValueError("network limit must be 2..80 and existing_ids at most 200")
    if focus != object_id and limit < 3:
        raise ValueError("expansion with a distinct focus requires limit >= 3")
    latest = int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)
    after = _decode_cursor(cursor, object_id, focus) if cursor else None
    if after:
        snapshot = int(str(after["snapshot"]))
        if revision is not None and revision != snapshot:
            raise ValueError("cursor revision does not match requested revision")
    else:
        snapshot = revision if revision is not None else latest
    if snapshot < 1 or snapshot > latest:
        if latest == 0 and revision is None:
            return None
        raise ValueError("network revision is outside stored history")
    anchors = {object_id, focus}
    objects = {
        item.object_id: item
        for item in await session.scalars(
            select(ObjectModel).where(
                ObjectModel.object_id.in_(anchors | existing),
                ObjectModel.created_revision <= snapshot,
            )
        )
    }
    if not anchors.issubset(objects):
        return None
    if len(objects) > 200:
        raise ValueError("network anchors and existing nodes must fit within 200 nodes")

    # Direction-specific indexed lookups avoid loading or scanning unrelated graph rows.
    relation_columns = (
        RelationModel.relation_id.label("relation_id"),
        RelationModel.created_revision.label("created_revision"),
    )
    accepted = (
        RelationModel.lifecycle == "accepted",
        RelationModel.created_revision <= snapshot,
    )
    adjacent = union_all(
        select(RelationModel.target_object_id.label("neighbor"), *relation_columns).where(
            RelationModel.source_object_id == focus, *accepted
        ),
        select(RelationModel.source_object_id.label("neighbor"), *relation_columns).where(
            RelationModel.target_object_id == focus, *accepted
        ),
    ).subquery()
    ranked = (
        select(
            adjacent.c.neighbor,
            func.count(EvidenceLinkModel.evidence_link_id).label("score"),
            func.max(adjacent.c.created_revision).label("newest"),
        )
        .join(ObjectModel, ObjectModel.object_id == adjacent.c.neighbor)
        .outerjoin(
            EvidenceLinkModel,
            and_(
                EvidenceLinkModel.target_kind == "relation",
                EvidenceLinkModel.target_id == adjacent.c.relation_id,
            ),
        )
        .where(
            ObjectModel.created_revision <= snapshot,
            adjacent.c.neighbor.not_in(set(objects)),
        )
        .group_by(adjacent.c.neighbor)
        .subquery()
    )
    page_query = select(ranked)
    if after:
        score, newest, last_id = after["score"], after["newest"], after["id"]
        page_query = page_query.where(
            or_(
                ranked.c.score < score,
                and_(ranked.c.score == score, ranked.c.newest < newest),
                and_(
                    ranked.c.score == score, ranked.c.newest == newest, ranked.c.neighbor > last_id
                ),
            )
        )
    remaining = int(
        await session.scalar(select(func.count()).select_from(page_query.subquery())) or 0
    )
    # A distinct focus consumes a second anchor position, but expansion still makes progress.
    page_size = min(limit - len(anchors), 200 - len(objects))
    page = (
        await session.execute(
            page_query.order_by(
                ranked.c.score.desc(), ranked.c.newest.desc(), ranked.c.neighbor
            ).limit(page_size)
        )
    ).all()
    new_ids = [row.neighbor for row in page]
    if new_ids:
        objects.update(
            {
                item.object_id: item
                for item in await session.scalars(
                    select(ObjectModel).where(ObjectModel.object_id.in_(new_ids))
                )
            }
        )
    relations = list(
        await session.scalars(
            select(RelationModel)
            .where(
                RelationModel.source_object_id.in_(objects),
                RelationModel.target_object_id.in_(objects),
                *accepted,
            )
            .order_by(RelationModel.created_revision, RelationModel.relation_id)
        )
    )
    revision_ids = {item.created_revision for item in objects.values()}
    revision_ids.update(item.created_revision for item in relations)
    revision_ids.update(item.superseded_revision for item in relations if item.superseded_revision)
    timestamps = dict(
        (
            await session.execute(
                select(KnowledgeRevisionModel.revision, KnowledgeRevisionModel.committed_at).where(
                    KnowledgeRevisionModel.revision.in_(revision_ids)
                )
            )
        ).all()
    )
    evidence = await _evidence_for_targets(
        session, {("relation", item.relation_id) for item in relations}
    )
    next_cursor = None
    remaining = max(0, remaining - len(page))
    if remaining and page and len(objects) < 200:
        last = page[-1]
        next_cursor = _encode_cursor(
            {
                "center": object_id,
                "focus": focus,
                "snapshot": snapshot,
                "score": last.score,
                "newest": last.newest,
                "id": last.neighbor,
            }
        )
    order = [
        object_id,
        *sorted(anchors - {object_id}),
        *new_ids,
        *sorted(set(objects) - anchors - set(new_ids)),
    ]
    return NetworkView(
        center_id=object_id,
        nodes=[
            NetworkNodeView(
                object_id=item.object_id,
                object_type=item.object_type,
                label=str(
                    item.properties.get("display_name")
                    or item.properties.get("title")
                    or item.properties.get("name")
                    or item.properties.get("full_name")
                    or item.canonical_key
                ),
                canonical_key=item.canonical_key,
                created_revision=item.created_revision,
                created_at=timestamps[item.created_revision],
            )
            for item in (objects[node_id] for node_id in order)
        ],
        edges=[
            NetworkEdgeView(
                relation_id=item.relation_id,
                source_id=item.source_object_id,
                target_id=item.target_object_id,
                relation_type=item.relation_type,
                origin=item.origin,
                qualifier=item.qualifier,
                created_revision=item.created_revision,
                superseded_revision=item.superseded_revision,
                created_at=timestamps[item.created_revision],
                superseded_at=(
                    timestamps.get(item.superseded_revision)
                    if item.superseded_revision is not None
                    else None
                ),
                evidence=evidence.get(("relation", item.relation_id), []),
            )
            for item in relations
        ],
        snapshot_revision=snapshot,
        next_cursor=next_cursor,
        remaining_count=remaining,
    )
