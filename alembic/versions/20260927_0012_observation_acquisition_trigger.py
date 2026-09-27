"""persist acquisition trigger on observations for self-contained replay

Revision ID: 20260927_0012
Revises: 20260927_0011
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0012"
down_revision: str | None = "20260927_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column(
            "acquisition_trigger",
            sa.String(length=32),
            nullable=False,
            server_default="replay",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE observations AS o "
            "SET acquisition_trigger = a.trigger "
            "FROM acquisition_runs AS a "
            "WHERE o.acquisition_run_id = a.run_id"
        )
    )
    op.alter_column("observations", "acquisition_trigger", server_default=None)


def downgrade() -> None:
    op.drop_column("observations", "acquisition_trigger")
