"""incident intelligence durable state

Revision ID: 20260925_0004
Revises: 20260925_0003
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0004"
down_revision: str | None = "20260925_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incident_revisions",
        sa.Column("revision", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "cause_observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="SET NULL"),
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_incident_revisions_cause_observation_id",
        "incident_revisions",
        ["cause_observation_id"],
    )

    op.create_table(
        "incidents",
        sa.Column("incident_id", sa.String(length=36), primary_key=True),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("incident_type", sa.String(length=128), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("promotion_reason", sa.String(length=64), nullable=False),
        sa.Column("current_summary", sa.Text()),
        sa.Column("watch_state", sa.JSON(), nullable=False),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("incident_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_revision",
            sa.Integer(),
            sa.ForeignKey("incident_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("candidate_id", name="uq_incidents_candidate_id"),
    )
    op.create_index("ix_incidents_candidate_id", "incidents", ["candidate_id"])
    op.create_index("ix_incidents_incident_type", "incidents", ["incident_type"])
    op.create_index("ix_incidents_lifecycle", "incidents", ["lifecycle"])

    op.create_table(
        "incident_timeline_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(length=36),
            sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_role", sa.String(length=32), nullable=False),
        sa.Column("claim_refs", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column(
            "supersedes_event_id",
            sa.String(length=36),
            sa.ForeignKey("incident_timeline_events.event_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("incident_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "incident_id",
            "signal_id",
            name="uq_incident_timeline_signal",
        ),
    )
    for name, column in [
        ("ix_incident_timeline_events_incident_id", "incident_id"),
        ("ix_incident_timeline_events_signal_id", "signal_id"),
        ("ix_incident_timeline_events_event_time", "event_time"),
        ("ix_incident_timeline_events_event_type", "event_type"),
        ("ix_incident_timeline_events_source_role", "source_role"),
    ]:
        op.create_index(name, "incident_timeline_events", [column])

    op.create_table(
        "incident_source_links",
        sa.Column("source_link_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "incident_id",
            sa.String(length=36),
            sa.ForeignKey("incidents.incident_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            sa.String(length=36),
            sa.ForeignKey("observations.observation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_family", sa.String(length=128), nullable=False),
        sa.Column("upstream_source", sa.String(length=256)),
        sa.Column("independence_key", sa.String(length=256), nullable=False),
        sa.Column("source_role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_revision",
            sa.Integer(),
            sa.ForeignKey("incident_revisions.revision", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "incident_id",
            "observation_id",
            name="uq_incident_source_observation",
        ),
    )
    for name, column in [
        ("ix_incident_source_links_incident_id", "incident_id"),
        ("ix_incident_source_links_observation_id", "observation_id"),
        ("ix_incident_source_links_source_id", "source_id"),
        ("ix_incident_source_links_independence_key", "independence_key"),
        ("ix_incident_source_links_source_role", "source_role"),
    ]:
        op.create_index(name, "incident_source_links", [column])


def downgrade() -> None:
    op.drop_table("incident_source_links")
    op.drop_table("incident_timeline_events")
    op.drop_table("incidents")
    op.drop_table("incident_revisions")
