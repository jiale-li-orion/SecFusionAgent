"""add prompt assembly records

Revision ID: 20260927_0022
Revises: 20260927_0021
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0022"
down_revision: str | None = "20260927_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_assembly_records",
        sa.Column("assembly_id", sa.String(length=36), primary_key=True),
        sa.Column("assembly_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "execution_id",
            sa.String(length=128),
            sa.ForeignKey("execution_runs.execution_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_contract_id", sa.String(length=36), nullable=False),
        sa.Column("context_manifest_ref", sa.String(length=256), nullable=False),
        sa.Column("context_manifest_revision", sa.Integer(), nullable=False),
        sa.Column("role_revision", sa.String(length=128), nullable=False),
        sa.Column("platform_invariant_revision", sa.String(length=128), nullable=False),
        sa.Column("execution_profile_revision", sa.String(length=128), nullable=False),
        sa.Column("policy_context_revision", sa.String(length=256), nullable=False),
        sa.Column("state_projection_revision", sa.String(length=256)),
        sa.Column("percept_refs_json", sa.JSON(), nullable=False),
        sa.Column("materialized_skill_refs_json", sa.JSON(), nullable=False),
        sa.Column("materialized_capability_view_refs_json", sa.JSON(), nullable=False),
        sa.Column("materialized_fragment_refs_json", sa.JSON(), nullable=False),
        sa.Column("ordered_fragment_ids_json", sa.JSON(), nullable=False),
        sa.Column("materialized_ref_set_digest", sa.String(length=64), nullable=False),
        sa.Column("cache_handle_hints_json", sa.JSON(), nullable=False),
        sa.Column("fragment_manifest_json", sa.JSON(), nullable=False),
        sa.Column("request_artifact_ref", sa.String(length=256)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "assembly_hash",
        "execution_id",
        "task_run_id",
        "task_contract_id",
        "context_manifest_ref",
        "role_revision",
        "created_at",
    ):
        op.create_index(
            f"ix_prompt_assembly_records_{column}",
            "prompt_assembly_records",
            [column],
        )


def downgrade() -> None:
    op.drop_table("prompt_assembly_records")
