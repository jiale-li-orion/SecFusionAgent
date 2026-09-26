"""document dense embedding storage

Revision ID: 20260926_0009
Revises: 20260926_0008
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "20260926_0009"
down_revision: str | None = "20260926_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("document_chunks", sa.Column("embedding", Vector(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding")
