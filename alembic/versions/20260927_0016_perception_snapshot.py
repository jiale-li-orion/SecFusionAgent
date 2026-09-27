"""add durable perception events and investigation snapshots

Revision ID: 20260927_0016
Revises: 20260927_0015
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0016"
down_revision: str | None = "20260927_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "perception_events",
        sa.Column("perception_event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column(
            "need_id",
            sa.String(length=36),
            sa.ForeignKey("evidence_needs.need_id", ondelete="SET NULL"),
        ),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("percept_ref", sa.String(length=256), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("observation_refs", sa.JSON(), nullable=False),
        sa.Column("cost", sa.JSON(), nullable=False),
        sa.Column("world_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_run_id", "request_id", name="uq_perception_event_task_request"),
    )
    for column in (
        "case_id",
        "task_run_id",
        "request_id",
        "need_id",
        "world_revision",
        "status",
        "failure_class",
    ):
        op.create_index(f"ix_perception_events_{column}", "perception_events", [column])

    op.create_table(
        "investigation_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("knowledge_revision", sa.Integer()),
        sa.Column("incident_revision", sa.String(length=128)),
        sa.Column("document_index_revision", sa.String(length=128)),
        sa.Column("experience_revision", sa.String(length=128)),
        sa.Column("policy_revision", sa.String(length=128), nullable=False),
        sa.Column("capability_registry_revision", sa.String(length=128)),
        sa.Column("routing_query_planner_revision", sa.String(length=128)),
        sa.Column("model_revision", sa.String(length=128)),
        sa.Column("prompt_assembly_revision", sa.String(length=128)),
        sa.Column("source_availability_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_investigation_snapshots_case_id", "investigation_snapshots", ["case_id"])
    op.create_index(
        "ix_investigation_snapshots_case_revision",
        "investigation_snapshots",
        ["case_revision"],
    )
    op.create_index(
        "ix_investigation_snapshots_knowledge_revision",
        "investigation_snapshots",
        ["knowledge_revision"],
    )


def downgrade() -> None:
    op.drop_table("investigation_snapshots")
    op.drop_table("perception_events")
