"""add runtime budget ledger and capability invocation audit

Revision ID: 20260927_0017
Revises: 20260927_0016
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0017"
down_revision: str | None = "20260927_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_accounts",
        sa.Column("account_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "parent_account_id",
            sa.String(length=128),
            sa.ForeignKey("budget_accounts.account_id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    for column in ("parent_account_id", "task_run_id", "status"):
        op.create_index(f"ix_budget_accounts_{column}", "budget_accounts", [column])

    op.create_table(
        "budget_reservations",
        sa.Column("reservation_id", sa.String(length=36), primary_key=True),
        sa.Column("reservation_group_id", sa.String(length=256), nullable=False),
        sa.Column(
            "account_id",
            sa.String(length=128),
            sa.ForeignKey("budget_accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_account_id",
            sa.String(length=128),
            sa.ForeignKey("budget_accounts.account_id", ondelete="RESTRICT"),
        ),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("amount_reserved", sa.Numeric(24, 6), nullable=False),
        sa.Column("amount_committed", sa.Numeric(24, 6), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "reservation_group_id",
            "resource_type",
            name="uq_budget_reservation_group_resource",
        ),
    )
    for column in (
        "reservation_group_id",
        "account_id",
        "child_account_id",
        "resource_type",
        "status",
    ):
        op.create_index(
            f"ix_budget_reservations_{column}",
            "budget_reservations",
            [column],
        )

    op.create_table(
        "capability_invocations",
        sa.Column("invocation_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="SET NULL"),
        ),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("contract_revision", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("binding_revision", sa.Integer(), nullable=False),
        sa.Column("tool_impl_id", sa.String(length=128), nullable=False),
        sa.Column("implementation_revision", sa.Integer(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("policy_decision_ref", sa.String(length=256), nullable=False),
        sa.Column("policy_decision_json", sa.JSON(), nullable=False),
        sa.Column("arguments_digest", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("observation_json", sa.JSON()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(length=128)),
        sa.Column("failure_detail", sa.Text()),
        sa.UniqueConstraint(
            "task_run_id",
            "request_id",
            name="uq_capability_invocation_task_request",
        ),
    )
    for column in (
        "task_run_id",
        "case_id",
        "request_id",
        "capability_id",
        "binding_id",
        "tool_impl_id",
        "status",
        "finished_at",
        "failure_code",
    ):
        op.create_index(
            f"ix_capability_invocations_{column}",
            "capability_invocations",
            [column],
        )


def downgrade() -> None:
    op.drop_table("capability_invocations")
    op.drop_table("budget_reservations")
    op.drop_table("budget_accounts")
