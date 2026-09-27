"""add execution and sandbox runtime audit state

Revision ID: 20260927_0019
Revises: 20260927_0018
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0019"
down_revision: str | None = "20260927_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_runs",
        sa.Column("execution_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "parent_execution_id",
            sa.String(length=128),
            sa.ForeignKey("execution_runs.execution_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("envelope_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stop_reason", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in (
        "parent_execution_id",
        "task_run_id",
        "status",
        "stop_reason",
        "finished_at",
    ):
        op.create_index(f"ix_execution_runs_{column}", "execution_runs", [column])

    op.create_table(
        "sandbox_instances",
        sa.Column("instance_id", sa.String(length=36), primary_key=True),
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
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_revision", sa.String(length=64), nullable=False),
        sa.Column("backend", sa.String(length=128), nullable=False),
        sa.Column("backend_handle_ref", sa.String(length=256)),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("lease_json", sa.JSON(), nullable=False),
        sa.Column("policy_decision_ref", sa.String(length=256), nullable=False),
        sa.Column("policy_decision_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("destroyed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(length=128)),
        sa.UniqueConstraint(
            "execution_id",
            "request_id",
            name="uq_sandbox_instance_request",
        ),
    )
    for column in (
        "execution_id",
        "task_run_id",
        "request_id",
        "profile_id",
        "backend",
        "status",
        "destroyed_at",
        "failure_code",
    ):
        op.create_index(f"ix_sandbox_instances_{column}", "sandbox_instances", [column])

    op.create_table(
        "sandbox_executions",
        sa.Column("sandbox_execution_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "instance_id",
            sa.String(length=36),
            sa.ForeignKey("sandbox_instances.instance_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.String(length=128), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("timeout_seconds", sa.Numeric(18, 6), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(length=128)),
        sa.UniqueConstraint(
            "instance_id",
            "operation_id",
            name="uq_sandbox_execution_operation",
        ),
    )
    for column in (
        "instance_id",
        "operation_id",
        "status",
        "finished_at",
        "failure_code",
    ):
        op.create_index(f"ix_sandbox_executions_{column}", "sandbox_executions", [column])


def downgrade() -> None:
    op.drop_table("sandbox_executions")
    op.drop_table("sandbox_instances")
    op.drop_table("execution_runs")
