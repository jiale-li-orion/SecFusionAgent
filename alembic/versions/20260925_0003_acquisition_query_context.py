"""add on-demand acquisition query context

Revision ID: 20260925_0003
Revises: 20260925_0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0003"
down_revision: str | None = "20260925_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("acquisition_runs", sa.Column("parent_run_id", sa.String(length=36)))
    op.add_column(
        "acquisition_runs",
        sa.Column("query_spec", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(
        "ix_acquisition_runs_parent_run_id",
        "acquisition_runs",
        ["parent_run_id"],
    )
    op.alter_column("acquisition_runs", "query_spec", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_acquisition_runs_parent_run_id", table_name="acquisition_runs")
    op.drop_column("acquisition_runs", "query_spec")
    op.drop_column("acquisition_runs", "parent_run_id")
