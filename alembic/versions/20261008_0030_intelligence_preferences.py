"""Add principal-scoped intelligence preferences and recommendation feedback.

Revision ID: 20261008_0030
Revises: 20261002_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261008_0030"
down_revision: str | None = "20261002_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intelligence_preferences",
        sa.Column("principal", sa.String(256), primary_key=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("target_object_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_recommendation_feedback",
        sa.Column("principal", sa.String(256), primary_key=True),
        sa.Column(
            "object_id",
            sa.String(36),
            sa.ForeignKey("objects.object_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feedback", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "feedback IN ('interested','ignored','neutral')",
            name="ck_intelligence_recommendation_feedback_value",
        ),
    )


def downgrade() -> None:
    op.drop_table("intelligence_recommendation_feedback")
    op.drop_table("intelligence_preferences")
