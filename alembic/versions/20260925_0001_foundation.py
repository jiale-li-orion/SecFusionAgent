"""foundation runtime tables

Revision ID: 20260925_0001
Revises:
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("source_id", sa.String(length=128), primary_key=True),
        sa.Column("adapter_type", sa.String(length=64), nullable=False),
        sa.Column("source_class", sa.String(length=64), nullable=False),
        sa.Column("authority_scope", sa.JSON(), nullable=False),
        sa.Column("source_role", sa.String(length=32), nullable=False),
        sa.Column("source_family", sa.String(length=128), nullable=False),
        sa.Column("upstream_source", sa.String(length=256)),
        sa.Column("access_mode", sa.String(length=64), nullable=False),
        sa.Column("update_semantics", sa.String(length=128), nullable=False),
        sa.Column("discovery_method", sa.JSON(), nullable=False),
        sa.Column("time_semantics", sa.JSON(), nullable=False),
        sa.Column("identity_semantics", sa.JSON(), nullable=False),
        sa.Column("auth_ref", sa.String(length=256)),
        sa.Column("rate_limit_policy", sa.JSON(), nullable=False),
        sa.Column("access_rights", sa.JSON(), nullable=False),
        sa.Column("retention_mode", sa.String(length=32), nullable=False),
        sa.Column("schedule_policy", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=False),
        sa.Column("managed_by", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_adapter_type", "sources", ["adapter_type"])
    op.create_index("ix_sources_source_class", "sources", ["source_class"])
    op.create_index("ix_sources_source_family", "sources", ["source_family"])
    op.create_index("ix_sources_retention_mode", "sources", ["retention_mode"])

    op.create_table(
        "source_state",
        sa.Column(
            "source_id",
            sa.String(length=128),
            sa.ForeignKey("sources.source_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_change_at", sa.DateTime(timezone=True)),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("backoff_until", sa.DateTime(timezone=True)),
        sa.Column("rate_limit_state", sa.JSON(), nullable=False),
    )
    op.create_index("ix_source_state_next_due_at", "source_state", ["next_due_at"])
    op.create_index("ix_source_state_backoff_until", "source_state", ["backoff_until"])

    op.create_table(
        "acquisition_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=128),
            sa.ForeignKey("sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cursor_in", sa.JSON(), nullable=False),
        sa.Column("cursor_out", sa.JSON(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("error_detail", sa.Text()),
    )
    op.create_index("ix_acquisition_runs_source_id", "acquisition_runs", ["source_id"])
    op.create_index("ix_acquisition_runs_status", "acquisition_runs", ["status"])

    op.create_table(
        "processing_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("processor_type", sa.String(length=64), nullable=False),
        sa.Column("processor_name", sa.String(length=128), nullable=False),
        sa.Column("processor_version", sa.String(length=64), nullable=False),
        sa.Column("input_revision_ids", sa.JSON(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128)),
        sa.Column("prompt_version", sa.String(length=128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=128)),
    )
    op.create_index("ix_processing_runs_processor_type", "processing_runs", ["processor_type"])
    op.create_index("ix_processing_runs_status", "processing_runs", ["status"])

    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=256), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("ix_outbox_events_topic", "outbox_events", ["topic"])
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_available_at", "outbox_events", ["available_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("processing_runs")
    op.drop_table("acquisition_runs")
    op.drop_table("source_state")
    op.drop_table("sources")
