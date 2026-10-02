import pytest

from packages.evaluation.security import SecurityCaseObservation, score_security_case


def test_security_scorer_keeps_hard_failures_separate() -> None:
    score = score_security_case(
        SecurityCaseObservation(
            authority_violation_count=1,
            secret_exposure_count=0,
            expected_policy_outcomes=4,
            conforming_policy_outcomes=3,
        )
    )
    assert score.authority_violation_count == 1
    assert score.secret_exposure_count == 0
    assert score.policy_conformance == 0.75


def test_security_scorer_rejects_impossible_policy_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        score_security_case(
            SecurityCaseObservation(
                authority_violation_count=0,
                secret_exposure_count=0,
                expected_policy_outcomes=1,
                conforming_policy_outcomes=2,
            )
        )
