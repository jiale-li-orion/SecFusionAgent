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
    failure_detail: str | None = None
    policy_decision_ref: str | None = None
    canonical_output_ref: str | None = None
    raw_artifact_ref: str | None = None
    effect_receipt_ref: str | None = None
    observation_class: str | None = None


class AgentPromptAssemblyView(BaseModel):
    assembly_id: str
    execution_id: str
    context_manifest_ref: str
    role_revision: str
    execution_profile_revision: str
    materialized_skill_refs: list[str] = Field(default_factory=list)
    materialized_capability_view_refs: list[str] = Field(default_factory=list)
    percept_refs: list[str] = Field(default_factory=list)
    materialized_ref_set_digest: str
    created_at: datetime


class AgentBudgetSnapshotView(BaseModel):
    account_id: str
    limits: dict[str, float] = Field(default_factory=dict)
    reserved: dict[str, float] = Field(default_factory=dict)
    committed: dict[str, float] = Field(default_factory=dict)
    remaining: dict[str, float] = Field(default_factory=dict)


class AgentRuntimeOverviewView(BaseModel):
    generated_at: datetime
    roles: list[AgentRoleRuntimeView] = Field(default_factory=list)
    recent_tasks: list[AgentTaskSummaryView] = Field(default_factory=list)
    recent_capabilities: list[AgentCapabilityActivityView] = Field(default_factory=list)


class AgentTaskDetailView(BaseModel):
    task: AgentTaskSummaryView
    events: list[AgentTaskEventView] = Field(default_factory=list)
    capabilities: list[AgentCapabilityActivityView] = Field(default_factory=list)
    budget: AgentBudgetSnapshotView | None = None
    prompt_assemblies: list[AgentPromptAssemblyView] = Field(default_factory=list)


class ProductSkillView(BaseModel):
    skill_ref: str
    skill_id: str
    version: int
    status: str
    source_type: str
    task_patterns: list[str] = Field(default_factory=list)
    evidence_need_patterns: list[str] = Field(default_factory=list)
    applicable_object_types: list[str] = Field(default_factory=list)
    applicability_conditions: list[str] = Field(default_factory=list)
    required_capability_classes: list[str] = Field(default_factory=list)
    optional_capability_classes: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    risk_hint: str | None = None
    cost_hint: str | None = None
    validation_ref: str | None = None
    supersedes: str | None = None
    steps: list[dict[str, object]] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)
    failure_guards: list[str] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    provenance_origin: str
    supporting_trajectory_refs: list[str] = Field(default_factory=list)
    supporting_experience_pattern_refs: list[str] = Field(default_factory=list)
    validation_case_refs: list[str] = Field(default_factory=list)
    promotion_history: list[str] = Field(default_factory=list)


class ProductExperienceView(BaseModel):
    experience_id: str
    experience_version_id: str
    version: int
    name: str
    task_signature: str
    status: str
    trigger_signals: list[str] = Field(default_factory=list)
    applicable_conditions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_expectation: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    fallback_actions: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    partial_count: int = 0
    support_records: list[ProductExperienceSupportView] = Field(default_factory=list)


class ProductExperienceSupportView(BaseModel):
    trajectory_id: str
    case_id: str
    trajectory_status: str
    trajectory_outcome: str | None = None
    latency_ms: int | None = None
    tool_calls: int = 0
    started_at: datetime
    finished_at: datetime | None = None
    outcome: str
    evaluation: dict[str, object] = Field(default_factory=dict)
    evaluator: str
    created_at: datetime


class AgentLearningOverviewView(BaseModel):
    skills: list[ProductSkillView] = Field(default_factory=list)
    experiences: list[ProductExperienceView] = Field(default_factory=list)
    experience_candidate_count: int = 0
    trajectory_count: int = 0
    completed_trajectory_count: int = 0
