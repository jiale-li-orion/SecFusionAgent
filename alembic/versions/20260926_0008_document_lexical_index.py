"""document lexical retrieval index

Revision ID: 20260926_0008
Revises: 20260925_0007
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260926_0008"
down_revision: str | None = "20260925_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_NAME = "ix_document_chunks_fts_simple"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX {INDEX_NAME} ON document_chunks "
        "USING GIN (to_tsvector('simple', coalesce(text, '')))"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
