"""persist observation request metadata for replay

Revision ID: 20260927_0011
Revises: 20260926_0010
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0011"
down_revision: str | None = "20260926_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("request_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "observations",
        sa.Column(
            "request_metadata_captured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("observations", "request_metadata_captured")
    op.drop_column("observations", "request_metadata")
