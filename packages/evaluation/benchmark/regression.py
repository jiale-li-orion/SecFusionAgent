from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from packages.evaluation.benchmark.report import CompetitionReport


class RegressionStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class RegressionRule(BaseModel):
    metric_name: str
    max_regression: float | None = None
    min_improvement: float | None = None
    hard_floor: float | None = None
    hard_ceiling: float | None = None
    required: bool = True


class RegressionResult(BaseModel):
    metric_name: str
    status: RegressionStatus
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta: float | None = None
    reason: str


class RegressionGateResult(BaseModel):
    passed: bool
    results: list[RegressionResult]


class RegressionGate:
    def evaluate(
        self,
        *,
        baseline: CompetitionReport,
        candidate: CompetitionReport,
        rules: list[RegressionRule],
    ) -> RegressionGateResult:
        baseline_metrics = {item.metric_name: item for item in baseline.metrics}
        candidate_metrics = {item.metric_name: item for item in candidate.metrics}
        results: list[RegressionResult] = []
        for rule in rules:
            base = baseline_metrics.get(rule.metric_name)
            cand = candidate_metrics.get(rule.metric_name)
            if base is None or cand is None:
                status = RegressionStatus.FAIL if rule.required else RegressionStatus.NOT_EVALUATED
                results.append(
                    RegressionResult(
                        metric_name=rule.metric_name,
                        status=status,
                        baseline_value=base.value if base is not None else None,
                        candidate_value=cand.value if cand is not None else None,
                        reason="required metric missing from baseline/candidate report",
                    )
                )
                continue
            if base.metric_definition_revision != cand.metric_definition_revision:
                results.append(
                    RegressionResult(
                        metric_name=rule.metric_name,
                        status=RegressionStatus.FAIL,
                        baseline_value=base.value,
                        candidate_value=cand.value,
                        reason=(
                            "metric definition revision changed: "
                            f"{base.metric_definition_revision} -> "
                            f"{cand.metric_definition_revision}"
                        ),
                    )
                )
                continue
            delta = cand.value - base.value
            failures: list[str] = []
            if rule.hard_floor is not None and cand.value < rule.hard_floor:
                failures.append(f"candidate below hard floor {rule.hard_floor}")
            if rule.hard_ceiling is not None and cand.value > rule.hard_ceiling:
                failures.append(f"candidate above hard ceiling {rule.hard_ceiling}")
            if rule.max_regression is not None:
                if base.direction.value == "higher_is_better":
                    regression = base.value - cand.value
                elif base.direction.value == "lower_is_better":
                    regression = cand.value - base.value
                else:
                    regression = 0.0
                if regression > rule.max_regression:
                    failures.append(f"regression {regression:.6g} exceeds {rule.max_regression}")
            if rule.min_improvement is not None:
                if base.direction.value == "higher_is_better":
                    improvement = cand.value - base.value
                elif base.direction.value == "lower_is_better":
                    improvement = base.value - cand.value
                else:
                    improvement = 0.0
                if improvement < rule.min_improvement:
                    failures.append(f"improvement {improvement:.6g} below {rule.min_improvement}")
            results.append(
                RegressionResult(
                    metric_name=rule.metric_name,
                    status=RegressionStatus.FAIL if failures else RegressionStatus.PASS,
                    baseline_value=base.value,
                    candidate_value=cand.value,
                    delta=delta,
                    reason="; ".join(failures) if failures else "rule satisfied",
                )
            )
        return RegressionGateResult(
            passed=all(item.status is not RegressionStatus.FAIL for item in results),
            results=results,
        )
