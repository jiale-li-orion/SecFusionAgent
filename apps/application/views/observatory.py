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
