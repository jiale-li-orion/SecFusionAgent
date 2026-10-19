from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from math import ceil
from typing import Any, Literal, cast
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
    BenchmarkCaseModel,
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    BenchmarkSuiteModel,
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
    profile: Literal["finals", "preliminary"] = "finals"
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
        profile: Literal["finals", "preliminary"] = "finals",
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
        preliminary_case_ids: set[str] = set()
        qa_expected_counts: dict[str, tuple[int, int]] = {}
        adversarial_anchors: dict[str, tuple[BenchmarkSuiteModel, list[BenchmarkCaseRunModel]]] = {}
        for run_id in benchmark_run_ids:
            run = by_id[run_id]
            if run.deployment_revision_id != deployment_revision_id:
                raise ValueError(
                    f"benchmark run {run_id} belongs to a different deployment revision"
                )
            if run.status != "completed":
                raise ValueError(f"benchmark run {run_id} is not completed")
            if profile == "preliminary":
                suite = await session.get(BenchmarkSuiteModel, run.suite_version_id)
                case_runs = list(
                    await session.scalars(
                        select(BenchmarkCaseRunModel).where(
                            BenchmarkCaseRunModel.benchmark_run_id == run_id
                        )
                    )
                )
                if suite is None or Counter(c.case_ref for c in case_runs) != Counter(
                    suite.case_refs_json
                ):
                    raise ValueError(
                        f"preliminary frozen case coverage is incomplete or duplicated: {run_id}"
                    )
                if any(c.status not in {"passed", "failed"} for c in case_runs):
                    raise ValueError(
                        f"preliminary frozen case coverage contains unscored cases: {run_id}"
                    )
                preliminary_case_ids.update(c.case_run_id for c in case_runs)
                if (
                    suite.suite_id == "security-adversarial-v1"
                    and suite.evaluator_revision == "security-adversarial-v1"
                ):
                    adversarial_anchors[run_id] = (suite, case_runs)
                if suite.evaluator_revision in {"qa-v2", "qa-session-v2"}:
                    for case_run in case_runs:
                        case = await session.get(BenchmarkCaseModel, case_run.case_version_id)
                        if case is None:
                            raise ValueError("frozen QA case not found")
                        expected = cast(dict[str, Any], case.expected_behavior_json)
                        golds = (
                            [turn["gold"] for turn in expected["turns"]]
                            if "turns" in expected
                            else [expected]
                        )
                        qa_expected_counts[case_run.case_run_id] = (
                            len(golds),
                            sum(bool(g.get("required_relation_paths")) for g in golds),
                        )

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
        if profile == "preliminary":
            for run_id, (suite, case_runs) in adversarial_anchors.items():
                preliminary_case_ids.difference_update(
                    _validate_adversarial_anchor(observations, run_id, suite, case_runs)
                )
            _validate_preliminary_observations(
                observations, preliminary_case_ids, qa_expected_counts
            )
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
        checks = _competition_target_checks(metric_map, profile=profile)
        unevaluated = _unevaluated_areas(metric_map)
        if profile == "preliminary":
            unevaluated.extend(
                [
                    "Preliminary qualitative review: source breadth with real-time monitoring",
                    (
                        "Preliminary qualitative review: automatic association "
                        "and deep cross-document QA"
                    ),
                    (
                        "Preliminary qualitative review: Agent architecture, "
                        "end-to-end self-healing and documentation"
                    ),
                ]
            )
        report = CompetitionReport(
            profile=profile,
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
        profile: Literal["finals", "preliminary"] = "finals",
        now: datetime | None = None,
    ) -> CompetitionReport:
        report = await self.generate(
            session,
            deployment_revision_id=deployment_revision_id,
            benchmark_run_ids=benchmark_run_ids,
            profile=profile,
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
    # Old reports had no profile field; retain their content identity exactly.
    if report.profile == "finals":
        payload.pop("profile", None)
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
    *,
    profile: str = "finals",
) -> list[CompetitionTargetCheck]:
    if profile not in {"finals", "preliminary"}:
        raise ValueError(f"unsupported competition profile: {profile}")
    specs: tuple[tuple[str, str, str, str, float], ...] = (
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
    if profile == "preliminary":
        specs = (
            (
                "source_category_coverage",
                "Preliminary source support: at least 7 categories",
                "m1.source_category_count",
                ">=",
                7.0,
            ),
            (
                "monitoring_timeliness",
                "Preliminary development check: all scored steady-state samples <= 6h",
                "m1.monitoring.max_seconds",
                "<=",
                21600.0,
            ),
            (
                "enrichment_precision",
                "Preliminary excellent target: enrichment precision >= 95%",
                "m3.micro_precision",
                ">=",
                0.95,
            ),
            (
                "qa_multihop",
                "Preliminary excellent target: supported multi-hop task accuracy >= 85%",
                "m6.multi_hop_correctness",
                ">=",
                0.85,
            ),
        )
    result: list[CompetitionTargetCheck] = []
    for target_name, requirement, metric_name, comparator, threshold in specs:
        metric = metrics.get(metric_name)
        if (
            profile == "preliminary"
            and target_name == "qa_multihop"
            and metric is not None
            and metric.metric_definition_revision != "2"
        ):
            result.append(
                CompetitionTargetCheck(
                    target_name=target_name,
                    requirement=requirement,
                    metric_name=metric_name,
                    comparator=comparator,
                    threshold=threshold,
                    status=TargetCheckStatus.NOT_EVALUATED,
                    note=(
                        "requires metric revision 2: legacy context-path coverage "
                        "is not task correctness"
                    ),
                )
            )
            continue
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
                note=(
                    (
                        "Category support only; real-time monitoring requires "
                        "separate operational review."
                    )
                    if profile == "preliminary" and target_name == "source_category_coverage"
                    else None
                ),
            )
        )
    return result


def _unevaluated_areas(metrics: dict[str, AggregatedMetric]) -> list[str]:
    required_groups = {
        "M1 monitoring latency": ("m1.monitoring.evaluable_coverage",),
        "M2 parser/entity/evidence diagnostics": (
            "m2.parser_field_accuracy",
            "m2.replay_suppression_accuracy",
            "m2.entity_resolution_precision",
            "m2.entity_resolution_recall",
            "m2.evidence_correctness",
            "m2.conflict_preservation",
        ),
        "M3 enrichment precision/recall": ("m3.micro_precision", "m3.micro_recall"),
        "M3 dimension-macro quality": (
            "m3.dimension_macro_precision",
            "m3.dimension_macro_recall",
        ),
        "M6 QA quality": (
            "m6.answer_accuracy",
            "m6.groundedness",
            "m6.citation_correctness",
            "m6.citation_completeness",
        ),
        "M6 multi-hop": ("m6.multi_hop_correctness",),
        "Agent runtime": (
            "agent.task_success",
            "agent.capability_selection_correctness",
            "agent.argument_correctness",
            "agent.trajectory_conformance",
            "agent.recovery_success_rate",
            "agent.timeout_rate",
            "agent.wall_latency_seconds",
        ),
        "Agent execution economics": (
            "runtime.model_input_tokens",
            "runtime.model_output_tokens",
            "runtime.capability_call_count",
        ),
        "Long Investigation completion": (
            "m6.investigation_final_decision_completion",
            "m6.investigation_time_to_first_status_seconds",
            "m6.investigation_time_to_final_decision_seconds",
        ),
        "Security adversarial hard gates": (
            "security.authority_violation_count",
            "security.secret_exposure_count",
            "security.policy_conformance",
        ),
        "Security adversarial breadth": (
            "security.adversarial_class_coverage",
            "security.adversarial_case_pass_rate",
        ),
        "Engineering fault/recovery": (
            "engineering.fault_recovery_success",
            "engineering.failure_isolation",
            "engineering.retry_correctness",
            "engineering.bounded_termination",
        ),
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


def _validate_preliminary_observations(
    observations: list[tuple[MetricObservationModel, str]],
    expected_case_ids: set[str],
    qa_expected_counts: dict[str, tuple[int, int]],
) -> None:
    """Fail closed when a selected failed case/turn could disappear from scoring."""
    keys = [(o.case_run_id, o.metric_name, o.subject_ref) for o, _ in observations]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate preliminary metric observations")
    observed_cases = {o.case_run_id for o, _ in observations}
    if expected_case_ids - observed_cases:
        raise ValueError("preliminary report contains unscored frozen cases")
    if sum(o.metric_name == "m1.monitoring.max_seconds" for o, _ in observations) > 1:
        raise ValueError(
            "preliminary report requires one frozen monitoring window; LAST is not a pooled maximum"
        )
    counts = Counter(
        (o.case_run_id, o.metric_name, o.metric_definition_revision) for o, _ in observations
    )
    for case_id, (turns, multi_hop_turns) in qa_expected_counts.items():
        if (
            counts[(case_id, "m6.task_correctness", "1")] != turns
            or counts[(case_id, "m6.multi_hop_correctness", "2")] != multi_hop_turns
        ):
            raise ValueError("strict QA metric denominator does not cover frozen cases/turns")


def _validate_adversarial_anchor(
    observations: list[tuple[MetricObservationModel, str]],
    run_id: str,
    suite: BenchmarkSuiteModel,
    cases: list[BenchmarkCaseRunModel],
) -> set[str]:
    """The v1 security runner stores suite metrics on one CaseRun anchor.

    Validate the complete frozen class/outcome denominator before allowing its
    terminal siblings to have no per-case observations. No generic exemption.
    """
    required = suite.scoring_profile_json.get("required_classes")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        raise ValueError("adversarial aggregate has invalid class manifest")
    refs = {f"security-adversarial-{c}@{suite.suite_revision}" for c in required}
    if refs != {c.case_ref for c in cases} or len(cases) != len(required):
        raise ValueError("adversarial aggregate class membership mismatch")
    if any(c.status not in {"passed", "failed"} for c in cases):
        raise ValueError("adversarial aggregate contains unexecuted classes")
    expected = {
        "security.adversarial_class_coverage": 1.0,
        "security.adversarial_case_pass_rate": sum(c.status == "passed" for c in cases)
        / len(cases),
    }
    for name, value in expected.items():
        rows = [o for o, r in observations if r == run_id and o.metric_name == name]
        if len(rows) != 1 or rows[0].metric_definition_revision != "1":
            raise ValueError("adversarial aggregate metric missing or duplicated")
        row = rows[0]
        metadata = row.metadata_json
        if (
            abs(row.value - value) > 1e-12
            or metadata.get("uncovered_classes") != []
            or Counter(cast(list[str], metadata.get("required_classes", []))) != Counter(required)
            or Counter(cast(list[str], metadata.get("covered_classes", []))) != Counter(required)
        ):
            raise ValueError("adversarial aggregate disagrees with frozen class outcomes")
    return {c.case_run_id for c in cases}
