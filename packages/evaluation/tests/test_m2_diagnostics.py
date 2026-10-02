from packages.evaluation.m2_diagnostics import (
    ConflictPreservationCheck,
    EntityResolutionCheck,
    EvidenceCorrectnessCheck,
    ParserFieldCheck,
    ReplaySuppressionCheck,
    score_m2_diagnostics,
)


def test_m2_diagnostic_scorer_keeps_dimensions_separate() -> None:
    score = score_m2_diagnostics(
        parser_fields=[
            ParserFieldCheck(
                check_id="p1",
                expected_value="9.8",
                predicted_value="9.8",
                locator_supports_value=True,
            ),
            ParserFieldCheck(
                check_id="p2",
                expected_value="HIGH",
                predicted_value="HIGH",
                locator_supports_value=False,
            ),
        ],
        replay_checks=[
            ReplaySuppressionCheck(
                check_id="r1",
                expected_suppressed=True,
                observed_suppressed=True,
            )
        ],
        entity_checks=[
            EntityResolutionCheck(
                check_id="e1", expected_same_entity=True, predicted_same_entity=True
            ),
            EntityResolutionCheck(
                check_id="e2", expected_same_entity=False, predicted_same_entity=True
            ),
        ],
        evidence_checks=[
            EvidenceCorrectnessCheck(
                check_id="v1",
                accepted_assertion=True,
                evidence_supports_assertion=True,
            )
        ],
        conflict_checks=[
            ConflictPreservationCheck(
                check_id="c1",
                expected_conflict=True,
                competing_assertions_preserved=True,
            )
        ],
    )
    assert score.parser_field_accuracy == 0.5
    assert score.replay_suppression_accuracy == 1.0
    assert score.entity_resolution_precision == 0.5
    assert score.entity_resolution_recall == 1.0
    assert score.evidence_correctness == 1.0
    assert score.conflict_preservation == 1.0
