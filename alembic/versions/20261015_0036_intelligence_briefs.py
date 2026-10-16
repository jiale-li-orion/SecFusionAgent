"""Versioned public intelligence report publication records.

Revision ID: 20261015_0036
Revises: 20261012_0035
"""

import sqlalchemy as sa

from alembic import op

revision = "20261015_0036"
down_revision = "20261012_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_briefs",
        sa.Column("brief_id", sa.String(64), primary_key=True),
        sa.Column("input_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("topic", sa.String(180), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "decision_id",
            sa.String(128),
            sa.ForeignKey("decision_results.decision_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("material_manifest", sa.JSON(), nullable=False),
        sa.Column("review_json", sa.JSON(), nullable=False),
        sa.Column("policy_revision", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_intelligence_briefs_status", "intelligence_briefs", ["status"])
    op.create_index("ix_intelligence_briefs_created_at", "intelligence_briefs", ["created_at"])


def downgrade() -> None:
    op.drop_table("intelligence_briefs")
