from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base


class DeploymentRevisionModel(Base):
    __tablename__ = "deployment_revisions"

    deployment_revision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    git_commit: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    container_image_digest: Mapped[str | None] = mapped_column(String(256))
    schema_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_inventory_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vocabulary_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_registry_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_registry_revision: Mapped[str | None] = mapped_column(String(128))
    model_provider_revision: Mapped[str] = mapped_column(String(256), nullable=False)
    configuration_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class CompetitionReportModel(Base):
    __tablename__ = "competition_reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    deployment_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("deployment_revisions.deployment_revision_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    benchmark_run_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    metric_definition_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    artifact_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class BenchmarkSuiteModel(Base):
    __tablename__ = "benchmark_suites"
    __table_args__ = (
        UniqueConstraint("suite_id", "suite_revision", name="uq_benchmark_suite_revision"),
    )

    suite_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    suite_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    case_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    gold_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluator_revision: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    default_world_snapshot_ref: Mapped[str | None] = mapped_column(String(256))
    scoring_profile_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BenchmarkCaseModel(Base):
    __tablename__ = "benchmark_cases"
    __table_args__ = (
        UniqueConstraint("case_id", "case_revision", name="uq_benchmark_case_revision"),
    )

    case_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    execution_profile: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    world_snapshot_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    fixture_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    expected_behavior_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    gold_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    latency_class: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    replay_tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BenchmarkRunModel(Base):
    __tablename__ = "benchmark_runs"

    benchmark_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_suites.suite_version_id", ondelete="RESTRICT"), index=True
    )
    suite_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    gold_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    deployment_revision_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("deployment_revisions.deployment_revision_id", ondelete="RESTRICT"),
        index=True,
    )
    model_config_ref: Mapped[str | None] = mapped_column(String(256))
    world_snapshot_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    warm_cold_condition: Mapped[str | None] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(128), nullable=False, index=True)


class BenchmarkCaseRunModel(Base):
    __tablename__ = "benchmark_case_runs"

    case_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    benchmark_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_runs.benchmark_run_id", ondelete="CASCADE"), index=True
    )
    case_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("benchmark_cases.case_version_id", ondelete="RESTRICT"), index=True
    )
    case_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    task_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_runs.run_id", ondelete="SET NULL"), index=True
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("execution_runs.execution_id", ondelete="SET NULL"), index=True
    )
    decision_ref: Mapped[str | None] = mapped_column(String(256))
    replay_checkpoint_ref: Mapped[str | None] = mapped_column(String(256))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(128), index=True)
    artifact_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class MetricDefinitionModel(Base):
    __tablename__ = "metric_definitions"

    metric_definition_ref: Mapped[str] = mapped_column(String(320), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    denominator: Mapped[str] = mapped_column(Text, nullable=False)
    aggregation: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_value_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64))
    definition_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class MetricObservationModel(Base):
    __tablename__ = "metric_observations"

    metric_observation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    metric_definition_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    measurement_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    case_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("benchmark_case_runs.case_run_id", ondelete="CASCADE"),
        index=True,
    )
    subject_ref: Mapped[str | None] = mapped_column(String(256), index=True)
    evidence_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
