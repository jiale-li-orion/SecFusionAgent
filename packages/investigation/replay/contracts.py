from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from packages.investigation.state.contracts import InvestigationState


class ReplayRuntimeBinding(BaseModel):
    task_run_id: str
    execution_envelope_ref: str
    execution_profile: str
    policy_revision: str
    capability_scope: list[str] = Field(default_factory=list)
    identity_scope: list[str] = Field(default_factory=list)
    network_policy: str
    side_effect_policy: str
    sandbox_profile_revision: str
    budget_ref: str
    budget_limits: dict[str, str] = Field(default_factory=dict)
    budget_reserved: dict[str, str] = Field(default_factory=dict)
    budget_committed: dict[str, str] = Field(default_factory=dict)


class ReplayLoopTopology(StrEnum):
    SINGLE_LOOP = "single_loop"
    MULTI_LOOP_DELEGATED = "multi_loop_delegated"


class ReplayCheckpoint(BaseModel):
    checkpoint_id: str
    case_id: str
    snapshot_id: str
    case_revision: int = Field(ge=0)
    knowledge_revision: int | None = Field(default=None, ge=0)
    task_run_id: str
    task_contract_ref: str
    context_manifest_ref: str
    task_event_seq: int = Field(ge=1)
    trajectory_id: str
    trajectory_ordinal: int = Field(ge=0)
    role_ref: str
    runtime: ReplayRuntimeBinding
    capability_registry_revision: str | None = None
    model_revision: str | None = None
    prompt_assembly_revision: str | None = None
    skill_refs: list[str] = Field(default_factory=list)
    source_availability_snapshot: dict[str, object] = Field(default_factory=dict)
    loop_topology: ReplayLoopTopology
    context_handoff_mode: str = "reference"
    created_at: datetime

    @model_validator(mode="after")
    def validate_checkpoint(self) -> ReplayCheckpoint:
        if self.runtime.task_run_id != self.task_run_id:
            raise ValueError("Replay runtime binding task_run_id mismatch")
        if not self.runtime.execution_envelope_ref.strip():
            raise ValueError("Replay checkpoint requires execution envelope ref")
        if self.context_handoff_mode not in {"reference", "summary"}:
            raise ValueError("unsupported context handoff mode")
        return self


class ReplayCheckpointCapture(BaseModel):
    checkpoint: ReplayCheckpoint
    trajectory_event_id: str
    replay: bool = False


class ReplayInterventionKind(StrEnum):
    LOOP_TOPOLOGY = "loop_topology"
    CONTEXT_HANDOFF = "context_handoff"
    POLICY = "policy"
    SANDBOX = "sandbox"
    SKILL = "skill"
    CAPABILITY_REGISTRY = "capability_registry"


class ReplayIntervention(BaseModel):
    kind: ReplayInterventionKind
    replacement: str
    rationale: str

    @model_validator(mode="after")
    def validate_intervention(self) -> ReplayIntervention:
        if not self.replacement.strip() or not self.rationale.strip():
            raise ValueError("Replay intervention replacement/rationale cannot be empty")
        if self.kind is ReplayInterventionKind.CONTEXT_HANDOFF:
            if self.replacement not in {"reference", "summary"}:
                raise ValueError("context handoff intervention must be reference or summary")
        return self


class ReplayEnvironment(BaseModel):
    checkpoint_id: str
    context_manifest_ref: str
    context_handoff_mode: str
    policy_revision: str
    sandbox_profile_revision: str
    capability_registry_revision: str | None = None
    skill_refs: list[str] = Field(default_factory=list)
    budget_limits: dict[str, str] = Field(default_factory=dict)
    loop_topology: ReplayLoopTopology
    intervention: ReplayIntervention | None = None


class ReplayPreparedCoordinate(BaseModel):
    checkpoint: ReplayCheckpoint
    state: InvestigationState
    environment: ReplayEnvironment
    world_revision: int


class ReplayExpectation(BaseModel):
    expected_task_status: str | None = None
    required_event_types: list[str] = Field(default_factory=list)
    forbidden_event_types: list[str] = Field(default_factory=list)
    expected_stop_reason: str | None = None
    require_no_authority_violation: bool = True


class ReplayObservation(BaseModel):
    task_status: str
    event_types: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    authority_violations: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class ReplayProtocolResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)
