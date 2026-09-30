from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel

from packages.evaluation.benchmark.contracts import MetricDirection


class MetricAggregation(StrEnum):
    MEAN = "mean"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    P50 = "p50"
    P95 = "p95"
    LAST = "last"
    DERIVED = "derived"


class MissingValuePolicy(StrEnum):
    EXCLUDE = "exclude"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class MetricDefinition(BaseModel):
    name: str
    revision: str
    denominator: str
    aggregation: MetricAggregation
    missing_value_policy: MissingValuePolicy
    direction: MetricDirection
    unit: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.revision}"

    @property
    def digest(self) -> str:
        return sha256(
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()


CORE_METRICS: dict[str, MetricDefinition] = {
    item.name: item
    for item in (
        MetricDefinition(
            name="m1.source_category_count",
            revision="1",
            denominator="fixed eight-category product source taxonomy",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="categories",
        ),
        MetricDefinition(
            name="m1.source_delivery_coverage",
            revision="1",
            denominator="frozen expected source delivery keys",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_overlap_rate",
            revision="1",
            denominator="follow-up RETRIEVE turns with non-empty document-chunk refs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_invocation_coverage",
            revision="1",
            denominator="follow-up RETRIEVE turns in a QASessionCase",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_retrieval_reuse_rate",
            revision="1",
            denominator="follow-up RETRIEVE turns with one durable retrieval invocation",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.INFORMATIONAL,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.citation_completeness",
            revision="1",
            denominator="factual conclusions requiring citation coverage",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.evaluable_coverage",
            revision="1",
            denominator="all monitoring latency samples in the frozen window",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.p50_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.unknown_correctness",
            revision="1",
            denominator="QA cases with adjudicated unknown/abstention behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.EXCLUDE,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.conflict_handling",
            revision="1",
            denominator="QA cases with adjudicated source conflicts",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.EXCLUDE,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.completion_correctness",
            revision="1",
            denominator="frozen QA cases with expected DIRECT/ANSWER/CONTINUE behavior",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m1.monitoring.p95_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m1.monitoring.max_seconds",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m1.monitoring.within_6h_rate",
            revision="1",
            denominator="latency-evaluable samples only",
            aggregation=MetricAggregation.LAST,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.micro_precision",
            revision="1",
            denominator="evidence-aware closed-set predicted facts",
            aggregation=MetricAggregation.DERIVED,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.micro_recall",
            revision="1",
            denominator="evidence-aware closed-set gold facts",
            aggregation=MetricAggregation.DERIVED,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m3.true_positive",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.INFORMATIONAL,
            unit="facts",
        ),
        MetricDefinition(
            name="m3.false_positive",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="facts",
        ),
        MetricDefinition(
            name="m3.false_negative",
            revision="1",
            denominator="evidence-aware closed-set facts",
            aggregation=MetricAggregation.SUM,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="facts",
        ),
        MetricDefinition(
            name="m6.answer_accuracy",
            revision="1",
            denominator="frozen QA cases with adjudicated answer gold",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.groundedness",
            revision="1",
            denominator="factual conclusions requiring evidence",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.citation_correctness",
            revision="1",
            denominator="answer citations checked against supporting evidence",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.multi_hop_correctness",
            revision="1",
            denominator="QA cases requiring adjudicated intermediate relation paths",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.interactive_latency_seconds",
            revision="1",
            denominator="interactive QA cases only; long investigations excluded",
            aggregation=MetricAggregation.P95,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.LOWER_IS_BETTER,
            unit="seconds",
        ),
        MetricDefinition(
            name="m6.session_context_chain_correctness",
            revision="1",
            denominator="live Product QA session cases with at least two turns",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="m6.session_target_carry_correctness",
            revision="1",
            denominator="follow-up turns with frozen expected canonical target keys",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.FAIL,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="agent.task_success",
            revision="1",
            denominator="frozen Agent benchmark case runs",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
        MetricDefinition(
            name="engineering.fault_recovery_success",
            revision="1",
            denominator="frozen fault-injection cases",
            aggregation=MetricAggregation.MEAN,
            missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
            direction=MetricDirection.HIGHER_IS_BETTER,
            unit="ratio",
        ),
    )
}


def metric_definition(name: str) -> MetricDefinition:
    exact = CORE_METRICS.get(name)
    if exact is not None:
        return exact
    if name.startswith("m3.dimension."):
        suffix = name.rsplit(".", 1)[-1]
        if suffix in {"precision", "recall"}:
            return MetricDefinition(
                name=name,
                revision="1",
                denominator="closed-set facts in the named enrichment dimension",
                aggregation=MetricAggregation.MEAN,
                missing_value_policy=MissingValuePolicy.EXCLUDE,
                direction=MetricDirection.HIGHER_IS_BETTER,
                unit="ratio",
            )
        if suffix in {"true_positive", "false_positive", "false_negative"}:
            return MetricDefinition(
                name=name,
                revision="1",
                denominator="closed-set facts in the named enrichment dimension",
                aggregation=MetricAggregation.SUM,
                missing_value_policy=MissingValuePolicy.EXCLUDE,
                direction=(
                    MetricDirection.INFORMATIONAL
                    if suffix == "true_positive"
                    else MetricDirection.LOWER_IS_BETTER
                ),
                unit="facts",
            )
    raise KeyError(f"metric definition is not registered: {name}")
