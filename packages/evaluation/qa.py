from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QAEvaluatorRevision = Literal["qa-v1", "qa-v2", "qa-session-v1", "qa-session-v2"]


def qa_evaluator_version(revision: str) -> int:
    if revision in {"qa-v1", "qa-session-v1"}:
        return 1
    if revision in {"qa-v2", "qa-session-v2"}:
        return 2
    raise ValueError(f"unsupported QA evaluator revision: {revision}")


class QACitationCheck(BaseModel):
    conclusion_fact: str
    evidence_ref: str
    supports: bool


class QAGold(BaseModel):
    case_id: str
    required_facts: list[str] = Field(default_factory=list)
    acceptable_answer_facts: list[str] = Field(default_factory=list)
    forbidden_facts: list[str] = Field(default_factory=list)
    required_relation_paths: list[list[str]] = Field(default_factory=list)
    acceptable_unknowns: list[str] = Field(default_factory=list)
    required_unknowns: list[str] = Field(default_factory=list)
    required_conflicts: list[str] = Field(default_factory=list)
    required_citation_facts: list[str] = Field(default_factory=list)
    allowed_assumptions: list[str] = Field(default_factory=list)
    completion_expectation: str

    @model_validator(mode="after")
    def validate_gold(self) -> QAGold:
        required = set(self.required_facts)
        forbidden = set(self.forbidden_facts)
        if required & forbidden:
            raise ValueError("QA gold fact cannot be both required and forbidden")
        if not set(self.required_citation_facts) <= required | set(self.acceptable_answer_facts):
            raise ValueError("required citation facts must be answer facts")
        if not set(self.required_unknowns) <= set(self.acceptable_unknowns):
            raise ValueError("required unknowns must be acceptable unknowns")
        if set(self.required_unknowns) & required:
            raise ValueError("required unknowns cannot also be required facts")
        return self


class QAPrediction(BaseModel):
    case_id: str
    conclusion_facts: list[str] = Field(default_factory=list)
    relation_paths: list[list[str]] = Field(default_factory=list)
    available_relation_paths: list[list[str]] = Field(default_factory=list)
    decision_relation_paths: list[list[str]] = Field(default_factory=list)
    citations: list[QACitationCheck] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    completion_status: str
    interactive_latency_seconds: float | None = Field(default=None, ge=0)
    execution_refs: list[str] = Field(default_factory=list)


class QAScore(BaseModel):
    # Legacy hand-built scores retain their historical recording contract.
    evaluator_revision: QAEvaluatorRevision = "qa-v1"
    task_correctness: float | None = Field(default=None, ge=0, le=1)
    answer_accuracy: float = Field(ge=0, le=1)
    groundedness: float = Field(ge=0, le=1)
    citation_correctness: float = Field(ge=0, le=1)
    citation_completeness: float = Field(ge=0, le=1)
    multi_hop_correctness: float | None = Field(default=None, ge=0, le=1)
    unknown_correctness: float | None = Field(ge=0, le=1)
    conflict_handling: float | None = Field(ge=0, le=1)
    completion_correctness: float = Field(ge=0, le=1)
    interactive_latency_seconds: float | None = Field(default=None, ge=0)


def score_qa(
    *, gold: QAGold, prediction: QAPrediction, evaluator_revision: str = "qa-v2"
) -> QAScore:
    version = qa_evaluator_version(evaluator_revision)
    score = _score_qa_v1(gold=gold, prediction=prediction)
    if version == 1:
        return score.model_copy(update={"evaluator_revision": evaluator_revision})

    predicted = set(prediction.conclusion_facts)
    required = set(gold.required_facts)
    supporting = {
        citation.conclusion_fact
        for citation in prediction.citations
        if citation.supports
        and citation.evidence_ref.strip()
        and citation.conclusion_fact in predicted
    }
    # Canonical answer membership remains a diagnostic; extra assertions must be supported.
    extra_facts = predicted - required - set(gold.acceptable_answer_facts)
    answer_correct = bool(score.answer_accuracy) and extra_facts <= supporting
    unknowns = set(prediction.unknowns)
    unknown_correct = (
        float(set(gold.required_unknowns) <= unknowns <= set(gold.acceptable_unknowns))
        if gold.acceptable_unknowns or gold.required_unknowns or unknowns
        else None
    )
    conflict_correct = (
        float(set(gold.required_conflicts) == set(prediction.conflicts))
        if gold.required_conflicts or prediction.conflicts
        else None
    )
    groundedness = _ratio(len(predicted & supporting), len(predicted))
    citation_correctness = _ratio(
        sum(
            citation.supports
            and bool(citation.evidence_ref.strip())
            and citation.conclusion_fact in predicted
            for citation in prediction.citations
        ),
        len(prediction.citations),
    )
    required_citations = set(gold.required_citation_facts)
    citation_completeness = _ratio(len(required_citations & supporting), len(required_citations))
    completion_correctness = float(
        prediction.completion_status in {"answered", "continuation_requested"}
        and prediction.completion_status == gold.completion_expectation
    )
    answer_task_correct = (
        answer_correct
        and groundedness == 1
        and citation_correctness == 1
        and citation_completeness == 1
        and completion_correctness == 1
        and unknown_correct != 0
        and conflict_correct != 0
        and not (predicted & unknowns)
    )
    expected_paths = {tuple(path) for path in gold.required_relation_paths}
    used_paths = {tuple(path) for path in prediction.decision_relation_paths}
    multi_hop = (
        float(answer_task_correct and bool(supporting) and expected_paths <= used_paths)
        if expected_paths
        else None
    )
    return score.model_copy(
        update={
            "evaluator_revision": evaluator_revision,
            "answer_accuracy": float(answer_correct),
            "task_correctness": float(answer_task_correct and multi_hop != 0),
            "groundedness": groundedness,
            "citation_correctness": citation_correctness,
            "citation_completeness": citation_completeness,
            "multi_hop_correctness": multi_hop,
            "unknown_correctness": unknown_correct,
            "conflict_handling": conflict_correct,
            "completion_correctness": completion_correctness,
        }
    )


def _score_qa_v1(*, gold: QAGold, prediction: QAPrediction) -> QAScore:
    if gold.case_id != prediction.case_id:
        raise ValueError("QA prediction case_id does not match gold")
    predicted = set(prediction.conclusion_facts)
    required = set(gold.required_facts)
    acceptable = set(gold.acceptable_answer_facts)
    forbidden = set(gold.forbidden_facts)
    answer_correct = required <= predicted and not (predicted & forbidden)
    if acceptable:
        answer_correct = answer_correct and bool(predicted & acceptable or required)
    answer_correct = answer_correct and set(prediction.assumptions) <= set(gold.allowed_assumptions)

    supporting_facts = {item.conclusion_fact for item in prediction.citations if item.supports}
    factual_conclusions = predicted - set(prediction.unknowns)
    groundedness = _ratio(len(factual_conclusions & supporting_facts), len(factual_conclusions))
    citation_correctness = _ratio(
        sum(item.supports for item in prediction.citations),
        len(prediction.citations),
    )
    required_citation = set(gold.required_citation_facts)
    citation_completeness = _ratio(
        len(required_citation & supporting_facts),
        len(required_citation),
    )

    expected_paths = {tuple(item) for item in gold.required_relation_paths}
    predicted_paths = {tuple(item) for item in prediction.relation_paths}
    multi_hop = (
        _ratio(len(expected_paths & predicted_paths), len(expected_paths))
        if expected_paths
        else None
    )
    unknown_correctness = float(set(prediction.unknowns) <= set(gold.acceptable_unknowns))
    conflict_handling = float(set(gold.required_conflicts) <= set(prediction.conflicts))
    completion_correctness = float(prediction.completion_status == gold.completion_expectation)
    return QAScore(
        answer_accuracy=float(answer_correct),
        groundedness=groundedness,
        citation_correctness=citation_correctness,
        citation_completeness=citation_completeness,
        multi_hop_correctness=multi_hop,
        unknown_correctness=unknown_correctness,
        conflict_handling=conflict_handling,
        completion_correctness=completion_correctness,
        interactive_latency_seconds=prediction.interactive_latency_seconds,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


class QAAdjudicationRecord(BaseModel):
    adjudication_id: str
    item_ref: str
    annotator_ref: str
    annotation: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime
    supersedes: str | None = None
    final: bool = False

    @model_validator(mode="after")
    def validate_record(self) -> QAAdjudicationRecord:
        if not self.adjudication_id.strip():
            raise ValueError("QA adjudication_id cannot be empty")
        if not self.item_ref.strip() or not self.annotator_ref.strip():
            raise ValueError("QA adjudication item_ref/annotator_ref cannot be empty")
        if not self.annotation.strip():
            raise ValueError("QA adjudication annotation cannot be empty")
        if self.final and not self.evidence_refs:
            raise ValueError("final QA adjudication requires evidence_refs")
        if self.supersedes == self.adjudication_id:
            raise ValueError("QA adjudication cannot supersede itself")
        return self


def validate_qa_adjudication_history(records: list[QAAdjudicationRecord]) -> None:
    by_id = {record.adjudication_id: record for record in records}
    if len(by_id) != len(records):
        raise ValueError("QA adjudication ids must be unique")
    superseded = {record.supersedes for record in records if record.supersedes is not None}
    for record in records:
        if record.supersedes is not None:
            previous = by_id.get(record.supersedes)
            if previous is None:
                raise ValueError("QA adjudication supersedes unknown record")
            if previous.item_ref != record.item_ref:
                raise ValueError("QA adjudication cannot supersede a different item")
            if previous.created_at > record.created_at:
                raise ValueError("QA adjudication cannot supersede a future record")
    for item_ref in {record.item_ref for record in records}:
        terminal = [
            record
            for record in records
            if record.item_ref == item_ref and record.adjudication_id not in superseded
        ]
        if len(terminal) != 1:
            raise ValueError(f"QA adjudication item requires one terminal record: {item_ref}")
        if not terminal[0].final:
            raise ValueError(f"QA adjudication terminal record must be final: {item_ref}")
