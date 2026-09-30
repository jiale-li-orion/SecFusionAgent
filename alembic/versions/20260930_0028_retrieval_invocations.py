"""add retrieval invocation provenance

Revision ID: 20260930_0028
Revises: 20260930_0027
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260930_0028"
down_revision: str | None = "20260930_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retrieval_invocations",
        sa.Column("invocation_id", sa.String(length=36), primary_key=True),
        sa.Column("request_owner_ref", sa.String(length=256), nullable=False),
        sa.Column("product_session_id", sa.String(length=36), nullable=False),
        sa.Column("product_turn_index", sa.Integer(), nullable=False),
        sa.Column("operator", sa.String(length=64), nullable=False),
        sa.Column("operator_revision", sa.String(length=128), nullable=False),
        sa.Column("query_digest", sa.String(length=64), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("knowledge_revision", sa.Integer(), nullable=False),
        sa.Column("result_limit", sa.Integer(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("result_refs", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column(
            "reuse_of_invocation_id",
            sa.String(length=36),
            sa.ForeignKey("retrieval_invocations.invocation_id", ondelete="SET NULL"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "request_owner_ref",
        "product_session_id",
        "product_turn_index",
        "operator",
        "operator_revision",
        "query_digest",
        "request_digest",
        "knowledge_revision",
        "disposition",
        "reuse_of_invocation_id",
        "finished_at",
    ):
        op.create_index(
            f"ix_retrieval_invocations_{column}",
            "retrieval_invocations",
            [column],
        )


def downgrade() -> None:
    op.drop_table("retrieval_invocations")
