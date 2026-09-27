"""add evaluation provenance records

Revision ID: 20260927_0025
Revises: 20260927_0024
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0025"
down_revision: str | None = "20260927_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("metric_definition_ref", sa.String(length=320), primary_key=True),
        sa.Column("metric_name", sa.String(length=256), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("denominator", sa.Text(), nullable=False),
        sa.Column("aggregation", sa.String(length=32), nullable=False),
        sa.Column("missing_value_policy", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=64)),
        sa.Column("definition_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("metric_name", "revision", "created_at"):
        op.create_index(f"ix_metric_definitions_{column}", "metric_definitions", [column])

    op.create_table(
        "competition_reports",
        sa.Column("report_id", sa.String(length=36), primary_key=True),
        sa.Column("report_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "deployment_revision_id",
            sa.String(length=128),
            sa.ForeignKey("deployment_revisions.deployment_revision_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("benchmark_run_ids_json", sa.JSON(), nullable=False),
        sa.Column("metric_definition_refs_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("artifact_refs_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("report_digest", "deployment_revision_id", "generated_at"):
        op.create_index(f"ix_competition_reports_{column}", "competition_reports", [column])


def downgrade() -> None:
    op.drop_table("competition_reports")
    op.drop_table("metric_definitions")
