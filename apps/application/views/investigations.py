from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue


class InvestigationFindingView(BaseModel):
    proposition: str
    target_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    updated_revision: int


class EvidenceNeedSummaryView(BaseModel):
    need_id: str
    question: str
    purpose: str
    status: str
    priority: int
    required_source_roles: list[str] = Field(default_factory=list)
    updated_revision: int


class InvestigationActivitySummaryView(BaseModel):
    phase: str
    actor_role: str | None = None
    task_kind: str | None = None
    task_status: str | None = None
    updated_at: datetime | None = None


class DecisionConclusionView(BaseModel):
    statement: str
    type: str
    evidence_refs: list[str] = Field(default_factory=list)


class DecisionCitationView(BaseModel):
    conclusion_index: int
    evidence_ref: str
    source_ref: str | None = None
    locator: dict[str, JsonValue] = Field(default_factory=dict)


class DecisionView(BaseModel):
    decision_id: str
    case_revision: int
    conclusions: list[DecisionConclusionView] = Field(default_factory=list)
    citations: list[DecisionCitationView] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    answer: dict[str, JsonValue] = Field(default_factory=dict)
    stop_reason: str
    created_at: datetime


class InvestigationView(BaseModel):
    case_id: str
    revision: int
    status: str
    execution_profile: str | None = None
    target_object_ids: list[str] = Field(default_factory=list)
    goal: str
    confirmed_findings: list[InvestigationFindingView] = Field(default_factory=list)
    conflicts: list[InvestigationFindingView] = Field(default_factory=list)
    unknowns: list[InvestigationFindingView] = Field(default_factory=list)
    open_evidence_needs: list[EvidenceNeedSummaryView] = Field(default_factory=list)
    current_activity: InvestigationActivitySummaryView
    latest_decision: DecisionView | None = None
    terminal_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class InvestigationPage(BaseModel):
    items: list[InvestigationView]
    next_cursor: str | None = None
    has_more: bool = False


class StartInvestigationResult(BaseModel):
    mode: Literal["accepted"] = "accepted"
    investigation: InvestigationView


class ProductRuntimeEventView(BaseModel):
    event_id: str
    event_type: str
    technical_type: str
    source_kind: str
    case_id: str
    task_run_id: str | None = None
    role_id: str | None = None
    status: str | None = None
    actor: str | None = None
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    case_revision: int | None = None
    occurred_at: datetime


class ProductRuntimeActivityView(BaseModel):
    case_id: str
    events: list[ProductRuntimeEventView] = Field(default_factory=list)
