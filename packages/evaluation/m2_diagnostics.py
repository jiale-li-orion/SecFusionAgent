from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue


class ParserFieldCheck(BaseModel):
    check_id: str
    expected_value: JsonValue
    predicted_value: JsonValue
    locator_supports_value: bool


class ReplaySuppressionCheck(BaseModel):
    check_id: str
    expected_suppressed: bool
    observed_suppressed: bool


class EntityResolutionCheck(BaseModel):
    check_id: str
    expected_same_entity: bool
    predicted_same_entity: bool


class EvidenceCorrectnessCheck(BaseModel):
    check_id: str
    accepted_assertion: bool
    evidence_supports_assertion: bool


class ConflictPreservationCheck(BaseModel):
    check_id: str
    expected_conflict: bool
    competing_assertions_preserved: bool


class M2DiagnosticScore(BaseModel):
    parser_field_accuracy: float | None = Field(default=None, ge=0, le=1)
    replay_suppression_accuracy: float | None = Field(default=None, ge=0, le=1)
    entity_resolution_precision: float | None = Field(default=None, ge=0, le=1)
    entity_resolution_recall: float | None = Field(default=None, ge=0, le=1)
    evidence_correctness: float | None = Field(default=None, ge=0, le=1)
    conflict_preservation: float | None = Field(default=None, ge=0, le=1)


def score_m2_diagnostics(
    *,
    parser_fields: list[ParserFieldCheck] | None = None,
    replay_checks: list[ReplaySuppressionCheck] | None = None,
    entity_checks: list[EntityResolutionCheck] | None = None,
    evidence_checks: list[EvidenceCorrectnessCheck] | None = None,
    conflict_checks: list[ConflictPreservationCheck] | None = None,
) -> M2DiagnosticScore:
    parser_fields = parser_fields or []
    replay_checks = replay_checks or []
    entity_checks = entity_checks or []
    evidence_checks = evidence_checks or []
    conflict_checks = conflict_checks or []
    parser_correct = sum(
        item.expected_value == item.predicted_value and item.locator_supports_value
        for item in parser_fields
    )
    replay_correct = sum(
        item.expected_suppressed == item.observed_suppressed for item in replay_checks
    )

    entity_tp = sum(
        item.expected_same_entity and item.predicted_same_entity for item in entity_checks
    )
    entity_fp = sum(
        not item.expected_same_entity and item.predicted_same_entity for item in entity_checks
    )
    entity_fn = sum(
        item.expected_same_entity and not item.predicted_same_entity for item in entity_checks
    )

    accepted_evidence = [item for item in evidence_checks if item.accepted_assertion]
    supported_evidence = sum(item.evidence_supports_assertion for item in accepted_evidence)
    expected_conflicts = [item for item in conflict_checks if item.expected_conflict]
    preserved_conflicts = sum(item.competing_assertions_preserved for item in expected_conflicts)

    return M2DiagnosticScore(
        parser_field_accuracy=_ratio(parser_correct, len(parser_fields)),
        replay_suppression_accuracy=_ratio(replay_correct, len(replay_checks)),
        entity_resolution_precision=_ratio(entity_tp, entity_tp + entity_fp),
        entity_resolution_recall=_ratio(entity_tp, entity_tp + entity_fn),
        evidence_correctness=_ratio(supported_evidence, len(accepted_evidence)),
        conflict_preservation=_ratio(preserved_conflicts, len(expected_conflicts)),
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
