"""add immutable M6 decision results

Revision ID: 20260929_0026
Revises: 20260927_0025
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260929_0026"
down_revision: str | None = "20260927_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_results",
        sa.Column("decision_id", sa.String(length=128), primary_key=True),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_decision_results_case_id", "decision_results", ["case_id"])
    op.create_index(
        "ix_decision_results_case_revision", "decision_results", ["case_revision"]
    )
    op.create_index("ix_decision_results_created_at", "decision_results", ["created_at"])


def downgrade() -> None:
    op.drop_table("decision_results")
