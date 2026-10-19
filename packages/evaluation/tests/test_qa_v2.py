from __future__ import annotations

import pytest

from packages.evaluation.benchmark.metrics import metric_definition
from packages.evaluation.qa import QACitationCheck, QAGold, QAPrediction, score_qa


def _case(**prediction_updates):
    gold = QAGold(
        case_id="strict",
        required_facts=["answer"],
        required_citation_facts=["answer"],
        completion_expectation="answered",
    )
    prediction = QAPrediction(
        case_id="strict",
        conclusion_facts=["answer"],
        citations=[
            QACitationCheck(conclusion_fact="answer", evidence_ref="evidence:answer", supports=True)
        ],
        completion_status="answered",
    )
    return gold, prediction.model_copy(update=prediction_updates)


def test_v2_rejects_unsupported_extra_fact_but_v1_is_reproducible():
    gold, prediction = _case(conclusion_facts=["answer", "fabricated"])
    strict = score_qa(gold=gold, prediction=prediction)
    assert strict.answer_accuracy == 0
    assert strict.task_correctness == 0
    assert strict.evaluator_revision == "qa-v2"
    assert (
        score_qa(gold=gold, prediction=prediction, evaluator_revision="qa-v1").answer_accuracy == 1
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"completion_status": "continuation_requested"},
        {"citations": []},
        {
            "citations": [
                QACitationCheck(conclusion_fact="answer", evidence_ref="wrong", supports=False)
            ]
        },
        {"conclusion_facts": []},
        {"unknowns": ["answer"]},
        {"conflicts": ["invented conflict"]},
    ],
)
def test_task_correctness_requires_complete_supported_answer(updates):
    gold, prediction = _case(**updates)
    assert score_qa(gold=gold, prediction=prediction).task_correctness == 0


def test_required_unknowns_and_conflicts_cannot_be_omitted():
    gold, prediction = _case()
    gold = gold.model_copy(
        update={
            "required_unknowns": ["missing"],
            "acceptable_unknowns": ["missing"],
            "required_conflicts": ["source disagreement"],
        }
    )
    missing = score_qa(gold=gold, prediction=prediction)
    assert missing.task_correctness == missing.unknown_correctness == missing.conflict_handling == 0
    prediction = prediction.model_copy(
        update={"unknowns": ["missing"], "conflicts": ["source disagreement"]}
    )
    assert score_qa(gold=gold, prediction=prediction).task_correctness == 1


def test_required_unknowns_must_be_declared_acceptable():
    with pytest.raises(ValueError, match="required unknowns"):
        QAGold(case_id="invalid", required_unknowns=["missing"], completion_expectation="answered")


def test_inapplicable_unknown_and_conflict_axes_have_no_score():
    gold, prediction = _case()
    score = score_qa(gold=gold, prediction=prediction)
    assert score.task_correctness == 1
    assert score.unknown_correctness is None
    assert score.conflict_handling is None
    legacy = score_qa(gold=gold, prediction=prediction, evaluator_revision="qa-v1")
    assert legacy.unknown_correctness == legacy.conflict_handling == 1


def test_context_paths_do_not_prove_multihop_and_every_path_is_required():
    gold, prediction = _case()
    paths = [["a", "r", "b", "s", "c"], ["a", "r", "b", "t", "d"]]
    gold = gold.model_copy(update={"required_relation_paths": paths})
    prediction = prediction.model_copy(
        update={"relation_paths": paths, "available_relation_paths": paths}
    )
    assert score_qa(gold=gold, prediction=prediction).multi_hop_correctness == 0
    assert (
        score_qa(gold=gold, prediction=prediction, evaluator_revision="qa-v1").multi_hop_correctness
        == 1
    )
    prediction = prediction.model_copy(update={"decision_relation_paths": paths[:1]})
    assert score_qa(gold=gold, prediction=prediction).multi_hop_correctness == 0
    prediction = prediction.model_copy(update={"decision_relation_paths": paths})
    assert score_qa(gold=gold, prediction=prediction).multi_hop_correctness == 1
    prediction = prediction.model_copy(update={"conclusion_facts": ["wrong"]})
    assert score_qa(gold=gold, prediction=prediction).multi_hop_correctness == 0


def test_revision_dispatch_rejects_unknown_and_preserves_session_v1_alias():
    gold, prediction = _case()
    with pytest.raises(ValueError, match="evaluator revision"):
        score_qa(gold=gold, prediction=prediction, evaluator_revision="qa-typo")
    assert (
        score_qa(
            gold=gold, prediction=prediction, evaluator_revision="qa-session-v1"
        ).answer_accuracy
        == 1
    )


def test_metric_revisions_preserve_historical_definition_and_register_strict_contract():
    assert metric_definition("m6.answer_accuracy", revision="1").revision == "1"
    assert metric_definition("m6.answer_accuracy", revision="2").revision == "2"
    assert metric_definition("m6.multi_hop_correctness", revision="2").revision == "2"
    assert metric_definition("m6.task_correctness").revision == "1"
    with pytest.raises(KeyError):
        metric_definition("m6.answer_accuracy", revision="99")


@pytest.mark.parametrize("status", ["execution_failed", "not_executed"])
def test_failed_or_unattempted_empty_gold_turn_cannot_succeed(status):
    gold = QAGold(case_id="empty", completion_expectation="answered")
    prediction = QAPrediction(case_id="empty", completion_status=status)
    assert score_qa(gold=gold, prediction=prediction).task_correctness == 0


def test_v2_path_only_empty_answer_cannot_earn_multihop_success():
    paths = [["a", "r", "b", "s", "c"]]
    gold = QAGold(
        case_id="empty-path", required_relation_paths=paths, completion_expectation="answered"
    )
    prediction = QAPrediction(
        case_id="empty-path", decision_relation_paths=paths, completion_status="answered"
    )
    score = score_qa(gold=gold, prediction=prediction)
    assert score.task_correctness == score.multi_hop_correctness == 0


@pytest.mark.parametrize("status", ["execution_failed", "not_executed"])
def test_v2_failure_status_is_never_success_even_when_gold_matches(status):
    gold = QAGold(case_id="failure-gold", completion_expectation=status)
    prediction = QAPrediction(case_id="failure-gold", completion_status=status)
    score = score_qa(gold=gold, prediction=prediction)
    assert score.task_correctness == 0
    assert score.completion_correctness == 0
    assert (
        score_qa(
            gold=gold, prediction=prediction, evaluator_revision="qa-v1"
        ).completion_correctness
        == 1
    )
