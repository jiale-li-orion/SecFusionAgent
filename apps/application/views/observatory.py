from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProofMetricView(BaseModel):
    metric_name: str
    value: float
    unit: str | None = None
    direction: str


class ProofTargetView(BaseModel):
    target_name: str
    requirement: str
    metric_name: str
    observed_value: float
    threshold: float
    comparator: str
    status: str


class ProofRunSummaryView(BaseModel):
    benchmark_run_id: str
    suite_ref: str
    deployment_revision_id: str
    world_snapshot_ref: str | None = None
    status: str
    execution_mode: str
    environment: str
    started_at: datetime
    finished_at: datetime | None = None
    case_count: int
    passed_case_count: int


class ProofCaseRunView(BaseModel):
    case_run_id: str
    case_ref: str
    target_refs: list[str] = Field(default_factory=list)
    execution_profile: str | None = None
    status: str
    failure_class: str | None = None
    task_run_id: str | None = None
    execution_id: str | None = None
    decision_ref: str | None = None
    replay_checkpoint_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime | None = None


class ProofMetricObservationView(BaseModel):
    metric_observation_id: str
    metric_name: str
    value: float
    unit: str | None = None
    direction: str
    measurement_source: str
    case_run_id: str
    subject_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime


class ProofDeploymentRevisionView(BaseModel):
    deployment_revision_id: str
    git_commit: str
    container_image_digest: str | None = None
    schema_revision: str
    source_inventory_hash: str
    vocabulary_revision: str
    policy_revision: str
    capability_registry_revision: str
    skill_registry_revision: str | None = None
    model_provider_revision: str
    configuration_digest: str
    created_at: datetime


class ProofRunDetailView(BaseModel):
    run: ProofRunSummaryView
    deployment: ProofDeploymentRevisionView
    cases: list[ProofCaseRunView] = Field(default_factory=list)
    metrics: list[ProofMetricObservationView] = Field(default_factory=list)


class CompetitionProofView(BaseModel):
    report_id: str
    report_digest: str
    deployment_revision_id: str
    generated_at: datetime
    benchmark_runs_completed: int
    case_runs_passed: int
    registered_core_metrics: int
    observed_core_metrics: int
    metric_groups: int
    observed_metric_groups: int
    partial_metric_groups: int
    unevaluated_core_metrics: list[str] = Field(default_factory=list)
    headline_metrics: list[ProofMetricView] = Field(default_factory=list)
    target_checks: list[ProofTargetView] = Field(default_factory=list)
    runs: list[ProofRunSummaryView] = Field(default_factory=list)
