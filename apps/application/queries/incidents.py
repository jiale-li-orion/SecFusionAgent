from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.incidents import (
    IncidentDetailView,
    IncidentListView,
    IncidentSourceLinkView,
    IncidentSummaryView,
    IncidentTimelineEventView,
)
from packages.intelligence.storage.incident_models import (
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)


async def list_product_incidents(
    session: AsyncSession,
    *,
    limit: int = 40,
) -> IncidentListView:
    incidents = list(
        await session.scalars(
            select(SecurityIncidentModel)
            .order_by(SecurityIncidentModel.updated_at.desc())
            .limit(limit)
        )
    )
    if not incidents:
        return IncidentListView()
    ids = [item.incident_id for item in incidents]
    timeline_counts = {
        incident_id: int(count)
        for incident_id, count in (
            await session.execute(
                select(
                    IncidentTimelineEventModel.incident_id,
                    func.count(),
                )
                .where(IncidentTimelineEventModel.incident_id.in_(ids))
                .group_by(IncidentTimelineEventModel.incident_id)
            )
        ).all()
    }
    source_rows = (
        await session.execute(
            select(
                IncidentSourceLinkModel.incident_id,
                func.count(),
                func.count(distinct(IncidentSourceLinkModel.independence_key)),
            )
            .where(IncidentSourceLinkModel.incident_id.in_(ids))
            .group_by(IncidentSourceLinkModel.incident_id)
        )
    ).all()
    source_counts = {
        incident_id: (int(count), int(diversity))
        for incident_id, count, diversity in source_rows
    }
    return IncidentListView(
        items=[
            _summary(
                item,
                timeline_event_count=timeline_counts.get(item.incident_id, 0),
                source_link_count=source_counts.get(item.incident_id, (0, 0))[0],
                source_diversity_count=source_counts.get(item.incident_id, (0, 0))[1],
            )
            for item in incidents
        ]
    )


async def get_product_incident(
    session: AsyncSession,
    incident_id: str,
) -> IncidentDetailView | None:
    incident = await session.get(SecurityIncidentModel, incident_id)
    if incident is None:
        return None
    timeline = list(
        await session.scalars(
            select(IncidentTimelineEventModel)
            .where(IncidentTimelineEventModel.incident_id == incident_id)
            .order_by(
                IncidentTimelineEventModel.event_time,
                IncidentTimelineEventModel.event_id,
            )
        )
    )
    sources = list(
        await session.scalars(
            select(IncidentSourceLinkModel)
            .where(IncidentSourceLinkModel.incident_id == incident_id)
            .order_by(
                IncidentSourceLinkModel.created_revision,
                IncidentSourceLinkModel.source_id,
            )
        )
    )
    return IncidentDetailView(
        incident=_summary(
            incident,
            timeline_event_count=len(timeline),
            source_link_count=len(sources),
            source_diversity_count=len({item.independence_key for item in sources}),
        ),
        timeline=[
            IncidentTimelineEventView(
                event_id=item.event_id,
                signal_id=item.signal_id,
                event_time=item.event_time,
                observed_at=item.observed_at,
                event_type=item.event_type,
                summary=item.summary,
                source_role=item.source_role,
                claim_refs=list(item.claim_refs),
                evidence_refs=list(item.evidence_refs),
                supersedes_event_id=item.supersedes_event_id,
                created_revision=item.created_revision,
            )
            for item in timeline
        ],
        sources=[
            IncidentSourceLinkView(
                source_link_id=item.source_link_id,
                observation_id=item.observation_id,
                source_id=item.source_id,
                source_family=item.source_family,
                upstream_source=item.upstream_source,
                independence_key=item.independence_key,
                source_role=item.source_role,
                created_revision=item.created_revision,
            )
            for item in sources
        ],
    )


def _summary(
    incident: SecurityIncidentModel,
    *,
    timeline_event_count: int,
    source_link_count: int,
    source_diversity_count: int,
) -> IncidentSummaryView:
    return IncidentSummaryView(
        incident_id=incident.incident_id,
        candidate_id=incident.candidate_id,
        incident_type=incident.incident_type,
        lifecycle=incident.lifecycle,
        promotion_reason=incident.promotion_reason,
        current_summary=incident.current_summary,
        watch_state=dict(incident.watch_state),
        current_revision=incident.current_revision,
        timeline_event_count=timeline_event_count,
        source_link_count=source_link_count,
        source_diversity_count=source_diversity_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
