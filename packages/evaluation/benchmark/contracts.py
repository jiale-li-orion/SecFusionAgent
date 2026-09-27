from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue


class BenchmarkDomain(StrEnum):
    M1_MONITORING = "m1_monitoring"
    M3_ENRICHMENT = "m3_enrichment"
    M5_AGENT = "m5_agent"
    M6_QA = "m6_qa"
    SECURITY = "security"
    PRODUCT_E2E = "product_e2e"


class BenchmarkExecutionMode(StrEnum):
    OFFLINE_SCORER = "offline_scorer"
    FROZEN_REPLAY = "frozen_replay"
    LIVE_CONTROLLED = "live_controlled"
    LIVE_EXTERNAL = "live_external"


class BenchmarkRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BenchmarkCaseRunStatus(StrEnum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    TARGET_ZERO = "target_zero"
    INFORMATIONAL = "informational"


class MeasurementSource(StrEnum):
    EXACT = "exact"
    SCORER = "scorer"
    PROVIDER_EXACT = "provider_exact"
    TOKENIZER_ESTIMATE = "tokenizer_estimate"
    RESERVATION_UPPER_BOUND = "reservation_upper_bound"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class DeploymentRevision(BaseModel):
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


class BenchmarkSuite(BaseModel):
    suite_id: str
    suite_revision: int = Field(ge=1)
    domain: BenchmarkDomain
    purpose: str
    case_refs: list[str]
    gold_revision: str
    evaluator_revision: str
    default_world_snapshot_ref: str | None = None
    scoring_profile: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime


class BenchmarkCase(BaseModel):
    case_id: str
    case_revision: int = Field(ge=1)
    input: dict[str, JsonValue]
    execution_profile: str
    target_refs: list[str] = Field(default_factory=list)
    world_snapshot_ref: str | None = None
    fixture_refs: list[str] = Field(default_factory=list)
    expected_behavior: dict[str, JsonValue] = Field(default_factory=dict)
    gold_ref: str
    tags: list[str] = Field(default_factory=list)
    latency_class: str
    replay_tier: str
    created_at: datetime


class BenchmarkRun(BaseModel):
    benchmark_run_id: str
    suite_ref: str
    gold_revision: str
    deployment_revision_id: str
    model_config_ref: str | None = None
    world_snapshot_ref: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: BenchmarkRunStatus
    execution_mode: BenchmarkExecutionMode
    warm_cold_condition: str | None = None
    environment: str


class BenchmarkCaseRun(BaseModel):
    case_run_id: str
    benchmark_run_id: str
    case_ref: str
    task_run_id: str | None = None
    execution_id: str | None = None
    decision_ref: str | None = None
    replay_checkpoint_ref: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: BenchmarkCaseRunStatus
    failure_class: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)


class MetricObservation(BaseModel):
    metric_observation_id: str
    metric_name: str
    metric_definition_revision: str
    value: float
    unit: str | None = None
    direction: MetricDirection
    measurement_source: MeasurementSource
    case_run_id: str
    subject_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime
