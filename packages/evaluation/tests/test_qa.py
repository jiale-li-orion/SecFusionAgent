from __future__ import annotations

from packages.evaluation.qa import QACitationCheck, QAGold, QAPrediction, score_qa


def test_qa_score_checks_answer_grounding_citation_multihop_and_completion() -> None:
    gold = QAGold(
        case_id="qa-1",
        required_facts=["fixed-release:0.22.0", "affected:vllm"],
        acceptable_answer_facts=["fixed-release:0.22.0"],
        forbidden_facts=["fixed-release:0.21.0"],
        required_relation_paths=[["vuln", "fix-commit", "release:0.22.0"]],
        required_citation_facts=["fixed-release:0.22.0", "affected:vllm"],
        completion_expectation="answered",
    )
    prediction = QAPrediction(
        case_id="qa-1",
        conclusion_facts=["fixed-release:0.22.0", "affected:vllm"],
        relation_paths=[["vuln", "fix-commit", "release:0.22.0"]],
        citations=[
            QACitationCheck(
                conclusion_fact="fixed-release:0.22.0",
                evidence_ref="evidence:release",
                supports=True,
            ),
            QACitationCheck(
                conclusion_fact="affected:vllm",
                evidence_ref="evidence:advisory",
                supports=True,
            ),
        ],
        completion_status="answered",
        interactive_latency_seconds=1.4,
    )
    score = score_qa(gold=gold, prediction=prediction)
    assert score.answer_accuracy == 1.0
    assert score.groundedness == 1.0
    assert score.citation_correctness == 1.0
    assert score.citation_completeness == 1.0
    assert score.multi_hop_correctness == 1.0
    assert score.completion_correctness == 1.0
    assert score.interactive_latency_seconds == 1.4


def test_qa_score_does_not_reward_correct_text_with_unsupported_citation() -> None:
    gold = QAGold(
        case_id="qa-2",
        required_facts=["cvss:9.8"],
        required_citation_facts=["cvss:9.8"],
        completion_expectation="answered",
    )
    prediction = QAPrediction(
        case_id="qa-2",
        conclusion_facts=["cvss:9.8"],
        citations=[
            QACitationCheck(
                conclusion_fact="cvss:9.8",
                evidence_ref="evidence:wrong",
                supports=False,
            )
        ],
        completion_status="answered",
    )
    score = score_qa(gold=gold, prediction=prediction)
    assert score.answer_accuracy == 1.0
    assert score.groundedness == 0.0
    assert score.citation_correctness == 0.0
    assert score.citation_completeness == 0.0
