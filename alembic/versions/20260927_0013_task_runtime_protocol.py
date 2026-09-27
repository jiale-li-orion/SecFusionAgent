"""add shared task runtime protocol state

Revision ID: 20260927_0013
Revises: 20260927_0012
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0013"
down_revision: str | None = "20260927_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_contract_versions",
        sa.Column("task_contract_version_id", sa.String(length=36), primary_key=True),
        sa.Column("task_contract_id", sa.String(length=128), nullable=False),
        sa.Column("contract_revision", sa.Integer(), nullable=False),
        sa.Column("principal", sa.String(length=256), nullable=False),
        sa.Column("on_behalf_of", sa.String(length=256)),
        sa.Column("task_kind", sa.String(length=64), nullable=False),
        sa.Column("effect_ceiling", sa.String(length=64), nullable=False),
        sa.Column("policy_revision", sa.String(length=128), nullable=False),
        sa.Column("contract_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "task_contract_id", "contract_revision", name="uq_task_contract_revision"
        ),
    )
    op.create_index(
        "ix_task_contract_versions_task_contract_id", "task_contract_versions", ["task_contract_id"]
    )
    op.create_index("ix_task_contract_versions_principal", "task_contract_versions", ["principal"])
    op.create_index(
        "ix_task_contract_versions_on_behalf_of", "task_contract_versions", ["on_behalf_of"]
    )
    op.create_index("ix_task_contract_versions_task_kind", "task_contract_versions", ["task_kind"])

    op.create_table(
        "context_manifest_versions",
        sa.Column("context_manifest_version_id", sa.String(length=36), primary_key=True),
        sa.Column("context_id", sa.String(length=128), nullable=False),
        sa.Column("context_revision", sa.Integer(), nullable=False),
        sa.Column("parent_context_id", sa.String(length=128)),
        sa.Column(
            "task_contract_version_id",
            sa.String(length=36),
            sa.ForeignKey("task_contract_versions.task_contract_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role_ref", sa.String(length=256), nullable=False),
        sa.Column("case_ref", sa.String(length=256)),
        sa.Column("knowledge_revision", sa.Integer()),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("context_id", "context_revision", name="uq_context_manifest_revision"),
    )
    op.create_index(
        "ix_context_manifest_versions_context_id", "context_manifest_versions", ["context_id"]
    )
    op.create_index(
        "ix_context_manifest_versions_parent_context_id",
        "context_manifest_versions",
        ["parent_context_id"],
    )
    op.create_index(
        "ix_context_manifest_versions_task_contract_version_id",
        "context_manifest_versions",
        ["task_contract_version_id"],
    )
    op.create_index(
        "ix_context_manifest_versions_case_ref", "context_manifest_versions", ["case_ref"]
    )
    op.create_index(
        "ix_context_manifest_versions_knowledge_revision",
        "context_manifest_versions",
        ["knowledge_revision"],
    )

    op.create_table(
        "task_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_contract_version_id",
            sa.String(length=36),
            sa.ForeignKey("task_contract_versions.task_contract_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("task_contract_id", sa.String(length=128), nullable=False),
        sa.Column("task_contract_revision", sa.Integer(), nullable=False),
        sa.Column(
            "context_manifest_version_id",
            sa.String(length=36),
            sa.ForeignKey(
                "context_manifest_versions.context_manifest_version_id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("context_id", sa.String(length=128), nullable=False),
        sa.Column("context_revision", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(length=36)),
        sa.Column(
            "parent_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column("role_id", sa.String(length=128), nullable=False),
        sa.Column("role_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("base_context_revision", sa.Integer(), nullable=False),
        sa.Column("execution_envelope_ref", sa.String(length=256), nullable=False),
        sa.Column("result_ref", sa.String(length=512)),
        sa.Column("stop_reason", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    for column in (
        "task_contract_version_id",
        "task_contract_id",
        "context_manifest_version_id",
        "context_id",
        "case_id",
        "parent_run_id",
        "role_id",
        "status",
        "stop_reason",
        "finished_at",
    ):
        op.create_index(f"ix_task_runs_{column}", "task_runs", [column])

    op.create_table(
        "task_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_run_id", sa.String(length=36)),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("producer", sa.String(length=128), nullable=False),
        sa.Column("base_context_revision", sa.Integer(), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_run_id", "seq", name="uq_task_event_seq"),
        sa.UniqueConstraint("task_run_id", "idempotency_key", name="uq_task_event_idempotency"),
    )
    for column in ("task_run_id", "parent_run_id", "event_type", "emitted_at"):
        op.create_index(f"ix_task_events_{column}", "task_events", [column])

    op.create_table(
        "task_event_deliveries",
        sa.Column(
            "event_id",
            sa.String(length=36),
            sa.ForeignKey("task_events.event_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stream_name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("redis_message_id", sa.String(length=128)),
        sa.Column("last_error", sa.Text()),
    )
    for column in ("stream_name", "status", "available_at"):
        op.create_index(f"ix_task_event_deliveries_{column}", "task_event_deliveries", [column])


def downgrade() -> None:
    op.drop_table("task_event_deliveries")
    op.drop_table("task_events")
    op.drop_table("task_runs")
    op.drop_table("context_manifest_versions")
    op.drop_table("task_contract_versions")
