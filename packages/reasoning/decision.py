from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import InvestigationState
from packages.reasoning.citation import CitationBinder, CitationSource, DecisionCitation


class ConclusionType(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"


class DecisionConclusion(BaseModel):
    statement: str
    type: ConclusionType
    evidence_refs: list[str] = Field(default_factory=list)
    reasoning_relation_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_conclusion(self) -> DecisionConclusion:
        if not self.statement.strip():
            raise ValueError("DecisionConclusion statement cannot be empty")
        if self.type is ConclusionType.FACT and not self.evidence_refs:
            raise ValueError("fact conclusion requires evidence_refs")
        if self.type is ConclusionType.INFERENCE and not (
            self.evidence_refs or self.reasoning_relation_refs
        ):
            raise ValueError("inference conclusion requires evidence or reasoning relation refs")
        return self


class DecisionReportParagraph(BaseModel):
    text: str = Field(min_length=1, max_length=2400)
    evidence_refs: list[str] = Field(default_factory=list)


class DecisionDraft(BaseModel):
    case_id: str
    case_revision: int = Field(ge=0)
    conclusions: list[DecisionConclusion] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    answer_payload: dict[str, JsonValue] = Field(default_factory=dict)
    report_paragraphs: list[DecisionReportParagraph] = Field(default_factory=list)
    stop_reason: str = Field(min_length=1, max_length=128)
    model_prompt_revision: str

    @model_validator(mode="after")
    def validate_draft(self) -> DecisionDraft:
        if not self.case_id.strip():
            raise ValueError("DecisionDraft case_id cannot be empty")
        if not self.stop_reason.strip() or not self.model_prompt_revision.strip():
            raise ValueError("DecisionDraft stop_reason/model_prompt_revision cannot be empty")
        return self


class DecisionResult(BaseModel):
    decision_id: str
    case_id: str
    case_revision: int = Field(ge=0)
    conclusions: list[DecisionConclusion] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    citations: list[DecisionCitation] = Field(default_factory=list)
    answer_payload: dict[str, JsonValue] = Field(default_factory=dict)
    report_paragraphs: list[DecisionReportParagraph] = Field(default_factory=list)
    stop_reason: str = Field(min_length=1, max_length=128)
    model_prompt_revision: str


class DecisionOutcome(BaseModel):
    result: DecisionResult | None = None
    continuation: ContinuationRequest | None = None

    @model_validator(mode="after")
    def exactly_one_outcome(self) -> DecisionOutcome:
        if (self.result is None) == (self.continuation is None):
            raise ValueError("DecisionOutcome requires exactly one result or continuation")
        return self


class DecisionService:
    """M6 validation/finalization over an already-materialized M4 state."""

    def __init__(self, citation_binder: CitationBinder | None = None) -> None:
        self._citations = citation_binder or CitationBinder()

    def decide(
        self,
        state: InvestigationState,
        draft: DecisionDraft,
        *,
        citation_sources: list[CitationSource],
    ) -> DecisionResult:
        self._require_state_identity(state, draft.case_id, draft.case_revision)
        confirmed_evidence = {
            evidence_ref for item in state.confirmed for evidence_ref in item.evidence_refs
        }
        state_evidence = {
            evidence_ref
            for bucket in (
                state.confirmed,
                state.tentative,
                state.conflicts,
                state.unknowns,
                state.hypotheses,
            )
            for item in bucket
            for evidence_ref in item.evidence_refs
        }
        for conclusion in draft.conclusions:
            refs = set(conclusion.evidence_refs)
            if conclusion.type is ConclusionType.FACT:
                if not refs <= confirmed_evidence:
                    raise ValueError("fact conclusion cites evidence outside confirmed M4 state")
                if not any(
                    item.proposition == conclusion.statement
                    and refs <= set(item.evidence_refs)
                    for item in state.confirmed
                ):
                    raise ValueError(
                        "fact conclusion must reproduce one confirmed M4 proposition "
                        "with its supporting evidence"
                    )
            if conclusion.type is ConclusionType.INFERENCE and not refs <= state_evidence:
                raise ValueError("inference conclusion cites evidence outside M4 state")

        cited_refs = {
            ref for conclusion in draft.conclusions for ref in conclusion.evidence_refs
        }
        for paragraph in draft.report_paragraphs:
            if not set(paragraph.evidence_refs) <= cited_refs:
                raise ValueError("report paragraph cites evidence outside decision conclusions")

        citations = self._citations.bind(
            [item.evidence_refs for item in draft.conclusions],
            citation_sources,
        )
        payload = draft.model_dump(mode="json")
        if not draft.report_paragraphs:
            payload.pop("report_paragraphs", None)
        decision_id = _decision_id(payload)
        return DecisionResult(
            decision_id=decision_id,
            case_id=draft.case_id,
            case_revision=draft.case_revision,
            conclusions=draft.conclusions,
            conflicts=draft.conflicts,
            unknowns=draft.unknowns,
            assumptions=draft.assumptions,
            citations=citations,
            answer_payload=draft.answer_payload,
            report_paragraphs=draft.report_paragraphs,
            stop_reason=draft.stop_reason,
            model_prompt_revision=draft.model_prompt_revision,
        )

    def request_continuation(
        self,
        state: InvestigationState,
        request: ContinuationRequest,
    ) -> ContinuationRequest:
        self._require_state_identity(state, request.case_id, request.base_case_revision)
        if not set(request.target_objects) <= set(state.targets):
            raise ValueError("ContinuationRequest target_objects escape M4 state")
        return request

    @staticmethod
    def _require_state_identity(
        state: InvestigationState,
        case_id: str,
        case_revision: int,
    ) -> None:
        if case_id != state.case_id:
            raise ValueError("Decision input case_id does not match M4 state")
        if case_revision != state.case_revision:
            raise ValueError("Decision input is stale against M4 state revision")


def _decision_id(payload: dict[str, object]) -> str:
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return f"decision:{digest[:32]}"
