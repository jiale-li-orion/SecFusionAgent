from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.evaluation.qa import (
    QAAdjudicationRecord,
    QAGold,
    QAPrediction,
    score_qa,
    validate_qa_adjudication_history,
)


def test_qa_score_rejects_unapproved_assumption() -> None:
    gold = QAGold(
        case_id="qa-assumption",
        required_facts=["affected:true"],
        allowed_assumptions=["deployment-version:1.2.3"],
        completion_expectation="answered",
    )
    prediction = QAPrediction(
        case_id="qa-assumption",
        conclusion_facts=["affected:true"],
        assumptions=["deployment-version:unknown"],
        completion_status="answered",
    )
    assert score_qa(gold=gold, prediction=prediction).answer_accuracy == 0.0


def test_qa_adjudication_history_requires_one_final_terminal_record() -> None:
    created = datetime(2026, 9, 28, tzinfo=UTC)
    draft = QAAdjudicationRecord(
        adjudication_id="adj-1",
        item_ref="qa-1:fact:affected",
        annotator_ref="human:reviewer-1",
        annotation="Needs vendor confirmation.",
        created_at=created,
    )
    final = QAAdjudicationRecord(
        adjudication_id="adj-2",
        item_ref="qa-1:fact:affected",
        annotator_ref="human:reviewer-2",
        annotation="Confirmed by the frozen vendor advisory.",
        evidence_refs=["evidence:vendor-advisory"],
        created_at=created + timedelta(minutes=5),
        supersedes="adj-1",
        final=True,
    )
    validate_qa_adjudication_history([draft, final])


def test_qa_adjudication_history_rejects_unresolved_terminal_record() -> None:
    record = QAAdjudicationRecord(
        adjudication_id="adj-open",
        item_ref="qa-1:fact:affected",
        annotator_ref="human:reviewer-1",
        annotation="Still under review.",
        created_at=datetime(2026, 9, 28, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="terminal record must be final"):
        validate_qa_adjudication_history([record])
