from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


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
    required_conflicts: list[str] = Field(default_factory=list)
    required_citation_facts: list[str] = Field(default_factory=list)
    completion_expectation: str

    @model_validator(mode="after")
    def validate_gold(self) -> QAGold:
        required = set(self.required_facts)
        forbidden = set(self.forbidden_facts)
        if required & forbidden:
            raise ValueError("QA gold fact cannot be both required and forbidden")
        if not set(self.required_citation_facts) <= required | set(self.acceptable_answer_facts):
            raise ValueError("required citation facts must be answer facts")
        return self


class QAPrediction(BaseModel):
    case_id: str
    conclusion_facts: list[str] = Field(default_factory=list)
    relation_paths: list[list[str]] = Field(default_factory=list)
    citations: list[QACitationCheck] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    completion_status: str
    interactive_latency_seconds: float | None = Field(default=None, ge=0)
    execution_refs: list[str] = Field(default_factory=list)


class QAScore(BaseModel):
    answer_accuracy: float = Field(ge=0, le=1)
    groundedness: float = Field(ge=0, le=1)
    citation_correctness: float = Field(ge=0, le=1)
    citation_completeness: float = Field(ge=0, le=1)
    multi_hop_correctness: float | None = Field(default=None, ge=0, le=1)
    unknown_correctness: float = Field(ge=0, le=1)
    conflict_handling: float = Field(ge=0, le=1)
    completion_correctness: float = Field(ge=0, le=1)
    interactive_latency_seconds: float | None = Field(default=None, ge=0)


def score_qa(*, gold: QAGold, prediction: QAPrediction) -> QAScore:
    if gold.case_id != prediction.case_id:
        raise ValueError("QA prediction case_id does not match gold")
    predicted = set(prediction.conclusion_facts)
    required = set(gold.required_facts)
    acceptable = set(gold.acceptable_answer_facts)
    forbidden = set(gold.forbidden_facts)
    answer_correct = required <= predicted and not (predicted & forbidden)
    if acceptable:
        answer_correct = answer_correct and bool(predicted & acceptable or required)

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
