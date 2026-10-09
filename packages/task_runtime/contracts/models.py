from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue, model_validator


class TaskKind(StrEnum):
    LOOKUP = "lookup"
    RETRIEVE = "retrieve"
    VERIFY_VERSION_FIX = "verify_version_fix"
    RESOLVE_CONFLICT = "resolve_conflict"
    INVESTIGATE_RELATION = "investigate_relation"
    INVESTIGATE_INCIDENT = "investigate_incident"
    WATCH_INCIDENT = "watch_incident"
    RESEARCH_INSIGHT = "research_insight"
    ASSESS_NORMATIVE_APPLICABILITY = "assess_normative_applicability"
    OBSERVE_LIVE_ASSET = "observe_live_asset"
    ENRICHMENT = "enrichment"


class ExecutionProfile(StrEnum):
    DIRECT = "DIRECT"
    RETRIEVE = "RETRIEVE"
    VERIFY = "VERIFY"
    INVESTIGATE = "INVESTIGATE"
    WATCH = "WATCH"


class EffectCeiling(StrEnum):
    READ_ONLY = "read_only"
    INTERNAL_STATE = "internal_state"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


_EFFECT_RANK: dict[EffectCeiling, int] = {
    EffectCeiling.READ_ONLY: 0,
    EffectCeiling.INTERNAL_STATE: 1,
    EffectCeiling.EXTERNAL_SIDE_EFFECT: 2,
}


def effect_within_ceiling(effect: EffectCeiling, ceiling: EffectCeiling) -> bool:
    return _EFFECT_RANK[effect] <= _EFFECT_RANK[ceiling]


class DelegationCeiling(BaseModel):
    allowed: bool = False
    max_depth: int = Field(default=0, ge=0)
    allowed_task_kinds: list[TaskKind] = Field(default_factory=list)
    child_effect_ceiling: EffectCeiling = EffectCeiling.READ_ONLY

    @model_validator(mode="after")
    def validate_disabled_shape(self) -> DelegationCeiling:
        if not self.allowed and (
            self.max_depth != 0
            or self.allowed_task_kinds
            or self.child_effect_ceiling != EffectCeiling.READ_ONLY
        ):
            raise ValueError(
                "disabled delegation cannot grant depth, task kinds, or elevated effects"
            )
        if self.allowed and self.max_depth < 1:
            raise ValueError("enabled delegation requires max_depth >= 1")
        return self


class CancellationSemantics(StrEnum):
    CANCELLABLE = "cancellable"
    TERMINAL_ONLY = "terminal_only"
    REQUIRES_RECONCILIATION = "requires_reconciliation"


class TaskIntent(BaseModel):
    raw_request: str | None = None
    trigger_ref: str | None = None
    parsed_identifiers: list[str] = Field(default_factory=list)
    candidate_task_kind: TaskKind | None = None
    candidate_targets: list[str] = Field(default_factory=list)
    temporal_expression: str | None = None
    requested_output: dict[str, JsonValue] = Field(default_factory=dict)
    requested_actions: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_request_or_trigger(self) -> TaskIntent:
        if not self.raw_request and not self.trigger_ref:
            raise ValueError("TaskIntent requires raw_request or trigger_ref")
        return self


class TaskContract(BaseModel):
    task_contract_id: str
    contract_revision: int = Field(ge=1)
    principal: str
    on_behalf_of: str | None = None
    task_kind: TaskKind
    target_resources: list[str] = Field(default_factory=list)
    desired_state: dict[str, JsonValue]
    evidence_contract: dict[str, JsonValue] = Field(default_factory=dict)
    output_contract: dict[str, JsonValue] = Field(default_factory=dict)
    temporal_contract: dict[str, JsonValue] = Field(default_factory=dict)
    effect_ceiling: EffectCeiling
    delegation_ceiling: DelegationCeiling = Field(default_factory=DelegationCeiling)
    completion_predicate: dict[str, JsonValue]
    cancellation_semantics: CancellationSemantics = CancellationSemantics.CANCELLABLE
    policy_revision: str

    @model_validator(mode="after")
    def validate_execution_contract(self) -> TaskContract:
        if not self.principal.strip():
            raise ValueError("TaskContract principal cannot be empty")
        if not self.desired_state:
            raise ValueError("TaskContract desired_state cannot be empty")
        if not self.completion_predicate:
            raise ValueError("TaskContract completion_predicate cannot be empty")
        if not self.policy_revision.strip():
            raise ValueError("TaskContract policy_revision cannot be empty")
        if self.delegation_ceiling.allowed and not effect_within_ceiling(
            self.delegation_ceiling.child_effect_ceiling,
            self.effect_ceiling,
        ):
            raise ValueError("delegated child effect ceiling exceeds parent task effect ceiling")
        return self


class TaskRunStatus(StrEnum):
    SUBMITTED = "submitted"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_DEPENDENCY = "waiting_dependency"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


TERMINAL_TASK_RUN_STATUSES = frozenset(
    {
        TaskRunStatus.BLOCKED,
        TaskRunStatus.COMPLETED,
        TaskRunStatus.FAILED,
        TaskRunStatus.CANCELLED,
        TaskRunStatus.TIMED_OUT,
    }
)

TASK_RUN_TRANSITIONS: dict[TaskRunStatus, frozenset[TaskRunStatus]] = {
    TaskRunStatus.SUBMITTED: frozenset(
        {TaskRunStatus.QUEUED, TaskRunStatus.CANCELLED, TaskRunStatus.BLOCKED}
    ),
    TaskRunStatus.QUEUED: frozenset(
        {
            TaskRunStatus.RUNNING,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.TIMED_OUT,
        }
    ),
    TaskRunStatus.RUNNING: frozenset(
        {
            TaskRunStatus.WAITING_INPUT,
            TaskRunStatus.WAITING_DEPENDENCY,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.COMPLETED,
            TaskRunStatus.FAILED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.TIMED_OUT,
        }
    ),
    TaskRunStatus.WAITING_INPUT: frozenset(
        {
            TaskRunStatus.QUEUED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.TIMED_OUT,
        }
    ),
    TaskRunStatus.WAITING_DEPENDENCY: frozenset(
        {
            TaskRunStatus.QUEUED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.TIMED_OUT,
        }
    ),
    TaskRunStatus.BLOCKED: frozenset(),
    TaskRunStatus.COMPLETED: frozenset(),
    TaskRunStatus.FAILED: frozenset(),
    TaskRunStatus.CANCELLED: frozenset(),
    TaskRunStatus.TIMED_OUT: frozenset(),
}


def can_transition_task_run(current: TaskRunStatus, target: TaskRunStatus) -> bool:
    return target in TASK_RUN_TRANSITIONS[current]


class TaskRun(BaseModel):
    run_id: str
    task_contract_id: str
    case_id: str | None = None
    parent_run_id: str | None = None
    role_id: str
    role_version: str
    context_manifest_ref: str
    status: TaskRunStatus = TaskRunStatus.SUBMITTED
    base_context_revision: int = Field(ge=1)
    execution_envelope_ref: str
    result_ref: str | None = None
    stop_reason: str | None = Field(default=None, max_length=128)


class RoleProfile(BaseModel):
    role_id: str
    version: str
    accepts_task_kinds: list[TaskKind]
    state_model: str
    planner_profile: str
    skill_scope: list[str] = Field(default_factory=list)
    seed_skill_refs: list[str] = Field(default_factory=list)
    mandatory_guard_refs: list[str] = Field(default_factory=list)
    capability_preferences: list[str] = Field(default_factory=list)
    default_execution_profile: ExecutionProfile
    delegation_rules: list[dict[str, JsonValue]] = Field(default_factory=list)

    def accepts(self, task_kind: TaskKind) -> bool:
        return task_kind in self.accepts_task_kinds


class ContextManifest(BaseModel):
    context_id: str
    context_revision: int = Field(ge=1)
    parent_context_id: str | None = None
    task_contract_ref: str
    role_ref: str
    case_ref: str | None = None
    knowledge_revision: int | None = Field(default=None, ge=0)
    investigation_state_ref: str | None = None
    enrichment_state_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)
    retrieval_invocation_refs: list[str] = Field(default_factory=list)
    query_intent: dict[str, JsonValue] | None = None
    query_intent_model_ref: str | None = None
    trajectory_checkpoint_ref: str | None = None
    skill_selection_refs: list[str] = Field(default_factory=list)
    experience_pattern_refs: list[str] = Field(default_factory=list)
    policy_context_ref: str
    capability_envelope_ref: str
    budget_ref: str
    cache_hint: str | None = None


class TaskEventType(StrEnum):
    TASK_CREATED = "TaskCreated"
    TASK_STARTED = "TaskStarted"
    TASK_PATCHED = "TaskPatched"
    CONTEXT_UPDATED = "ContextUpdated"
    EVIDENCE_FOUND = "EvidenceFound"
    KNOWLEDGE_CHANGED = "KnowledgeChanged"
    ENRICHMENT_STATE_CHANGED = "EnrichmentStateChanged"
    INVESTIGATION_STATE_CHANGED = "InvestigationStateChanged"
    TASK_BLOCKED = "TaskBlocked"
    NEED_INPUT = "NeedInput"
    NEED_CONTEXT = "NeedContext"
    BUDGET_WARNING = "BudgetWarning"
    ARTIFACT_PRODUCED = "ArtifactProduced"
    PROGRESS = "Progress"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    TASK_CANCELED = "TaskCanceled"


class TaskEvent(BaseModel):
    event_id: str
    task_run_id: str
    parent_run_id: str | None = None
    seq: int = Field(ge=1)
    event_type: TaskEventType
    producer: str
    base_context_revision: int = Field(ge=1)
    payload_ref: str
    idempotency_key: str
    emitted_at: datetime

    @model_validator(mode="after")
    def validate_non_empty_identity(self) -> TaskEvent:
        for value, label in (
            (self.producer, "producer"),
            (self.payload_ref, "payload_ref"),
            (self.idempotency_key, "idempotency_key"),
        ):
            if not value.strip():
                raise ValueError(f"TaskEvent {label} cannot be empty")
        return self
