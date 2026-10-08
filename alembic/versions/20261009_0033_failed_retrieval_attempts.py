"""Record pre-context retrieval failures without creating a Product session.

Revision ID: 20261009_0033
Revises: 20261009_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261009_0033"
down_revision: str | None = "20261009_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("retrieval_invocations", sa.Column("failure_class", sa.String(128)))


def downgrade() -> None:
    op.drop_column("retrieval_invocations", "failure_class")
