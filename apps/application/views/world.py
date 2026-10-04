from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorldHealthCountsView(BaseModel):
    healthy: int = 0
    degraded: int = 0
    blocked: int = 0


class WorldCategoryHealthView(BaseModel):
    category: str
    healthy: int = 0
    degraded: int = 0
    blocked: int = 0


class WorldWindowView(BaseModel):
    observations: int = 0
    fresh_external_changes: int = 0
    backfill_observations: int = 0
    canonical_writes: int = 0
    scheduled_runs: int = 0
    scheduled_run_success_rate: float | None = None
    provider_boundary_failure_rate: float | None = None
    runtime_owned_failure_rate: float | None = None
    queue_delay_p95_seconds: float | None = None
    execution_p95_seconds: float | None = None
    fresh_knowledge_latency_p95_seconds: float | None = None
    evidence_integrity_rate: float | None = None


class WorldSeriesPointView(BaseModel):
    hour_start: datetime
    observations: int = 0
    fresh_external_changes: int = 0
    backfill_observations: int = 0
    canonical_writes: int = 0
    scheduled_runs: int = 0
    scheduled_run_success_rate: float | None = None
    provider_boundary_failure_rate: float | None = None
    runtime_owned_failure_rate: float | None = None
    queue_delay_p95_seconds: float | None = None
    execution_p95_seconds: float | None = None
    fresh_knowledge_latency_p95_seconds: float | None = None


class WorldOverviewView(BaseModel):
    schema_version: str
    generated_at: datetime
    source_health: WorldHealthCountsView
    healthy_rate: float
    overdue_sources: int
    backfill_pending_sources: int
    categories: list[WorldCategoryHealthView] = Field(default_factory=list)
    windows: dict[str, WorldWindowView]
    hourly_series: list[WorldSeriesPointView] = Field(default_factory=list)
    outbox_delivered: int = 0
    lexical_ready_documents: int = 0
    artifact_store_status: str | None = None
    public_epoch_artifact_integrity_rate: float | None = None
