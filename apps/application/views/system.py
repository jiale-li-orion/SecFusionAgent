from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SystemDependencyView(BaseModel):
    component: str
    status: str
    latency_ms: float | None = None
    detail_code: str | None = None


class SystemBacklogView(BaseModel):
    pending_count: int = 0
    oldest_pending_at: datetime | None = None


class SystemWorkerView(BaseModel):
    name: str
    availability: Literal["responding", "partial_response"]
    ping_responded: bool
    queue_response_received: bool
    queue_names: list[str] = Field(default_factory=list)
    checked_at: datetime
    failure_code: str | None = None


class SystemWorkerQueueView(BaseModel):
    queue_name: str
    availability: Literal["available", "unobserved", "unknown"]
    consumer_names: list[str] = Field(default_factory=list)
    checked_at: datetime
    failure_code: str | None = None


class SystemWorkerProbeView(BaseModel):
    status: Literal["healthy", "degraded", "unavailable"]
    scope: Literal["celery_control_ping_and_active_queues"] = (
        "celery_control_ping_and_active_queues"
    )
    checked_at: datetime
    completed_at: datetime
    failure_code: str | None = None
    workers: list[SystemWorkerView] = Field(default_factory=list)
    queues: list[SystemWorkerQueueView] = Field(default_factory=list)


class SystemOverviewView(BaseModel):
    generated_at: datetime
    overall: str
    dependencies: list[SystemDependencyView] = Field(default_factory=list)
    outbox: SystemBacklogView
    task_event_delivery: SystemBacklogView
    task_event_stream_pending: int | None = None
    runtime_policy_status: str
    model_provider_status: str
    worker_probe: SystemWorkerProbeView
    measurement_boundaries: dict[str, str] = Field(default_factory=dict)
