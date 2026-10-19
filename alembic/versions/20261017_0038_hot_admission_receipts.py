"""Retain lightweight metadata for completed hot-cache admissions."""

import sqlalchemy as sa

from alembic import op

revision = "20261017_0038"
down_revision = "20261015_0037"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hot_admission_receipts",
        sa.Column("receipt_id", sa.String(64), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(128),
            sa.ForeignKey("sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_object_id", sa.Text(), nullable=False),
        sa.Column("external_revision", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "acquisition_run_id",
            sa.String(36),
            sa.ForeignKey("acquisition_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("source_definition_hash", sa.String(64), nullable=False),
        sa.Column("input_backfill_pending", sa.Boolean(), nullable=False),
        sa.Column("output_backfill_pending", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_hot_admission_source_publication",
        "hot_admission_receipts",
        ["source_id", "published_at", "available_at"],
    )
    op.create_index(
        "ix_hot_admission_source_update",
        "hot_admission_receipts",
        ["source_id", "updated_at", "available_at"],
    )
    op.create_index(
        "ix_hot_admission_receipts_acquisition_run_id",
        "hot_admission_receipts",
        ["acquisition_run_id"],
    )


def downgrade():
    op.drop_table("hot_admission_receipts")
