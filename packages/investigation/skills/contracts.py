from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue, model_validator


class SkillStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DEPRECATED = "deprecated"


class SkillSourceType(StrEnum):
    SEEDED = "seeded"
    EXPERIENCE_DERIVED = "experience_derived"
    IMPORTED = "imported"


class SkillDisclosureLevel(StrEnum):
    MANIFEST = "manifest"
    PROCEDURE = "procedure"
    STEP = "step"
    PROVENANCE = "provenance"


class SkillManifest(BaseModel):
    skill_id: str
    version: int = Field(ge=1)
    status: SkillStatus
    source_type: SkillSourceType
    task_patterns: list[str] = Field(default_factory=list)
    evidence_need_patterns: list[str] = Field(default_factory=list)
    applicable_object_types: list[str] = Field(default_factory=list)
    applicability_conditions: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    required_capability_classes: list[str] = Field(default_factory=list)
    optional_capability_classes: list[str] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    risk_hint: str | None = None
    cost_hint: str | None = None
    procedure_ref: str
    provenance_ref: str
    validation_ref: str | None = None
    supersedes: str | None = None

    @model_validator(mode="after")
    def validate_manifest(self) -> SkillManifest:
        if not self.skill_id.strip() or "." not in self.skill_id:
            raise ValueError("SkillManifest skill_id must be namespaced")
        if not self.procedure_ref.strip() or not self.provenance_ref.strip():
            raise ValueError("SkillManifest procedure/provenance refs cannot be empty")
        if not self.task_patterns:
            raise ValueError("SkillManifest requires task_patterns")
        return self

    @property
    def namespace(self) -> str:
        return self.skill_id.split(".", 1)[0]

    @property
    def ref(self) -> str:
        return f"skill:{self.skill_id}@{self.version}"


class SkillStepFragment(BaseModel):
    skill_id: str
    version: int = Field(ge=1)
    step_id: str
    semantic_instruction: str
    required_state_refs: list[str] = Field(default_factory=list)
    required_capability_classes: list[str] = Field(default_factory=list)
    success_predicate: str
    failure_predicate: str
    fallback_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_step(self) -> SkillStepFragment:
        if not self.step_id.strip() or not self.semantic_instruction.strip():
            raise ValueError("SkillStepFragment step_id/instruction cannot be empty")
        return self


class SkillProcedure(BaseModel):
    skill_id: str
    version: int = Field(ge=1)
    steps: list[SkillStepFragment]
    evidence_expectations: list[str] = Field(default_factory=list)
    failure_guards: list[str] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    budget_profile: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_procedure(self) -> SkillProcedure:
        if not self.steps:
            raise ValueError("SkillProcedure requires steps")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("SkillProcedure step_id values must be unique")
        for step in self.steps:
            if step.skill_id != self.skill_id or step.version != self.version:
                raise ValueError("SkillProcedure step identity mismatch")
        return self


class SkillProvenance(BaseModel):
    skill_id: str
    version: int = Field(ge=1)
    origin: str
    supporting_trajectory_refs: list[str] = Field(default_factory=list)
    supporting_experience_pattern_refs: list[str] = Field(default_factory=list)
    validation_case_refs: list[str] = Field(default_factory=list)
    promotion_history: list[str] = Field(default_factory=list)


class SkillVersion(BaseModel):
    manifest: SkillManifest
    procedure: SkillProcedure
    provenance: SkillProvenance

    @model_validator(mode="after")
    def validate_identity(self) -> SkillVersion:
        identity = (self.manifest.skill_id, self.manifest.version)
        if identity != (self.procedure.skill_id, self.procedure.version):
            raise ValueError("SkillVersion procedure identity mismatch")
        if identity != (self.provenance.skill_id, self.provenance.version):
            raise ValueError("SkillVersion provenance identity mismatch")
        return self


class SkillSelection(BaseModel):
    selection_id: str
    task_run_id: str
    candidate_skill_refs: list[str] = Field(default_factory=list)
    selected_skill_ref: str | None = None
    disclosure_level: SkillDisclosureLevel = SkillDisclosureLevel.MANIFEST
    selection_reason: str
    state_signature: str
    capability_view_revision: str

    @model_validator(mode="after")
    def validate_selection(self) -> SkillSelection:
        if not self.selection_id.strip() or not self.task_run_id.strip():
            raise ValueError("SkillSelection identity cannot be empty")
        if not self.selection_reason.strip() or not self.state_signature.strip():
            raise ValueError("SkillSelection reason/state_signature cannot be empty")
        if not self.capability_view_revision.strip():
            raise ValueError("SkillSelection capability_view_revision cannot be empty")
        if self.selected_skill_ref is not None:
            if self.selected_skill_ref not in self.candidate_skill_refs:
                raise ValueError("selected Skill must be present in candidate_skill_refs")
        return self
