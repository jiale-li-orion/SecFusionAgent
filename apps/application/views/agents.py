from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRoleRuntimeView(BaseModel):
    role_id: str
    version: str
    state_model: str
    planner_profile: str
    default_execution_profile: str
    accepted_task_kinds: list[str] = Field(default_factory=list)
    skill_scope: list[str] = Field(default_factory=list)
    status_counts: dict[str, int] = Field(default_factory=dict)
    active_tasks: int = 0
    total_tasks: int = 0
    last_updated_at: datetime | None = None


class AgentTaskSummaryView(BaseModel):
    run_id: str
    task_kind: str
    case_id: str | None = None
    parent_run_id: str | None = None
    role_id: str
    role_version: str
    status: str
    stop_reason: str | None = None
    result_available: bool = False
    event_count: int = 0
    last_event_type: str | None = None
    last_event_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class AgentTaskEventView(BaseModel):
    event_id: str
    seq: int
    event_type: str
    producer: str
    emitted_at: datetime


class AgentCapabilityActivityView(BaseModel):
    invocation_id: str
    task_run_id: str
    case_id: str | None = None
    capability_id: str
    binding_id: str
    tool_impl_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    failure_code: str | None = None


class AgentRuntimeOverviewView(BaseModel):
    generated_at: datetime
    roles: list[AgentRoleRuntimeView] = Field(default_factory=list)
    recent_tasks: list[AgentTaskSummaryView] = Field(default_factory=list)
    recent_capabilities: list[AgentCapabilityActivityView] = Field(default_factory=list)


class AgentTaskDetailView(BaseModel):
    task: AgentTaskSummaryView
    events: list[AgentTaskEventView] = Field(default_factory=list)
    capabilities: list[AgentCapabilityActivityView] = Field(default_factory=list)
