"""add metric definition revision

Revision ID: 20260927_0024
Revises: 20260927_0023
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0024"
down_revision: str | None = "20260927_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "metric_observations",
        sa.Column("metric_definition_revision", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE metric_observations SET metric_definition_revision = '1' "
        "WHERE metric_definition_revision IS NULL"
    )
    op.alter_column(
        "metric_observations",
        "metric_definition_revision",
        nullable=False,
    )
    op.create_index(
        "ix_metric_observations_metric_definition_revision",
        "metric_observations",
        ["metric_definition_revision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metric_observations_metric_definition_revision",
        table_name="metric_observations",
    )
    op.drop_column("metric_observations", "metric_definition_revision")
