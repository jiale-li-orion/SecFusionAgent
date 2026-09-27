from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue, model_validator


def _default_completion_predicate() -> dict[str, JsonValue]:
    return {"type": "state_accepted"}


class CaseLifecycle(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ProposedState(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    HYPOTHESIS = "hypothesis"


class PatchDisposition(StrEnum):
    SET = "set"
    CLEAR = "clear"


class ReasoningSemantics(StrEnum):
    DETERMINISTIC = "deterministic"
    INFERRED = "inferred"


class ReasoningRelation(BaseModel):
    relation_type: str
    semantics: ReasoningSemantics
    source_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relation(self) -> ReasoningRelation:
        if not self.relation_type.strip():
            raise ValueError("reasoning relation_type cannot be empty")
        return self


class StatePatchOperation(BaseModel):
    proposition: str
    target_ref: str | None = None
    proposed_state: ProposedState
    disposition: PatchDisposition = PatchDisposition.SET
    evidence_refs: list[str] = Field(default_factory=list)
    reasoning_relation: ReasoningRelation | None = None
    resolves_need_id: str | None = None

    @model_validator(mode="after")
    def validate_operation(self) -> StatePatchOperation:
        if not self.proposition.strip():
            raise ValueError("state patch proposition cannot be empty")
        if self.proposed_state in {ProposedState.CONFIRMED, ProposedState.CONFLICT}:
            if self.disposition is PatchDisposition.SET and not self.evidence_refs:
                raise ValueError(f"{self.proposed_state.value} state requires evidence_refs")
        return self


class StatePatch(BaseModel):
    patch_id: str
    case_id: str
    base_case_revision: int = Field(ge=0)
    operations: list[StatePatchOperation] = Field(min_length=1)
    producer: str
    model_prompt_revision: str | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> StatePatch:
        if not self.patch_id.strip() or not self.case_id.strip() or not self.producer.strip():
            raise ValueError("StatePatch identity/producer cannot be empty")
        return self


class EvidenceNeedStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


class EvidenceNeedContract(BaseModel):
    require_evidence: bool = True
    required_source_roles: list[str] = Field(default_factory=list)
    min_independent_sources: int = Field(default=1, ge=1)
    accepted_states: list[ProposedState] = Field(
        default_factory=lambda: [
            ProposedState.CONFIRMED,
            ProposedState.CONFLICT,
            ProposedState.UNKNOWN,
        ]
    )


class EvidenceNeed(BaseModel):
    need_id: str
    case_id: str
    derived_from_enrichment_requirement: str | None = None
    proposition_or_question: str
    purpose: str
    target_objects: list[str] = Field(default_factory=list)
    evidence_contract: EvidenceNeedContract = Field(default_factory=EvidenceNeedContract)
    preferred_source_roles: list[str] = Field(default_factory=list)
    rejected_evidence_patterns: list[str] = Field(default_factory=list)
    freshness_requirement: dict[str, JsonValue] = Field(default_factory=dict)
    completion_predicate: dict[str, JsonValue] = Field(
        default_factory=_default_completion_predicate
    )
    priority: int = Field(default=50, ge=0, le=100)
    status: EvidenceNeedStatus = EvidenceNeedStatus.OPEN
    resolution_evidence_refs: list[str] = Field(default_factory=list)
    opened_revision: int = Field(ge=0)
    updated_revision: int = Field(ge=0)
    opened_at: datetime
    updated_at: datetime


class CaseStateEventType(StrEnum):
    FACT_CONFIRMED = "fact_confirmed"
    FACT_RETRACTED = "fact_retracted"
    TENTATIVE_ADDED = "tentative_added"
    TENTATIVE_REMOVED = "tentative_removed"
    CONFLICT_OPENED = "conflict_opened"
    CONFLICT_RESOLVED = "conflict_resolved"
    UNKNOWN_OPENED = "unknown_opened"
    UNKNOWN_RESOLVED = "unknown_resolved"
    HYPOTHESIS_ADDED = "hypothesis_added"
    HYPOTHESIS_REJECTED = "hypothesis_rejected"
    EVIDENCE_NEED_OPENED = "evidence_need_opened"
    EVIDENCE_NEED_RESOLVED = "evidence_need_resolved"
    EVIDENCE_ATTACHED = "evidence_attached"
    DECISION_CHANGED = "decision_changed"
    PERCEPTION_RECORDED = "perception_recorded"


class CaseStateEvent(BaseModel):
    event_id: str
    case_id: str
    case_revision: int = Field(ge=1)
    base_case_revision: int = Field(ge=0)
    event_type: CaseStateEventType
    proposition: str | None = None
    target_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    writer: str
    reason_code: str
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime


class InvestigationStateItem(BaseModel):
    proposition: str
    target_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    writer: str
    reason_code: str
    reasoning_relation: ReasoningRelation | None = None
    updated_revision: int = Field(ge=1)


class InvestigationState(BaseModel):
    case_id: str
    case_revision: int = Field(ge=0)
    goal: str
    targets: list[str] = Field(default_factory=list)
    confirmed: list[InvestigationStateItem] = Field(default_factory=list)
    tentative: list[InvestigationStateItem] = Field(default_factory=list)
    conflicts: list[InvestigationStateItem] = Field(default_factory=list)
    unknowns: list[InvestigationStateItem] = Field(default_factory=list)
    hypotheses: list[InvestigationStateItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    decision_variables: list[str] = Field(default_factory=list)
    evidence_need_ids: list[str] = Field(default_factory=list)
    active_skills: list[str] = Field(default_factory=list)
    normative_context_refs: list[str] = Field(default_factory=list)
    unresolved_applicability: list[str] = Field(default_factory=list)
    current_decision: dict[str, JsonValue] | None = None
    last_world_revision: int | None = Field(default=None, ge=0)
    last_perception_at: datetime | None = None
    updated_at: datetime
