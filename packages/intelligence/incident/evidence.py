from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.document_models import (
    DocumentRevisionModel,
    InsightCandidateModel,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.shared.storage.models import OutboxEventModel
from packages.sources.storage.models import SourceModel


class IncidentEvidenceAttachmentResult(BaseModel):
    incident_id: str
    incident_revision: int
    source_link_id: str
    timeline_event_id: str
    observation_id: str
    replay: bool = False


class IncidentEvidenceAttachmentService:
    """Attach an explicitly resolved managed-document observation to a durable incident."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def attach_document(
        self,
        session: AsyncSession,
        *,
        incident_id: str,
        document_revision_id: str,
        event_type: str,
        summary: str,
        event_time: datetime | None = None,
    ) -> IncidentEvidenceAttachmentResult:
        if not event_type.strip():
            raise ValueError("incident evidence event_type cannot be empty")
        if not summary.strip():
            raise ValueError("incident evidence summary cannot be empty")

        incident = await session.get(SecurityIncidentModel, incident_id)
        if incident is None:
            raise LookupError(f"incident not found: {incident_id}")
        revision = await session.get(DocumentRevisionModel, document_revision_id)
        if revision is None:
            raise LookupError(f"document revision not found: {document_revision_id}")
        observation = await session.get(ObservationModel, revision.observation_id)
        if observation is None:
            raise RuntimeError("document revision exists without observation")
        source = await session.get(SourceModel, observation.source_id)
        if source is None:
            raise RuntimeError("document observation references missing source")

        existing_link = await session.scalar(
            select(IncidentSourceLinkModel).where(
                IncidentSourceLinkModel.incident_id == incident_id,
                IncidentSourceLinkModel.observation_id == observation.observation_id,
            )
        )
        signal_id = f"document:{document_revision_id}"
        existing_event = await session.scalar(
            select(IncidentTimelineEventModel).where(
                IncidentTimelineEventModel.incident_id == incident_id,
                IncidentTimelineEventModel.signal_id == signal_id,
            )
        )
        if existing_link is not None and existing_event is not None:
            return IncidentEvidenceAttachmentResult(
                incident_id=incident_id,
                incident_revision=incident.current_revision,
                source_link_id=existing_link.source_link_id,
                timeline_event_id=existing_event.event_id,
                observation_id=observation.observation_id,
                replay=True,
            )
        if existing_link is not None or existing_event is not None:
            raise RuntimeError("incident document attachment is partially persisted")

        now = self._now()
        incident_revision = IncidentRevisionModel(
            cause_observation_id=observation.observation_id,
            committed_at=now,
        )
        session.add(incident_revision)
        await session.flush()

        insight = await session.scalar(
            select(InsightCandidateModel).where(
                InsightCandidateModel.document_revision_id == document_revision_id
            )
        )
        claim_refs = sorted(set(insight.related_claim_ids)) if insight is not None else []

        source_link_id = _stable_id(f"incident-source:{incident_id}:{observation.observation_id}")
        timeline_event_id = _stable_id(
            f"incident-document-event:{incident_id}:{document_revision_id}"
        )
        session.add(
            IncidentSourceLinkModel(
                source_link_id=source_link_id,
                incident_id=incident_id,
                observation_id=observation.observation_id,
                source_id=source.source_id,
                source_family=source.source_family,
                upstream_source=source.upstream_source,
                independence_key=source.upstream_source or source.source_family,
                source_role=source.source_role,
                created_revision=incident_revision.revision,
            )
        )
        session.add(
            IncidentTimelineEventModel(
                event_id=timeline_event_id,
                incident_id=incident_id,
                signal_id=signal_id,
                event_time=event_time
                or revision.published_at
                or revision.updated_at
                or observation.observed_at,
                observed_at=observation.observed_at,
                event_type=event_type.strip(),
                summary=summary.strip(),
                source_role=source.source_role,
                claim_refs=claim_refs,
                evidence_refs=[observation.observation_id],
                supersedes_event_id=None,
                created_revision=incident_revision.revision,
            )
        )

        incident.current_revision = incident_revision.revision
        incident.updated_at = now
        session.add(
            OutboxEventModel(
                event_id=_stable_id(
                    f"outbox:incident.changed:{incident_id}:{incident_revision.revision}"
                ),
                topic="incident.changed",
                aggregate_id=incident_id,
                payload={
                    "incident_id": incident_id,
                    "revision": incident_revision.revision,
                },
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        await session.flush()
        return IncidentEvidenceAttachmentResult(
            incident_id=incident_id,
            incident_revision=incident_revision.revision,
            source_link_id=source_link_id,
            timeline_event_id=timeline_event_id,
            observation_id=observation.observation_id,
        )


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
