"""add model execution records

Revision ID: 20260927_0021
Revises: 20260927_0020
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0021"
down_revision: str | None = "20260927_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_requests",
        sa.Column("model_request_id", sa.String(length=36), primary_key=True),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column("request_owner_ref", sa.String(length=256), nullable=False),
        sa.Column(
            "execution_id",
            sa.String(length=128),
            sa.ForeignKey("execution_runs.execution_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="SET NULL"),
        ),
        sa.Column("processing_run_id", sa.String(length=128)),
        sa.Column("prompt_assembly_id", sa.String(length=128)),
        sa.Column("prompt_revision", sa.String(length=128), nullable=False),
        sa.Column("request_schema_digest", sa.String(length=64), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("request_artifact_ref", sa.String(length=256)),
        sa.Column("requested_model", sa.String(length=256), nullable=False),
        sa.Column("provider_policy_ref", sa.String(length=256)),
        sa.Column(
            "budget_ref",
            sa.String(length=128),
            sa.ForeignKey("budget_accounts.account_id", ondelete="SET NULL"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "purpose",
        "request_owner_ref",
        "execution_id",
        "task_run_id",
        "case_id",
        "processing_run_id",
        "prompt_assembly_id",
        "prompt_revision",
        "request_digest",
        "requested_model",
        "budget_ref",
        "created_at",
    ):
        op.create_index(f"ix_model_requests_{column}", "model_requests", [column])

    op.create_table(
        "model_attempts",
        sa.Column("model_attempt_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "model_request_id",
            sa.String(length=36),
            sa.ForeignKey("model_requests.model_request_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("adapter_revision", sa.String(length=128), nullable=False),
        sa.Column("actual_model", sa.String(length=256), nullable=False),
        sa.Column("provider_request_id", sa.String(length=256)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=128)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("response_schema_digest", sa.String(length=64), nullable=False),
        sa.Column("response_artifact_ref", sa.String(length=256)),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("cost_json", sa.JSON(), nullable=False),
        sa.Column("cache_usage_json", sa.JSON(), nullable=False),
        sa.Column("response_metadata_json", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.BigInteger()),
        sa.UniqueConstraint(
            "model_request_id",
            "ordinal",
            name="uq_model_attempt_request_ordinal",
        ),
    )
    for column in (
        "model_request_id",
        "provider",
        "actual_model",
        "provider_request_id",
        "started_at",
        "finished_at",
        "status",
        "failure_class",
    ):
        op.create_index(f"ix_model_attempts_{column}", "model_attempts", [column])


def downgrade() -> None:
    op.drop_table("model_attempts")
    op.drop_table("model_requests")
