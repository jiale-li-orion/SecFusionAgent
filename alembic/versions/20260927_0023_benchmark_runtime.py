"""add benchmark runtime

Revision ID: 20260927_0023
Revises: 20260927_0022
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0023"
down_revision: str | None = "20260927_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deployment_revisions",
        sa.Column("deployment_revision_id", sa.String(length=128), primary_key=True),
        sa.Column("git_commit", sa.String(length=128), nullable=False),
        sa.Column("container_image_digest", sa.String(length=256)),
        sa.Column("schema_revision", sa.String(length=128), nullable=False),
        sa.Column("source_inventory_hash", sa.String(length=64), nullable=False),
        sa.Column("vocabulary_revision", sa.String(length=128), nullable=False),
        sa.Column("policy_revision", sa.String(length=128), nullable=False),
        sa.Column("capability_registry_revision", sa.String(length=128), nullable=False),
        sa.Column("skill_registry_revision", sa.String(length=128)),
        sa.Column("model_provider_revision", sa.String(length=256), nullable=False),
        sa.Column("configuration_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _indexes(
        "deployment_revisions",
        ("git_commit", "schema_revision", "created_at"),
    )

    op.create_table(
        "benchmark_cases",
        sa.Column("case_version_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("case_revision", sa.Integer(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("execution_profile", sa.String(length=128), nullable=False),
        sa.Column("target_refs_json", sa.JSON(), nullable=False),
        sa.Column("world_snapshot_ref", sa.String(length=256)),
        sa.Column("fixture_refs_json", sa.JSON(), nullable=False),
        sa.Column("expected_behavior_json", sa.JSON(), nullable=False),
        sa.Column("gold_ref", sa.String(length=256), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("latency_class", sa.String(length=64), nullable=False),
        sa.Column("replay_tier", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_id", "case_revision", name="uq_benchmark_case_revision"),
    )
    _indexes(
        "benchmark_cases",
        ("case_id", "execution_profile", "world_snapshot_ref", "latency_class", "replay_tier"),
    )

    op.create_table(
        "benchmark_suites",
        sa.Column("suite_version_id", sa.String(length=36), primary_key=True),
        sa.Column("suite_id", sa.String(length=128), nullable=False),
        sa.Column("suite_revision", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("case_refs_json", sa.JSON(), nullable=False),
        sa.Column("gold_revision", sa.String(length=128), nullable=False),
        sa.Column("evaluator_revision", sa.String(length=128), nullable=False),
        sa.Column("default_world_snapshot_ref", sa.String(length=256)),
        sa.Column("scoring_profile_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("suite_id", "suite_revision", name="uq_benchmark_suite_revision"),
    )
    _indexes(
        "benchmark_suites",
        ("suite_id", "domain", "gold_revision", "evaluator_revision"),
    )

    op.create_table(
        "benchmark_runs",
        sa.Column("benchmark_run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "suite_version_id",
            sa.String(length=36),
            sa.ForeignKey("benchmark_suites.suite_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("suite_ref", sa.String(length=256), nullable=False),
        sa.Column("gold_revision", sa.String(length=128), nullable=False),
        sa.Column(
            "deployment_revision_id",
            sa.String(length=128),
            sa.ForeignKey("deployment_revisions.deployment_revision_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("model_config_ref", sa.String(length=256)),
        sa.Column("world_snapshot_ref", sa.String(length=256)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_mode", sa.String(length=32), nullable=False),
        sa.Column("warm_cold_condition", sa.String(length=64)),
        sa.Column("environment", sa.String(length=128), nullable=False),
    )
    _indexes(
        "benchmark_runs",
        (
            "suite_version_id",
            "suite_ref",
            "deployment_revision_id",
            "world_snapshot_ref",
            "started_at",
            "finished_at",
            "status",
            "execution_mode",
            "environment",
        ),
    )

    op.create_table(
        "benchmark_case_runs",
        sa.Column("case_run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "benchmark_run_id",
            sa.String(length=36),
            sa.ForeignKey("benchmark_runs.benchmark_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_version_id",
            sa.String(length=36),
            sa.ForeignKey("benchmark_cases.case_version_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("case_ref", sa.String(length=256), nullable=False),
        sa.Column(
            "task_run_id",
            sa.String(length=36),
            sa.ForeignKey("task_runs.run_id", ondelete="SET NULL"),
        ),
        sa.Column(
            "execution_id",
            sa.String(length=128),
            sa.ForeignKey("execution_runs.execution_id", ondelete="SET NULL"),
        ),
        sa.Column("decision_ref", sa.String(length=256)),
        sa.Column("replay_checkpoint_ref", sa.String(length=256)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=128)),
        sa.Column("artifact_refs_json", sa.JSON(), nullable=False),
    )
    _indexes(
        "benchmark_case_runs",
        (
            "benchmark_run_id",
            "case_version_id",
            "case_ref",
            "task_run_id",
            "execution_id",
            "started_at",
            "finished_at",
            "status",
            "failure_class",
        ),
    )

    op.create_table(
        "metric_observations",
        sa.Column("metric_observation_id", sa.String(length=36), primary_key=True),
        sa.Column("metric_name", sa.String(length=256), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64)),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("measurement_source", sa.String(length=64), nullable=False),
        sa.Column(
            "case_run_id",
            sa.String(length=36),
            sa.ForeignKey("benchmark_case_runs.case_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_ref", sa.String(length=256)),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _indexes(
        "metric_observations",
        (
            "metric_name",
            "direction",
            "measurement_source",
            "case_run_id",
            "subject_ref",
            "created_at",
        ),
    )


def downgrade() -> None:
    op.drop_table("metric_observations")
    op.drop_table("benchmark_case_runs")
    op.drop_table("benchmark_runs")
    op.drop_table("benchmark_suites")
    op.drop_table("benchmark_cases")
    op.drop_table("deployment_revisions")


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])
