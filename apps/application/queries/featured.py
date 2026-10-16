"""Evidence-backed editorial focus across incidents, tools and research."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.world import WorldStoryEvidenceView, WorldStoryView
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.incident_models import (
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.sources.inventory import load_source_inventory
from packages.sources.storage.models import SourceModel


async def curated_world_stories(session: AsyncSession, *, limit: int) -> list[WorldStoryView]:
    incidents = list(
        await session.scalars(
            select(SecurityIncidentModel)
            .where(SecurityIncidentModel.watch_state["historical_backfill"].as_boolean().is_(True))
            .order_by(
                SecurityIncidentModel.watch_state["featured_priority"].as_integer().desc(),
                SecurityIncidentModel.updated_at.desc(),
                SecurityIncidentModel.incident_id,
            )
            .limit(limit)
        )
    )
    if not incidents:
        return []
    ids = [i.incident_id for i in incidents]
    links = (
        await session.execute(
            select(IncidentSourceLinkModel, ObservationModel, SourceModel)
            .join(
                ObservationModel,
                ObservationModel.observation_id == IncidentSourceLinkModel.observation_id,
            )
            .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
            .where(IncidentSourceLinkModel.incident_id.in_(ids))
        )
    ).all()
    artifacts = list(
        await session.scalars(
            select(EvidenceArtifactModel).where(
                EvidenceArtifactModel.observation_id.in_([o.observation_id for _, o, _ in links])
            )
        )
    )
    public = {
        a.observation_id for a in artifacts if a.access_rights.get("classification") == "public"
    }
    public -= {
        a.observation_id for a in artifacts if a.access_rights.get("classification") != "public"
    }
    timelines = list(
        await session.scalars(
            select(IncidentTimelineEventModel)
            .where(IncidentTimelineEventModel.incident_id.in_(ids))
            .order_by(IncidentTimelineEventModel.event_time)
        )
    )
    names = {
        sid: entry.name for entry in load_source_inventory().entries for sid in entry.source_ids
    }
    stories = []
    for incident in incidents:
        source_rows = [(o, s) for link, o, s in links if link.incident_id == incident.incident_id]
        if not source_rows or any(
            o.observation_id not in public or s.access_rights.get("classification") != "public"
            for o, s in source_rows
        ):
            continue
        events = [e for e in timelines if e.incident_id == incident.incident_id]
        if not events:
            continue
        observation, source = source_rows[0]
        state = incident.watch_state
        kind = str(state.get("display_kind") or "Incident")
        stories.append(
            WorldStoryView(
                story_id=f"incident:{incident.incident_id}",
                category="development" if kind == "Tool" else "incidents",
                kind=kind,
                headline=str(state.get("title") or incident.current_summary),
                excerpt=incident.current_summary,
                excerpt_origin="analyst_summary",
                happened_at=events[0].event_time,
                observed_at=incident.created_at,
                published_at=observation.published_at,
                time_basis="observed",
                source_id=source.source_id,
                source_name=names.get(source.source_id, source.source_family),
                incident_id=incident.incident_id,
                external_ref=observation.canonical_url,
                facts={
                    "featured_priority": state.get("featured_priority", 0),
                    "editorial_angle": state.get("editorial_angle"),
                    "historical_backfill": True,
                    "incident_type": incident.incident_type,
                },
                evidence=WorldStoryEvidenceView(
                    observation_id=observation.observation_id,
                    locator={"kind": "curated_incident", "revision": incident.current_revision},
                ),
            )
        )
    return stories
