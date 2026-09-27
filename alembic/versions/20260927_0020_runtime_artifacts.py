"""add runtime artifact registry

Revision ID: 20260927_0020
Revises: 20260927_0019
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0020"
down_revision: str | None = "20260927_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_artifacts",
        sa.Column("artifact_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "execution_id",
            sa.String(length=128),
            sa.ForeignKey("execution_runs.execution_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("producer_kind", sa.String(length=64), nullable=False),
        sa.Column("producer_ref", sa.String(length=256)),
        sa.Column("logical_name", sa.String(length=256), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("trust_class", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "execution_id",
            "logical_name",
            "content_hash",
            name="uq_runtime_artifact_execution_name_hash",
        ),
    )
    for column in (
        "execution_id",
        "producer_kind",
        "producer_ref",
        "content_hash",
        "trust_class",
    ):
        op.create_index(f"ix_runtime_artifacts_{column}", "runtime_artifacts", [column])


def downgrade() -> None:
    op.drop_table("runtime_artifacts")
