"""current materialized projections

Revision ID: 20260925_0005
Revises: 20260925_0004
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0005"
down_revision: str | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "current_projections",
        sa.Column("projection_id", sa.String(length=36), primary_key=True),
        sa.Column("projection_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("projection_key", sa.String(length=512), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("upstream_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "projection_type",
            "subject_id",
            name="uq_current_projection_type_subject",
        ),
    )
    op.create_index(
        "ix_current_projections_projection_type",
        "current_projections",
        ["projection_type"],
    )
    op.create_index(
        "ix_current_projections_subject_id",
        "current_projections",
        ["subject_id"],
    )
    op.create_index(
        "ix_current_projections_projection_key",
        "current_projections",
        ["projection_key"],
    )
    op.create_index(
        "ix_current_projections_upstream_revision",
        "current_projections",
        ["upstream_revision"],
    )


def downgrade() -> None:
    op.drop_table("current_projections")
