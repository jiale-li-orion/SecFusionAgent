from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SystemDependencyView(BaseModel):
    component: str
    status: str
    latency_ms: float | None = None
    detail_code: str | None = None


class SystemBacklogView(BaseModel):
    pending_count: int = 0
    oldest_pending_at: datetime | None = None


class SystemOverviewView(BaseModel):
    generated_at: datetime
    overall: str
    dependencies: list[SystemDependencyView] = Field(default_factory=list)
    outbox: SystemBacklogView
    task_event_delivery: SystemBacklogView
    task_event_stream_pending: int | None = None
    runtime_policy_status: str
    model_provider_status: str
    measurement_boundaries: dict[str, str] = Field(default_factory=dict)
