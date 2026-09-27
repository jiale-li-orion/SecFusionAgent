"""add M4 investigation state runtime

Revision ID: 20260927_0015
Revises: 20260927_0014
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0015"
down_revision: str | None = "20260927_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "investigation_cases",
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE investigation_cases SET status = 'active' WHERE status IN ('open', 'running')"
    )
    op.alter_column("investigation_cases", "current_revision", server_default=None)

    op.create_table(
        "case_state_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("base_case_revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("patch_id", sa.String(length=128)),
        sa.Column("operation_index", sa.Integer()),
        sa.Column("proposition", sa.Text()),
        sa.Column("target_ref", sa.String(length=512)),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("writer", sa.String(length=256), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "case_revision", name="uq_case_state_revision"),
        sa.UniqueConstraint(
            "case_id",
            "patch_id",
            "operation_index",
            name="uq_case_state_patch_operation",
        ),
    )
    for column in (
        "case_id",
        "event_type",
        "patch_id",
        "target_ref",
        "writer",
        "reason_code",
        "created_at",
    ):
        op.create_index(f"ix_case_state_events_{column}", "case_state_events", [column])

    op.create_table(
        "evidence_needs",
        sa.Column("need_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("derived_from_enrichment_requirement", sa.String(length=256)),
        sa.Column("proposition_or_question", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(length=256), nullable=False),
        sa.Column("target_objects", sa.JSON(), nullable=False),
        sa.Column("evidence_contract", sa.JSON(), nullable=False),
        sa.Column("preferred_source_roles", sa.JSON(), nullable=False),
        sa.Column("rejected_evidence_patterns", sa.JSON(), nullable=False),
        sa.Column("freshness_requirement", sa.JSON(), nullable=False),
        sa.Column("completion_predicate", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolution_evidence_refs", sa.JSON(), nullable=False),
        sa.Column("opened_revision", sa.Integer(), nullable=False),
        sa.Column("updated_revision", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "case_id",
        "derived_from_enrichment_requirement",
        "priority",
        "status",
    ):
        op.create_index(f"ix_evidence_needs_{column}", "evidence_needs", [column])

    op.create_table(
        "investigation_state_current",
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("confirmed", sa.JSON(), nullable=False),
        sa.Column("tentative", sa.JSON(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("hypotheses", sa.JSON(), nullable=False),
        sa.Column("open_questions", sa.JSON(), nullable=False),
        sa.Column("decision_variables", sa.JSON(), nullable=False),
        sa.Column("evidence_need_ids", sa.JSON(), nullable=False),
        sa.Column("active_skills", sa.JSON(), nullable=False),
        sa.Column("normative_context_refs", sa.JSON(), nullable=False),
        sa.Column("unresolved_applicability", sa.JSON(), nullable=False),
        sa.Column("current_decision", sa.JSON()),
        sa.Column("last_world_revision", sa.Integer()),
        sa.Column("last_perception_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_investigation_state_current_case_revision",
        "investigation_state_current",
        ["case_revision"],
    )
    op.create_index(
        "ix_investigation_state_current_last_world_revision",
        "investigation_state_current",
        ["last_world_revision"],
    )


def downgrade() -> None:
    op.drop_table("investigation_state_current")
    op.drop_table("evidence_needs")
    op.drop_table("case_state_events")
    op.drop_column("investigation_cases", "current_revision")
