"""Independent, principal-scoped activity feedback.

Revision ID: 20261012_0035
Revises: 20261009_0034
"""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0035"
down_revision = "20261009_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_activity_feedback",
        sa.Column("principal", sa.String(256), primary_key=True),
        sa.Column("activity_id", sa.String(64), primary_key=True),
        sa.Column("feedback", sa.String(16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "feedback IN ('interested','ignored','neutral')", name="ck_activity_feedback_value"
        ),
    )


def downgrade() -> None:
    op.drop_table("intelligence_activity_feedback")
