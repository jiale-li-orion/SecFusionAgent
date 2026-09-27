"""add versioned runtime skills

Revision ID: 20260927_0018
Revises: 20260927_0017
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0018"
down_revision: str | None = "20260927_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_versions",
        sa.Column("skill_version_id", sa.String(length=36), primary_key=True),
        sa.Column("skill_id", sa.String(length=256), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("procedure_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_ref", sa.String(length=256)),
        sa.Column("supersedes", sa.String(length=256)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_versions_identity"),
    )
    for column in (
        "skill_id",
        "namespace",
        "status",
        "source_type",
        "validation_ref",
        "supersedes",
    ):
        op.create_index(f"ix_skill_versions_{column}", "skill_versions", [column])


def downgrade() -> None:
    op.drop_table("skill_versions")
