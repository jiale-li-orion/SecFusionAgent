from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ChildContextSpec(BaseModel):
    context_id: str
    policy_context_ref: str
    capability_envelope_ref: str
    budget_ref: str
    include_case: bool = False
    include_investigation_state: bool = False
    include_trajectory_checkpoint: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)
    enrichment_state_refs: list[str] = Field(default_factory=list)
    skill_selection_refs: list[str] = Field(default_factory=list)
    experience_pattern_refs: list[str] = Field(default_factory=list)
    cache_hint: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> ChildContextSpec:
        for value, label in (
            (self.context_id, "context_id"),
            (self.policy_context_ref, "policy_context_ref"),
            (self.capability_envelope_ref, "capability_envelope_ref"),
            (self.budget_ref, "budget_ref"),
        ):
            if not value.strip():
                raise ValueError(f"ChildContextSpec {label} cannot be empty")
        return self


class ContextRefresh(BaseModel):
    context_revision: int = Field(ge=2)
    knowledge_revision: int | None = Field(default=None, ge=0)
    investigation_state_ref: str | None = None
    add_evidence_refs: list[str] = Field(default_factory=list)
    add_object_refs: list[str] = Field(default_factory=list)
    add_relation_refs: list[str] = Field(default_factory=list)
    add_enrichment_state_refs: list[str] = Field(default_factory=list)
    add_skill_selection_refs: list[str] = Field(default_factory=list)
    add_experience_pattern_refs: list[str] = Field(default_factory=list)
    cache_hint: str | None = None


class ContextScalarChange(BaseModel):
    field: str
    before: str | int | None
    after: str | int | None


class ContextDelta(BaseModel):
    base_ref: str
    current_ref: str
    scalar_changes: list[ContextScalarChange] = Field(default_factory=list)
    added_refs: dict[str, list[str]] = Field(default_factory=dict)
    removed_refs: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.scalar_changes and not self.added_refs and not self.removed_refs


class ContextDependencySet(BaseModel):
    knowledge_revision: bool = True
    investigation_state_ref: bool = True
    trajectory_checkpoint_ref: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)
    enrichment_state_refs: list[str] = Field(default_factory=list)
    skill_selection_refs: list[str] = Field(default_factory=list)
    experience_pattern_refs: list[str] = Field(default_factory=list)


class ContextResultProvenance(BaseModel):
    based_on_context_id: str
    based_on_context_revision: int = Field(ge=1)
    dependencies: ContextDependencySet = Field(default_factory=ContextDependencySet)


class ContextCompatibilityStatus(StrEnum):
    VALID = "valid"
    REBASE_REQUIRED = "rebase_required"
    STALE = "stale"
    CONFLICT = "conflict"


class ContextCompatibility(BaseModel):
    status: ContextCompatibilityStatus
    reasons: list[str] = Field(default_factory=list)
    delta: ContextDelta
