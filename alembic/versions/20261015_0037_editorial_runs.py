"""Durable automatic editorial scheduling and fenced worker claims."""

import sqlalchemy as sa

from alembic import op

revision = "20261015_0037"
down_revision = "20261015_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "editorial_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("slot_at", sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("brief_id", sa.String(64)),
        sa.Column("last_error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_editorial_runs_status", "editorial_runs", ["status"])


def downgrade():
    op.drop_table("editorial_runs")
