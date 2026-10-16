"""Analyst-curated historical incidents backed by retained document revisions."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.document_models import DocumentChunkModel, DocumentRevisionModel
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.incident_models import (
    IncidentRevisionModel,
    IncidentSourceLinkModel,
    IncidentTimelineEventModel,
    SecurityIncidentModel,
)
from packages.shared.storage.models import OutboxEventModel
from packages.sources.storage.models import SourceModel


class CuratedTimelineNode(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    document_revision_id: str
    summary: str = Field(min_length=10, max_length=2000)
    # Exact retained passage is a locator for analyst verification, never model authority.
    supporting_excerpt: str = Field(min_length=20, max_length=2000)
    event_time: AwareDatetime
    time_basis: Literal["reported_date", "published", "observed"]
    event_type: str = Field(default="reported", min_length=1, max_length=64)


class CuratedIncident(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,100}$")
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=10, max_length=2000)
    incident_type: str = Field(default="ai-security-incident", max_length=128)
    display_kind: Literal["Incident", "Tool", "Research"] = "Incident"
    featured_priority: int = Field(default=0, ge=0, le=100)
    editorial_angle: str | None = Field(default=None, max_length=600)
    timeline: list[CuratedTimelineNode] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_nodes(self) -> CuratedIncident:
        if len({node.key for node in self.timeline}) != len(self.timeline):
            raise ValueError("timeline keys must be unique")
        return self


def _id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:curated:{value}"))


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


class IncidentCurationService:
    """Explicit analyst pin, not retroactive monitoring or automated confirmation.

    Caller owns transaction. A key identifies an immutable reviewed edition; replay
    with different content is rejected instead of silently rewriting history.
    """

    async def import_incident(
        self, session: AsyncSession, spec: CuratedIncident
    ) -> tuple[str, bool]:
        fingerprint = sha256(spec.model_dump_json().encode()).hexdigest()
        incident_id = _id(spec.key)
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            lock = int.from_bytes(sha256(incident_id.encode()).digest()[:8], "big", signed=True)
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        existing = await session.get(SecurityIncidentModel, incident_id)
        if existing is not None:
            if existing.watch_state.get("curation_fingerprint") != fingerprint:
                raise ValueError("curation key already exists with different reviewed content")
            return incident_id, True

        evidence = {}
        for node in spec.timeline:
            revision = await session.get(DocumentRevisionModel, node.document_revision_id)
            if revision is None:
                raise ValueError("curation requires a retained document revision")
            observation = await session.get(ObservationModel, revision.observation_id)
            if observation is None:
                raise ValueError("document revision has no retained observation")
            source = await session.get(SourceModel, observation.source_id)
            artifacts = list(
                await session.scalars(
                    select(EvidenceArtifactModel).where(
                        EvidenceArtifactModel.observation_id == revision.observation_id
                    )
                )
            )
            if (
                source is None
                or source.access_rights.get("classification") != "public"
                or not artifacts
                or any(a.access_rights.get("classification") != "public" for a in artifacts)
            ):
                raise ValueError("curation requires public source and retained public artifacts")
            quality = revision.metadata_json.get("content_quality", {})
            if isinstance(quality, dict) and quality.get("usable") is False:
                raise ValueError("rejected material cannot support an incident")
            chunks = list(
                await session.scalars(
                    select(DocumentChunkModel.text).where(
                        DocumentChunkModel.document_revision_id == node.document_revision_id
                    )
                )
            )
            if not any(
                _normalized(node.supporting_excerpt) in _normalized(chunk) for chunk in chunks
            ):
                raise ValueError("supporting excerpt is not present in retained document chunks")
            expected_time = (
                observation.observed_at
                if node.time_basis == "observed"
                else revision.published_at
                if node.time_basis == "published"
                else None
            )
            if node.time_basis in {"observed", "published"}:
                if expected_time is None or node.event_time != expected_time.replace(
                    tzinfo=expected_time.tzinfo or UTC
                ):
                    raise ValueError("timeline time basis must match retained timestamp")
            if node.event_time > datetime.now(UTC):
                raise ValueError("historical incident date cannot be in the future")
            evidence[node.key] = (revision, observation, source)

        now = datetime.now(UTC)
        revision_row = IncidentRevisionModel(
            cause_observation_id=evidence[spec.timeline[0].key][1].observation_id,
            committed_at=now,
        )
        session.add(revision_row)
        await session.flush()
        state = {
            "title": spec.title,
            "display_kind": spec.display_kind,
            "timeline_start": min(n.event_time for n in spec.timeline).isoformat(),
            "featured_priority": spec.featured_priority,
            "editorial_angle": spec.editorial_angle,
            "historical_backfill": True,
            "curation_fingerprint": fingerprint,
            "timeline_time_basis": {
                _id(f"{spec.key}:{n.key}"): n.time_basis for n in spec.timeline
            },
            "timeline_evidence": {
                _id(f"{spec.key}:{n.key}"): {
                    "document_revision_id": n.document_revision_id,
                    "supporting_excerpt": n.supporting_excerpt,
                }
                for n in spec.timeline
            },
        }
        session.add(
            SecurityIncidentModel(
                incident_id=incident_id,
                candidate_id=_id(f"candidate:{spec.key}"),
                incident_type=spec.incident_type,
                lifecycle="tracked",
                promotion_reason="analyst_pin",
                current_summary=spec.summary,
                watch_state=state,
                created_revision=revision_row.revision,
                current_revision=revision_row.revision,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        linked = set()
        for node in spec.timeline:
            _, observation, source = evidence[node.key]
            if observation.observation_id not in linked:
                session.add(
                    IncidentSourceLinkModel(
                        source_link_id=_id(f"{spec.key}:source:{observation.observation_id}"),
                        incident_id=incident_id,
                        observation_id=observation.observation_id,
                        source_id=source.source_id,
                        source_family=source.source_family,
                        upstream_source=source.upstream_source,
                        independence_key=source.upstream_source or source.source_family,
                        source_role=source.source_role,
                        created_revision=revision_row.revision,
                    )
                )
                linked.add(observation.observation_id)
            session.add(
                IncidentTimelineEventModel(
                    event_id=_id(f"{spec.key}:{node.key}"),
                    incident_id=incident_id,
                    signal_id=f"curated:{_id(f'{spec.key}:{node.key}')}",
                    event_time=node.event_time,
                    observed_at=observation.observed_at,
                    event_type=node.event_type,
                    summary=node.summary,
                    source_role=source.source_role,
                    claim_refs=[],
                    evidence_refs=[observation.observation_id],
                    created_revision=revision_row.revision,
                )
            )
        session.add(
            OutboxEventModel(
                event_id=_id(f"{spec.key}:changed"),
                topic="incident.changed",
                aggregate_id=incident_id,
                payload={"incident_id": incident_id, "revision": revision_row.revision},
                status="pending",
                attempts=0,
                available_at=now,
            )
        )
        await session.flush()
        return incident_id, False
