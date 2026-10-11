"""Incident-record associations, explicitly separate from canonical knowledge relations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.knowledge.network import (
    NetworkEdgeView,
    NetworkNodeView,
    NetworkView,
    _decode_cursor,
    _encode_cursor,
)
from packages.intelligence.knowledge.read import EvidenceRef, _evidence_for_targets
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.intelligence.storage.knowledge_models import ClaimModel, ObjectModel

RECORD_CAP = 200


async def get_incident_network(
    session: AsyncSession,
    incident_id: str,
    *,
    focus_id: str | None = None,
    existing_ids: list[str] | None = None,
    limit: int = 40,
    revision: int | None = None,
    cursor: str | None = None,
) -> NetworkView | None:
    focus = focus_id or incident_id
    existing = set(existing_ids or [])
    if not 2 <= limit <= 80 or len(existing) > 200:
        raise ValueError("network limit must be 2..80 and existing_ids at most 200")
    if focus != incident_id and limit < 3:
        raise ValueError("expansion with a distinct focus requires limit >= 3")
    incident = await session.get(SecurityIncidentModel, incident_id)
    if incident is None:
        return None
    after = _decode_cursor(cursor, incident_id, focus) if cursor else None
    snapshot = (
        int(str(after["snapshot"]))
        if after
        else (revision if revision is not None else incident.current_revision)
    )
    if after and revision is not None and revision != snapshot:
        raise ValueError("cursor revision does not match requested revision")
    if snapshot < incident.created_revision:
        return None
    if snapshot > incident.current_revision:
        raise ValueError("network revision is outside stored incident history")
    events = list(
        await session.scalars(
            select(IncidentTimelineEventModel)
            .where(
                IncidentTimelineEventModel.incident_id == incident_id,
                IncidentTimelineEventModel.created_revision <= snapshot,
            )
            .order_by(
                IncidentTimelineEventModel.created_revision.desc(),
                IncidentTimelineEventModel.event_id,
            )
            .limit(RECORD_CAP + 1)
        )
    )
    sources = list(
        await session.scalars(
            select(IncidentSourceLinkModel)
            .where(
                IncidentSourceLinkModel.incident_id == incident_id,
                IncidentSourceLinkModel.created_revision <= snapshot,
            )
            .order_by(
                IncidentSourceLinkModel.created_revision.desc(),
                IncidentSourceLinkModel.source_link_id,
            )
            .limit(RECORD_CAP + 1)
        )
    )
    truncated = len(events) > RECORD_CAP or len(sources) > RECORD_CAP
    events, sources = events[:RECORD_CAP], sources[:RECORD_CAP]
    claim_ids = sorted({ref.removeprefix("claim:") for e in events for ref in e.claim_refs})
    observation_ids = sorted(
        {s.observation_id for s in sources}
        | {ref.removeprefix("observation:") for e in events for ref in e.evidence_refs}
    )
    truncated |= len(claim_ids) > RECORD_CAP or len(observation_ids) > RECORD_CAP * 2
    claims = (
        {
            c.claim_id: c
            for c in await session.scalars(
                select(ClaimModel).where(ClaimModel.claim_id.in_(claim_ids[:RECORD_CAP]))
            )
        }
        if claim_ids
        else {}
    )
    claim_evidence = await _evidence_for_targets(
        session, {("claim", claim_id) for claim_id in claims}
    )
    subjects = (
        set(
            await session.scalars(
                select(ObjectModel.object_id).where(
                    ObjectModel.object_id.in_({claim.subject_id for claim in claims.values()})
                )
            )
        )
        if claims
        else set()
    )
    observations = (
        {
            o.observation_id: o
            for o in await session.scalars(
                select(ObservationModel).where(
                    ObservationModel.observation_id.in_(observation_ids[: RECORD_CAP * 2])
                )
            )
        }
        if observation_ids
        else {}
    )
    revision_ids = {incident.created_revision}
    revision_ids.update(event.created_revision for event in events)
    revision_ids.update(source.created_revision for source in sources)
    times = dict(
        (
            await session.execute(
                select(IncidentRevisionModel.revision, IncidentRevisionModel.committed_at).where(
                    IncidentRevisionModel.revision.in_(revision_ids)
                )
            )
        ).all()
    )
    nodes = {
        incident_id: NetworkNodeView(
            object_id=incident_id,
            object_type="Incident",
            canonical_key=incident_id,
            label=incident.current_summary or incident.incident_type,
            created_revision=incident.created_revision,
            created_at=incident.created_at,
        )
    }
    edges: list[NetworkEdgeView] = []
    supersessions = {
        event.supersedes_event_id: event.created_revision
        for event in reversed(events)
        if event.supersedes_event_id
    }

    def add_edge(
        relation_id: str,
        source: str,
        target: str,
        relation_type: str,
        created: int,
        evidence: list[EvidenceRef] | None = None,
        superseded: int | None = None,
    ) -> None:
        edges.append(
            NetworkEdgeView(
                relation_id=relation_id,
                source_id=source,
                target_id=target,
                relation_type=relation_type,
                origin="incident_record",
                qualifier={"projection": "incident_association", "revision_domain": "incident"},
                created_revision=created,
                created_at=times[created],
                superseded_revision=superseded,
                superseded_at=times.get(superseded) if superseded is not None else None,
                evidence=evidence or [],
            )
        )

    def observation_node(observation_id: str, created: int) -> EvidenceRef | None:
        observation = observations.get(observation_id)
        if observation is None:
            return None
        node_id = f"observation:{observation_id}"
        if node_id not in nodes or nodes[node_id].created_revision > created:
            nodes[node_id] = NetworkNodeView(
                object_id=node_id,
                object_type="Evidence",
                canonical_key=observation_id,
                label=f"{observation.source_id} · {observation.external_object_id}",
                created_revision=created,
                created_at=times[created],
                evidence_ref=node_id,
                event_time=observation.published_at,
            )
        return EvidenceRef(
            evidence_ref=node_id,
            source_id=observation.source_id,
            observation_id=observation_id,
            external_object_id=observation.external_object_id,
            external_revision=observation.external_revision,
            published_at=observation.published_at,
            updated_at=observation.updated_at,
            observed_at=observation.observed_at,
            canonical_url=observation.canonical_url,
        )

    for source in sources:
        evidence = observation_node(source.observation_id, source.created_revision)
        if evidence:
            add_edge(
                f"incident-source:{source.source_link_id}",
                incident_id,
                f"observation:{source.observation_id}",
                "has_source_evidence",
                source.created_revision,
                [evidence],
            )
    for event in events:
        node_id = f"event:{event.event_id}"
        nodes[node_id] = NetworkNodeView(
            object_id=node_id,
            object_type="IncidentEvent",
            canonical_key=event.event_id,
            label=event.summary,
            created_revision=event.created_revision,
            created_at=times[event.created_revision],
            event_time=event.event_time,
        )
        superseded = supersessions.get(event.event_id)
        event_evidence = []
        for ref in sorted(set(event.evidence_refs)):
            observation_id = ref.removeprefix("observation:")
            evidence = observation_node(observation_id, event.created_revision)
            if evidence:
                event_evidence.append(evidence)
                add_edge(
                    f"incident-event-evidence:{event.event_id}:{observation_id}",
                    node_id,
                    f"observation:{observation_id}",
                    "references_evidence",
                    event.created_revision,
                    [evidence],
                    superseded,
                )
        add_edge(
            f"incident-event:{event.event_id}",
            incident_id,
            node_id,
            "has_event",
            event.created_revision,
            event_evidence,
            superseded,
        )
        for ref in sorted(set(event.claim_refs)):
            claim = claims.get(ref.removeprefix("claim:"))
            if claim is None:
                continue
            claim_node_id = f"claim:{claim.claim_id}"
            if (
                claim_node_id not in nodes
                or nodes[claim_node_id].created_revision > event.created_revision
            ):
                nodes[claim_node_id] = NetworkNodeView(
                    object_id=claim_node_id,
                    object_type="Claim",
                    canonical_key=claim.claim_id,
                    label=f"{claim.predicate}: {str(claim.value)[:240]}",
                    created_revision=event.created_revision,
                    created_at=times[event.created_revision],
                    canonical_object_id=claim.subject_id if claim.subject_id in subjects else None,
                )
            add_edge(
                f"incident-event-claim:{event.event_id}:{claim.claim_id}",
                node_id,
                claim_node_id,
                "references_claim",
                event.created_revision,
                evidence=claim_evidence.get(("claim", claim.claim_id), []),
                superseded=superseded,
            )
    if focus not in nodes:
        return None
    selected = ({incident_id, focus} | existing) & nodes.keys()
    if len(selected) > 200:
        raise ValueError("network anchors and existing nodes must fit within 200 nodes")
    rank: dict[str, tuple[int, int, str]] = {}
    for edge in edges:
        neighbor = (
            edge.target_id
            if edge.source_id == focus
            else (edge.source_id if edge.target_id == focus else None)
        )
        if neighbor is None or neighbor in selected:
            continue
        previous = rank.get(neighbor, (0, 0, neighbor))
        rank[neighbor] = (
            previous[0] + len(edge.evidence),
            max(previous[1], edge.created_revision),
            neighbor,
        )
    ranked = sorted(rank.values(), key=lambda item: (-item[0], -item[1], item[2]))
    if after:
        last = (-int(str(after["score"])), -int(str(after["newest"])), str(after["id"]))
        ranked = [item for item in ranked if (-item[0], -item[1], item[2]) > last]
    page_size = min(limit - len({incident_id, focus}), 200 - len(selected))
    page = ranked[:page_size]
    selected.update(item[2] for item in page)
    remaining = len(ranked) - len(page)
    next_cursor = (
        _encode_cursor(
            {
                "center": incident_id,
                "focus": focus,
                "snapshot": snapshot,
                "score": page[-1][0],
                "newest": page[-1][1],
                "id": page[-1][2],
            }
        )
        if remaining and page and len(selected) < 200
        else None
    )
    ordered = [incident_id, *sorted(selected - {incident_id})]
    return NetworkView(
        center_id=incident_id,
        revision_domain="incident",
        nodes=[nodes[node_id] for node_id in ordered],
        edges=[edge for edge in edges if edge.source_id in selected and edge.target_id in selected],
        snapshot_revision=snapshot,
        next_cursor=next_cursor,
        remaining_count=remaining,
        history_scope=(
            "Incident association arrivals use incident revisions, not knowledge revisions. "
            "Actual source links and timeline claim/observation references only; no canonical "
            "relations inferred. Current summaries and referenced claim/evidence metadata are "
            "not historical snapshots. Read scope: newest 200 timeline and 200 source records, "
            "200 referenced claims and 400 observations. "
            + (
                "Scope truncated; older records may be absent."
                if truncated
                else "Scope not truncated."
            )
        ),
    )
