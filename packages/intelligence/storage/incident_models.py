from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class IncidentRevisionModel(Base):
    __tablename__ = "incident_revisions"

    revision: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cause_observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("observations.observation_id", ondelete="SET NULL"), index=True
    )
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SecurityIncidentModel(Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("candidate_id", name="uq_incidents_candidate_id"),)

    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    promotion_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    current_summary: Mapped[str | None] = mapped_column(Text)
    watch_state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("incident_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
    current_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("incident_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncidentTimelineEventModel(Base):
    __tablename__ = "incident_timeline_events"
    __table_args__ = (
        UniqueConstraint("incident_id", "signal_id", name="uq_incident_timeline_signal"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    claim_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("incident_timeline_events.event_id", ondelete="SET NULL")
    )
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("incident_revisions.revision", ondelete="RESTRICT"), nullable=False
    )


class IncidentSourceLinkModel(Base):
    __tablename__ = "incident_source_links"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "observation_id",
            name="uq_incident_source_observation",
        ),
    )

    source_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("observations.observation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_family: Mapped[str] = mapped_column(String(128), nullable=False)
    upstream_source: Mapped[str | None] = mapped_column(String(256))
    independence_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    source_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_revision: Mapped[int] = mapped_column(
        Integer, ForeignKey("incident_revisions.revision", ondelete="RESTRICT"), nullable=False
    )
