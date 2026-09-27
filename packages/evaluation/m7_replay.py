from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from pydantic import BaseModel, Field, JsonValue, model_validator

from packages.investigation.replay import (
    ReplayCheckpoint,
    ReplayExpectation,
    ReplayIntervention,
    ReplayProtocolResult,
)


class ReplayFailureStage(StrEnum):
    AVAILABILITY = "availability"
    ENRICHMENT_GAP = "enrichment_gap_identification"
    TASK_ROLE_ROUTING = "task_role_routing"
    CAPABILITY = "capability_visibility_binding"
    POLICY = "policy_obligation_enforcement"
    PERCEPTION = "perception_selection_compression"
    INTEGRATION = "state_knowledge_integration"
    EVIDENCE_USE = "evidence_use"
    DECISION = "decision"


class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    EXACT = "exact"


class ReplayMetricRule(BaseModel):
    metric: str
    direction: MetricDirection
    tolerance: float = Field(default=0.0, ge=0.0)


class ReplayCase(BaseModel):
    replay_case_id: str
    source_ref: str
    checkpoint: ReplayCheckpoint
    expectation: ReplayExpectation = Field(default_factory=ReplayExpectation)
    expected_domain_outcome: dict[str, JsonValue] = Field(default_factory=dict)
    metric_rules: list[ReplayMetricRule] = Field(default_factory=list)

    @property
    def freeze_hash(self) -> str:
        return _digest(self.checkpoint.model_dump(mode="json"))


class ReplayVariant(BaseModel):
    variant_id: str
    intervention: ReplayIntervention | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_variant(self) -> ReplayVariant:
        if not self.variant_id.strip():
            raise ValueError("ReplayVariant variant_id cannot be empty")
        return self

    @property
    def is_baseline(self) -> bool:
        return self.intervention is None


class ReplayObservation(BaseModel):
    replay_case_id: str
    freeze_hash: str
    variant_id: str
    protocol: ReplayProtocolResult
    expected_domain_outcome_met: bool
    metrics: dict[str, float] = Field(default_factory=dict)
    failure_stage: ReplayFailureStage | None = None
    findings: list[str] = Field(default_factory=list)


class ReplayComparison(BaseModel):
    replay_case_id: str
    source_ref: str
    freeze_hash: str
    baseline: ReplayObservation
    candidate: ReplayObservation
    regression_reasons: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.candidate.protocol.passed
            and self.candidate.expected_domain_outcome_met
            and not self.regression_reasons
        )


class ReplaySuiteReport(BaseModel):
    report_id: str
    baseline_variant: ReplayVariant
    candidate_variant: ReplayVariant
    comparisons: list[ReplayComparison] = Field(min_length=1)

    @property
    def passed(self) -> bool:
        return all(comparison.passed for comparison in self.comparisons)

    @property
    def covered_source_refs(self) -> set[str]:
        return {comparison.source_ref for comparison in self.comparisons}

    @property
    def validation_case_refs(self) -> list[str]:
        return [comparison.replay_case_id for comparison in self.comparisons]


class ReplayExecutor(Protocol):
    async def execute(
        self,
        replay_case: ReplayCase,
        variant: ReplayVariant,
    ) -> ReplayObservation: ...


class M7ReplayService:
    """Compare one controlled intervention against a frozen replay checkpoint."""

    async def compare(
        self,
        *,
        cases: list[ReplayCase],
        executor: ReplayExecutor,
        candidate_variant: ReplayVariant,
        baseline_variant: ReplayVariant | None = None,
    ) -> ReplaySuiteReport:
        if not cases:
            raise ValueError("M7 replay suite requires at least one case")
        baseline = baseline_variant or ReplayVariant(variant_id="baseline")
        if not baseline.is_baseline:
            raise ValueError("baseline_variant cannot contain an intervention")
        if candidate_variant.is_baseline:
            raise ValueError("candidate_variant requires exactly one intervention")

        comparisons: list[ReplayComparison] = []
        for replay_case in cases:
            baseline_observation = await executor.execute(replay_case, baseline)
            candidate_observation = await executor.execute(replay_case, candidate_variant)
            _validate_observation(replay_case, baseline, baseline_observation)
            _validate_observation(replay_case, candidate_variant, candidate_observation)
            comparisons.append(
                ReplayComparison(
                    replay_case_id=replay_case.replay_case_id,
                    source_ref=replay_case.source_ref,
                    freeze_hash=replay_case.freeze_hash,
                    baseline=baseline_observation,
                    candidate=candidate_observation,
                    regression_reasons=_regressions(
                        replay_case.metric_rules,
                        baseline_observation.metrics,
                        candidate_observation.metrics,
                    ),
                )
            )
        report_payload = {
            "baseline": baseline.model_dump(mode="json"),
            "candidate": candidate_variant.model_dump(mode="json"),
            "comparisons": [item.model_dump(mode="json") for item in comparisons],
        }
        return ReplaySuiteReport(
            report_id=f"m7-replay:{_digest(report_payload)[:32]}",
            baseline_variant=baseline,
            candidate_variant=candidate_variant,
            comparisons=comparisons,
        )


def _validate_observation(
    replay_case: ReplayCase,
    variant: ReplayVariant,
    observation: ReplayObservation,
) -> None:
    if observation.replay_case_id != replay_case.replay_case_id:
        raise ValueError("Replay executor returned wrong replay_case_id")
    if observation.variant_id != variant.variant_id:
        raise ValueError("Replay executor returned wrong variant_id")
    if observation.freeze_hash != replay_case.freeze_hash:
        raise ValueError("Replay executor changed frozen task/world/context/budget coordinates")


def _regressions(
    rules: list[ReplayMetricRule],
    baseline: dict[str, float],
    candidate: dict[str, float],
) -> list[str]:
    reasons: list[str] = []
    for rule in rules:
        if rule.metric not in baseline or rule.metric not in candidate:
            reasons.append(f"metric_missing:{rule.metric}")
            continue
        before = baseline[rule.metric]
        after = candidate[rule.metric]
        if rule.direction is MetricDirection.HIGHER_IS_BETTER:
            regressed = after + rule.tolerance < before
        elif rule.direction is MetricDirection.LOWER_IS_BETTER:
            regressed = after > before + rule.tolerance
        else:
            regressed = abs(after - before) > rule.tolerance
        if regressed:
            reasons.append(f"metric_regression:{rule.metric}:{before}->{after}")
    return reasons


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
