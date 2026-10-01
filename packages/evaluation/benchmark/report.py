from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from math import ceil
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.evaluation.benchmark.contracts import MetricDirection
from packages.evaluation.benchmark.metrics import (
    MetricAggregation,
    MetricDefinition,
    MissingValuePolicy,
)
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    CompetitionReportModel,
    MetricDefinitionModel,
    MetricObservationModel,
)


class TargetCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class AggregatedMetric(BaseModel):
    metric_name: str
    metric_definition_revision: str
    value: float
    unit: str | None = None
    aggregation: MetricAggregation
    denominator: str
    missing_value_policy: MissingValuePolicy
    direction: MetricDirection
    observation_count: int = Field(ge=1)
    case_run_ids: list[str]
    benchmark_run_ids: list[str]


class CompetitionTargetCheck(BaseModel):
    target_name: str
    requirement: str
    metric_name: str
    comparator: str
    threshold: float
    observed_value: float | None = None
    status: TargetCheckStatus
    benchmark_run_ids: list[str] = Field(default_factory=list)
    note: str | None = None


class CompetitionReport(BaseModel):
    report_id: str
    report_digest: str
    deployment_revision_id: str
    benchmark_run_ids: list[str]
    generated_at: datetime
    metrics: list[AggregatedMetric]
    target_checks: list[CompetitionTargetCheck]
    metric_definition_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    unevaluated_competition_areas: list[str] = Field(default_factory=list)


class CompetitionReportService:
    async def generate(
        self,
        session: AsyncSession,
        *,
        deployment_revision_id: str,
        benchmark_run_ids: list[str],
        now: datetime | None = None,
    ) -> CompetitionReport:
        if not benchmark_run_ids:
            raise ValueError("competition report requires at least one benchmark run")
        if len(set(benchmark_run_ids)) != len(benchmark_run_ids):
            raise ValueError("benchmark_run_ids must be unique")

        runs = list(
            await session.scalars(
                select(BenchmarkRunModel).where(
                    BenchmarkRunModel.benchmark_run_id.in_(benchmark_run_ids)
                )
            )
        )
        by_id = {item.benchmark_run_id: item for item in runs}
        missing = [item for item in benchmark_run_ids if item not in by_id]
        if missing:
            raise LookupError(f"benchmark runs not found: {missing}")
        for run_id in benchmark_run_ids:
            run = by_id[run_id]
            if run.deployment_revision_id != deployment_revision_id:
                raise ValueError(
                    f"benchmark run {run_id} belongs to a different deployment revision"
                )
            if run.status != "completed":
                raise ValueError(f"benchmark run {run_id} is not completed")

        result = await session.execute(
            select(MetricObservationModel, BenchmarkCaseRunModel.benchmark_run_id)
            .join(
                BenchmarkCaseRunModel,
                BenchmarkCaseRunModel.case_run_id == MetricObservationModel.case_run_id,
            )
            .where(BenchmarkCaseRunModel.benchmark_run_id.in_(benchmark_run_ids))
            .order_by(MetricObservationModel.created_at, MetricObservationModel.metric_name)
        )
        observations = [(row[0], row[1]) for row in result.all()]
        definition_refs = sorted(
            {f"{item.metric_name}@{item.metric_definition_revision}" for item, _ in observations}
        )
        definition_models = list(
            await session.scalars(
                select(MetricDefinitionModel).where(
                    MetricDefinitionModel.metric_definition_ref.in_(definition_refs)
                )
            )
        )
        definitions = {
            item.metric_definition_ref: _definition_view(item) for item in definition_models
        }
        missing_definitions = [item for item in definition_refs if item not in definitions]
        if missing_definitions:
            raise ValueError(
                f"benchmark metrics reference missing durable definitions: {missing_definitions}"
            )
        metrics = _aggregate_observations(observations, definitions)
        metric_map = {item.metric_name: item for item in metrics}
        checks = _competition_target_checks(metric_map)
        unevaluated = _unevaluated_areas(metric_map)
        report = CompetitionReport(
            report_id=str(uuid4()),
            report_digest="",
            deployment_revision_id=deployment_revision_id,
            benchmark_run_ids=list(benchmark_run_ids),
            generated_at=now or datetime.now(UTC),
            metrics=metrics,
            target_checks=checks,
            metric_definition_refs=definition_refs,
            artifact_refs=[],
            unevaluated_competition_areas=unevaluated,
        )
        return report.model_copy(update={"report_digest": _competition_report_digest(report)})

    async def generate_and_persist(
        self,
        session: AsyncSession,
        *,
        deployment_revision_id: str,
        benchmark_run_ids: list[str],
        artifact_refs: list[str] | None = None,
        now: datetime | None = None,
    ) -> CompetitionReport:
        report = await self.generate(
            session,
            deployment_revision_id=deployment_revision_id,
            benchmark_run_ids=benchmark_run_ids,
            now=now,
        )
        resolved_artifacts = list(artifact_refs or [])
        report = report.model_copy(update={"artifact_refs": resolved_artifacts})
        report = report.model_copy(update={"report_digest": _competition_report_digest(report)})
        existing = await session.scalar(
            select(CompetitionReportModel).where(
                CompetitionReportModel.report_digest == report.report_digest
            )
        )
        if existing is not None:
            return CompetitionReport.model_validate(existing.payload_json)
        payload = report.model_dump(mode="json")
        session.add(
            CompetitionReportModel(
                report_id=report.report_id,
                report_digest=report.report_digest,
                deployment_revision_id=report.deployment_revision_id,
                benchmark_run_ids_json=list(report.benchmark_run_ids),
                metric_definition_refs_json=list(report.metric_definition_refs),
                payload_json=payload,
                artifact_refs_json=resolved_artifacts,
                generated_at=report.generated_at,
            )
        )
        await session.flush()
        return report


def _competition_report_digest(report: CompetitionReport) -> str:
    payload = report.model_dump(
        mode="json",
        exclude={"report_id", "report_digest", "generated_at"},
    )
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _aggregate_observations(
    rows: list[tuple[MetricObservationModel, str]],
    definitions: dict[str, MetricDefinition],
) -> list[AggregatedMetric]:
    grouped: dict[tuple[str, str], list[tuple[MetricObservationModel, str]]] = defaultdict(list)
    for observation, benchmark_run_id in rows:
        grouped[(observation.metric_name, observation.metric_definition_revision)].append(
            (observation, benchmark_run_id)
        )

    revisions_by_name: dict[str, set[str]] = defaultdict(set)
    for name, revision in grouped:
        revisions_by_name[name].add(revision)
    mixed = {name: revisions for name, revisions in revisions_by_name.items() if len(revisions) > 1}
    if mixed:
        raise ValueError(f"report cannot mix metric definition revisions: {mixed}")

    result: list[AggregatedMetric] = []
    for (name, revision), values in sorted(grouped.items()):
        definition = definitions[f"{name}@{revision}"]
        aggregated_value = _aggregate_metric(definition, values, grouped)
        result.append(
            AggregatedMetric(
                metric_name=name,
                metric_definition_revision=revision,
                value=aggregated_value,
                unit=values[-1][0].unit or definition.unit,
                aggregation=definition.aggregation,
                denominator=definition.denominator,
                missing_value_policy=definition.missing_value_policy,
                direction=definition.direction,
                observation_count=len(values),
                case_run_ids=sorted({item.case_run_id for item, _ in values}),
                benchmark_run_ids=sorted({run_id for _, run_id in values}),
            )
        )
    return result


def _aggregate_metric(
    definition: MetricDefinition,
    values: list[tuple[MetricObservationModel, str]],
    grouped: dict[tuple[str, str], list[tuple[MetricObservationModel, str]]],
) -> float:
    numeric = [item.value for item, _ in values]
    aggregation = definition.aggregation
    if aggregation is MetricAggregation.MEAN:
        return sum(numeric) / len(numeric)
    if aggregation is MetricAggregation.SUM:
        return sum(numeric)
    if aggregation is MetricAggregation.MIN:
        return min(numeric)
    if aggregation is MetricAggregation.MAX:
        return max(numeric)
    if aggregation is MetricAggregation.P50:
        return _nearest_rank(numeric, 0.50)
    if aggregation is MetricAggregation.P95:
        return _nearest_rank(numeric, 0.95)
    if aggregation is MetricAggregation.LAST:
        return numeric[-1]
    if aggregation is MetricAggregation.DERIVED:
        if definition.name == "m3.micro_precision":
            tp = _sum_metric(grouped, "m3.true_positive")
            fp = _sum_metric(grouped, "m3.false_positive")
            if tp + fp == 0:
                fn = _sum_metric(grouped, "m3.false_negative")
                return 1.0 if fn == 0 else 0.0
            return tp / (tp + fp)
        if definition.name == "m3.micro_recall":
            tp = _sum_metric(grouped, "m3.true_positive")
            fn = _sum_metric(grouped, "m3.false_negative")
            return tp / (tp + fn) if tp + fn else 1.0
        raise ValueError(f"no derived aggregation implementation for {definition.name}")
    raise ValueError(f"unsupported metric aggregation: {aggregation.value}")


def _sum_metric(
    grouped: dict[tuple[str, str], list[tuple[MetricObservationModel, str]]],
    metric_name: str,
) -> float:
    matches = [rows for (name, _), rows in grouped.items() if name == metric_name]
    if len(matches) > 1:
        raise ValueError(f"derived metric mixes definition revisions: {metric_name}")
    rows = matches[0] if matches else []
    if not rows:
        raise ValueError(f"derived metric is missing required component: {metric_name}")
    return sum(item.value for item, _ in rows)


def _nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _competition_target_checks(
    metrics: dict[str, AggregatedMetric],
) -> list[CompetitionTargetCheck]:
    specs = (
        (
            "source_category_coverage",
            "Competition excellent/full-coverage target: at least 7 source categories",
            "m1.source_category_count",
            ">=",
            7.0,
        ),
        (
            "enrichment_precision",
            "Finals development target: enrichment precision >= 95%",
            "m3.micro_precision",
            ">=",
            0.95,
        ),
        (
            "enrichment_recall",
            "Finals development target: enrichment recall >= 95%",
            "m3.micro_recall",
            ">=",
            0.95,
        ),
        (
            "qa_accuracy",
            "Finals excellent target: QA accuracy >= 95%",
            "m6.answer_accuracy",
            ">=",
            0.95,
        ),
        (
            "qa_interactive_latency",
            "Finals QA response target for interactive cases: <= 5 seconds",
            "m6.interactive_latency_seconds",
            "<=",
            5.0,
        ),
    )
    result: list[CompetitionTargetCheck] = []
    for target_name, requirement, metric_name, comparator, threshold in specs:
        metric = metrics.get(metric_name)
        if metric is None:
            result.append(
                CompetitionTargetCheck(
                    target_name=target_name,
                    requirement=requirement,
                    metric_name=metric_name,
                    comparator=comparator,
                    threshold=threshold,
                    status=TargetCheckStatus.NOT_EVALUATED,
                    note="required benchmark metric is absent from the selected run set",
                )
            )
            continue
        passed = metric.value >= threshold if comparator == ">=" else metric.value <= threshold
        result.append(
            CompetitionTargetCheck(
                target_name=target_name,
                requirement=requirement,
                metric_name=metric_name,
                comparator=comparator,
                threshold=threshold,
                observed_value=metric.value,
                status=TargetCheckStatus.PASS if passed else TargetCheckStatus.FAIL,
                benchmark_run_ids=list(metric.benchmark_run_ids),
            )
        )
    return result


def _unevaluated_areas(metrics: dict[str, AggregatedMetric]) -> list[str]:
    required_groups = {
        "M1 monitoring latency": ("m1.monitoring.evaluable_coverage",),
        "M3 enrichment precision/recall": ("m3.micro_precision", "m3.micro_recall"),
        "M6 QA quality": (
            "m6.answer_accuracy",
            "m6.groundedness",
            "m6.citation_correctness",
        ),
        "M6 multi-hop": ("m6.multi_hop_correctness",),
        "Agent runtime": ("agent.task_success",),
        "Long Investigation completion": (
            "m6.investigation_final_decision_completion",
            "m6.investigation_time_to_final_decision_seconds",
        ),
        "Engineering fault/recovery": ("engineering.fault_recovery_success",),
    }
    return [
        label
        for label, names in required_groups.items()
        if any(name not in metrics for name in names)
    ]


def _definition_view(model: MetricDefinitionModel) -> MetricDefinition:
    return MetricDefinition(
        name=model.metric_name,
        revision=model.revision,
        denominator=model.denominator,
        aggregation=MetricAggregation(model.aggregation),
        missing_value_policy=MissingValuePolicy(model.missing_value_policy),
        direction=MetricDirection(model.direction),
        unit=model.unit,
    )
