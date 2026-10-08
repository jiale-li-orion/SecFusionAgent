"""Persist Product command replay identity.

Revision ID: 20261009_0032
Revises: 20261008_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_0032"
down_revision: str | None = "20261008_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_command_records",
        sa.Column("principal_scope", sa.String(256), primary_key=True),
        sa.Column("operation", sa.String(128), primary_key=True),
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("response_ref", sa.String(256)),
        sa.Column("response_payload", sa.JSON()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("product_command_records")
