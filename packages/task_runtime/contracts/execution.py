from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.task_runtime.contracts.models import ExecutionProfile


class ExecutionEnvelope(BaseModel):
    execution_id: str
    parent_execution_id: str | None = None
    task_contract_id: str
    task_run_id: str
    case_id: str | None = None
    role_revision: str
    context_manifest_revision: int = Field(ge=1)
    execution_profile: ExecutionProfile
    capability_scope: list[str] = Field(default_factory=list)
    deadline_at: datetime
    budget_ref: str
    policy_revision: str
    identity_scope: list[str] = Field(default_factory=list)
    network_policy: str
    side_effect_policy: str
    sandbox_profile_revision: str
    trace_context: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_envelope(self) -> ExecutionEnvelope:
        if self.deadline_at.tzinfo is None:
            raise ValueError("ExecutionEnvelope deadline_at must be timezone-aware")
        for value, label in (
            (self.execution_id, "execution_id"),
            (self.task_contract_id, "task_contract_id"),
            (self.task_run_id, "task_run_id"),
            (self.role_revision, "role_revision"),
            (self.budget_ref, "budget_ref"),
            (self.policy_revision, "policy_revision"),
            (self.network_policy, "network_policy"),
            (self.side_effect_policy, "side_effect_policy"),
            (self.sandbox_profile_revision, "sandbox_profile_revision"),
        ):
            if not value.strip():
                raise ValueError(f"ExecutionEnvelope {label} cannot be empty")
        return self


def validate_child_execution_envelope(
    parent: ExecutionEnvelope,
    child: ExecutionEnvelope,
) -> list[str]:
    errors: list[str] = []
    if child.parent_execution_id != parent.execution_id:
        errors.append("parent_execution_mismatch")
    if child.deadline_at > parent.deadline_at:
        errors.append("child_deadline_exceeds_parent")
    if not set(child.capability_scope) <= set(parent.capability_scope):
        errors.append("child_capability_scope_exceeds_parent")
    if not set(child.identity_scope) <= set(parent.identity_scope):
        errors.append("child_identity_scope_exceeds_parent")
    return errors


def bounded_timeout_seconds(
    envelope: ExecutionEnvelope,
    *,
    now: datetime,
    action_timeout_seconds: float,
) -> float:
    if now.tzinfo is None:
        raise ValueError("bounded timeout requires timezone-aware now")
    remaining = (envelope.deadline_at - now).total_seconds()
    if remaining <= 0:
        return 0.0
    return min(action_timeout_seconds, remaining)
