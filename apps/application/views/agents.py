from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, JsonValue


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
    predecessor_run_id: str | None = None
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


class AgentTaskPageView(BaseModel):
    generated_at: datetime
    items: list[AgentTaskSummaryView] = Field(default_factory=list)


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


class AgentModelRuntimeView(BaseModel):
    scope: str
    request_limit: int
    request_count: int = 0
    attempt_count: int = 0
    retry_attempt_count: int = 0
    retry_scheduled_count: int = 0
    failed_attempt_count: int = 0
    unknown_after_dispatch_count: int = 0
    p95_latency_ms: int | None = None
    provider_counts: dict[str, int] = Field(default_factory=dict)
    model_counts: dict[str, int] = Field(default_factory=dict)
    latest_attempt_at: datetime | None = None


class AgentControlRuntimeView(BaseModel):
    scope: str
    sampled_task_count: int = 0
    dependency_wake_count: int = 0
    waiting_event_count: int = 0
    stop_reason_counts: dict[str, int] = Field(default_factory=dict)
    wake_latency_ms: int | None = None
    wake_latency_measurement: str = "unavailable"


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
    fragments: list[dict[str, JsonValue]] = Field(default_factory=list)
    created_at: datetime


class AgentModelAttemptView(BaseModel):
    model_request_id: str
    model_attempt_id: str
    purpose: str
    prompt_revision: str
    requested_model: str
    actual_model: str
    status: str
    ordinal: int
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    started_at: datetime


class AgentContextManifestView(BaseModel):
    context_id: str
    context_revision: int
    parent_context_id: str | None = None
    role_ref: str
    case_ref: str | None = None
    knowledge_revision: int | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)
    retrieval_invocation_refs: list[str] = Field(default_factory=list)
    policy_context_ref: str
    capability_envelope_ref: str
    budget_ref: str


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
    model_runtime: AgentModelRuntimeView
    control_runtime: AgentControlRuntimeView


class AgentTaskDetailView(BaseModel):
    task: AgentTaskSummaryView
    parent: AgentTaskSummaryView | None = None
    predecessor: AgentTaskSummaryView | None = None
    children: list[AgentTaskSummaryView] = Field(default_factory=list)
    events: list[AgentTaskEventView] = Field(default_factory=list)
    capabilities: list[AgentCapabilityActivityView] = Field(default_factory=list)
    budget: AgentBudgetSnapshotView | None = None
    prompt_assemblies: list[AgentPromptAssemblyView] = Field(default_factory=list)
    model_attempts: list[AgentModelAttemptView] = Field(default_factory=list)
    context: AgentContextManifestView | None = None


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


class AgentControlledProofCaseView(BaseModel):
    case_id: str
    subsystem: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)
    task_run_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    capability_invocation_ids: list[str] = Field(default_factory=list)


class AgentControlledProofView(BaseModel):
    schema_version: str
    benchmark_run_id: str
    deployment_revision_id: str
    suite_ref: str
    execution_mode: str
    scope: str
    cases: list[AgentControlledProofCaseView] = Field(default_factory=list)
