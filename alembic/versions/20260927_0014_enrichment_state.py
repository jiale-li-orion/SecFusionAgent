"""add materialized enrichment state and attempt ledger

Revision ID: 20260927_0014
Revises: 20260927_0013
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0014"
down_revision: str | None = "20260927_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_dimension_states",
        sa.Column("state_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "target_object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vocabulary_revision", sa.String(length=64), nullable=False),
        sa.Column("requirement_id", sa.String(length=256), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("accepted_fact_refs", sa.JSON(), nullable=False),
        sa.Column("conflict_refs", sa.JSON(), nullable=False),
        sa.Column("missing_prerequisites", sa.JSON(), nullable=False),
        sa.Column("attempted_operator_refs", sa.JSON(), nullable=False),
        sa.Column("blocked_attempt_refs", sa.JSON(), nullable=False),
        sa.Column("world_revision", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "target_object_id",
            "vocabulary_revision",
            "dimension",
            name="uq_enrichment_dimension_state",
        ),
    )
    for column in (
        "target_object_id",
        "vocabulary_revision",
        "dimension",
        "status",
        "world_revision",
    ):
        op.create_index(
            f"ix_enrichment_dimension_states_{column}",
            "enrichment_dimension_states",
            [column],
        )

    op.create_table(
        "enrichment_attempts",
        sa.Column("attempt_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "target_object_id",
            sa.String(length=36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_id", sa.String(length=256), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("operator_id", sa.String(length=128), nullable=False),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("semantic_outcome", sa.String(length=32)),
        sa.Column("blocked_reason", sa.String(length=128)),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("output_refs", sa.JSON(), nullable=False),
        sa.Column("world_revision_before", sa.Integer(), nullable=False),
        sa.Column("world_revision_after", sa.Integer()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in (
        "target_object_id",
        "requirement_id",
        "dimension",
        "operator_id",
        "task_run_id",
        "execution_status",
        "semantic_outcome",
        "blocked_reason",
    ):
        op.create_index(
            f"ix_enrichment_attempts_{column}",
            "enrichment_attempts",
            [column],
        )


def downgrade() -> None:
    op.drop_table("enrichment_attempts")
    op.drop_table("enrichment_dimension_states")
