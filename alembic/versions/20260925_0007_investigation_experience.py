"""investigation case trajectory and experience memory

Revision ID: 20260925_0007
Revises: 20260925_0006
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0007"
down_revision: str | None = "20260925_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investigation_cases",
        sa.Column("case_id", sa.String(length=36), primary_key=True),
        sa.Column("task_signature", sa.String(length=256), nullable=False),
        sa.Column("target_object_ids", sa.JSON(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("initial_knowledge_revision", sa.Integer()),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_investigation_cases_task_signature",
        "investigation_cases",
        ["task_signature"],
    )
    op.create_index("ix_investigation_cases_status", "investigation_cases", ["status"])

    op.create_table(
        "investigation_trajectories",
        sa.Column("trajectory_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32)),
        sa.Column("retrieved_experience_versions", sa.JSON(), nullable=False),
        sa.Column("used_experience_versions", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Float()),
        sa.Column("outcome_summary", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_investigation_trajectories_case_id",
        "investigation_trajectories",
        ["case_id"],
    )
    op.create_index(
        "ix_investigation_trajectories_status",
        "investigation_trajectories",
        ["status"],
    )
    op.create_index(
        "ix_investigation_trajectories_outcome",
        "investigation_trajectories",
        ["outcome"],
    )

    op.create_table(
        "trajectory_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "trajectory_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("experience_version_refs", sa.JSON(), nullable=False),
        sa.Column("artifact_uri", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "trajectory_id",
            "ordinal",
            name="uq_trajectory_event_ordinal",
        ),
    )
    op.create_index(
        "ix_trajectory_events_trajectory_id",
        "trajectory_events",
        ["trajectory_id"],
    )
    op.create_index("ix_trajectory_events_event_type", "trajectory_events", ["event_type"])
    op.create_index("ix_trajectory_events_occurred_at", "trajectory_events", ["occurred_at"])

    op.create_table(
        "experience_candidates",
        sa.Column("candidate_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_trajectory_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extraction_kind", sa.String(length=64), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_experience_candidates_source_trajectory_id",
        "experience_candidates",
        ["source_trajectory_id"],
    )
    op.create_index(
        "ix_experience_candidates_extraction_kind",
        "experience_candidates",
        ["extraction_kind"],
    )
    op.create_index(
        "ix_experience_candidates_status",
        "experience_candidates",
        ["status"],
    )

    op.create_table(
        "experiences",
        sa.Column("experience_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("task_signature", sa.String(length=256), nullable=False),
        sa.Column("current_version_id", sa.String(length=36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experiences_task_signature", "experiences", ["task_signature"])
    op.create_index("ix_experiences_current_version_id", "experiences", ["current_version_id"])

    op.create_table(
        "experience_versions",
        sa.Column("experience_version_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experience_id",
            sa.String(length=36),
            sa.ForeignKey("experiences.experience_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("trigger_signals", sa.JSON(), nullable=False),
        sa.Column("applicable_conditions", sa.JSON(), nullable=False),
        sa.Column("recommended_actions", sa.JSON(), nullable=False),
        sa.Column("evidence_expectation", sa.JSON(), nullable=False),
        sa.Column("failure_modes", sa.JSON(), nullable=False),
        sa.Column("stop_conditions", sa.JSON(), nullable=False),
        sa.Column("fallback_actions", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("partial_count", sa.Integer(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "supersedes_version_id",
            sa.String(length=36),
            sa.ForeignKey("experience_versions.experience_version_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "source_candidate_id",
            sa.String(length=36),
            sa.ForeignKey("experience_candidates.candidate_id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("deprecated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "experience_id",
            "version",
            name="uq_experience_version_number",
        ),
    )
    op.create_index(
        "ix_experience_versions_experience_id",
        "experience_versions",
        ["experience_id"],
    )
    op.create_index("ix_experience_versions_status", "experience_versions", ["status"])
    op.create_index(
        "ix_experience_versions_supersedes_version_id",
        "experience_versions",
        ["supersedes_version_id"],
    )
    op.create_index(
        "ix_experience_versions_source_candidate_id",
        "experience_versions",
        ["source_candidate_id"],
    )

    op.create_table(
        "experience_support",
        sa.Column("support_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experience_version_id",
            sa.String(length=36),
            sa.ForeignKey("experience_versions.experience_version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trajectory_id",
            sa.String(length=36),
            sa.ForeignKey("investigation_trajectories.trajectory_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=False),
        sa.Column("evaluator", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "experience_version_id",
            "trajectory_id",
            name="uq_experience_support_trajectory",
        ),
    )
    op.create_index(
        "ix_experience_support_experience_version_id",
        "experience_support",
        ["experience_version_id"],
    )
    op.create_index(
        "ix_experience_support_trajectory_id",
        "experience_support",
        ["trajectory_id"],
    )
    op.create_index("ix_experience_support_outcome", "experience_support", ["outcome"])


def downgrade() -> None:
    op.drop_table("experience_support")
    op.drop_table("experience_versions")
    op.drop_table("experiences")
    op.drop_table("experience_candidates")
    op.drop_table("trajectory_events")
    op.drop_table("investigation_trajectories")
    op.drop_table("investigation_cases")
