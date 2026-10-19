from __future__ import annotations

import pytest

from packages.evaluation.benchmark.contracts import MetricDirection
from packages.evaluation.benchmark.metrics import MetricAggregation, MissingValuePolicy
from packages.evaluation.benchmark.report import (
    AggregatedMetric,
    TargetCheckStatus,
    _competition_target_checks,
)


def _metric(name: str, value: float, revision: str = "1") -> AggregatedMetric:
    return AggregatedMetric(
        metric_name=name,
        metric_definition_revision=revision,
        value=value,
        aggregation=MetricAggregation.MEAN,
        denominator="frozen independent cases",
        missing_value_policy=MissingValuePolicy.NOT_EVALUATED,
        direction=MetricDirection.HIGHER_IS_BETTER,
        observation_count=20,
        case_run_ids=[f"case:{n}" for n in range(20)],
        benchmark_run_ids=["run:preliminary"],
    )


def test_preliminary_uses_its_own_thresholds_and_strict_multihop() -> None:
    metrics = {
        name: _metric(name, value, revision)
        for name, value, revision in (
            ("m1.source_category_count", 8, "1"),
            ("m1.monitoring.max_seconds", 21600, "1"),
            ("m3.micro_precision", 0.95, "1"),
            ("m6.multi_hop_correctness", 0.85, "2"),
            ("m6.answer_accuracy", 0.90, "2"),
            ("m6.interactive_latency_seconds", 8, "1"),
        )
    }
    checks = {c.target_name: c for c in _competition_target_checks(metrics, profile="preliminary")}
    assert set(checks) == {
        "source_category_coverage",
        "monitoring_timeliness",
        "enrichment_precision",
        "qa_multihop",
    }
    assert all(c.status is TargetCheckStatus.PASS for c in checks.values())
    assert "real-time" in (checks["source_category_coverage"].note or "")


def test_preliminary_does_not_accept_legacy_context_path_score() -> None:
    name = "m6.multi_hop_correctness"
    checks = _competition_target_checks({name: _metric(name, 1)}, profile="preliminary")
    target = next(c for c in checks if c.target_name == "qa_multihop")
    assert target.status is TargetCheckStatus.NOT_EVALUATED
    assert "revision 2" in (target.note or "")


def test_preliminary_failed_threshold_and_missing_measurements_stay_visible() -> None:
    name = "m6.multi_hop_correctness"
    checks = {
        c.target_name: c
        for c in _competition_target_checks({name: _metric(name, 0.8, "2")}, profile="preliminary")
    }
    assert checks["qa_multihop"].status is TargetCheckStatus.FAIL
    assert checks["monitoring_timeliness"].status is TargetCheckStatus.NOT_EVALUATED


def test_unknown_competition_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="profile"):
        _competition_target_checks({}, profile="unreviewed")


@pytest.mark.asyncio
async def test_preliminary_report_rejects_a_missing_frozen_case() -> None:
    from sqlalchemy import select

    from packages.evaluation.benchmark.report import CompetitionReportService
    from packages.evaluation.benchmark.storage import BenchmarkSuiteModel
    from packages.evaluation.benchmark.tests.test_report_and_regression import _database, _seed_run

    engine, factory = await _database()
    try:
        await _seed_run(factory, run_id="incomplete", tp=1, fp=0, fn=0)
        async with factory() as session, session.begin():
            suite = await session.scalar(select(BenchmarkSuiteModel))
            suite.case_refs_json = [*suite.case_refs_json, "missing-case@1"]
        async with factory() as session:
            with pytest.raises(ValueError, match="frozen case coverage"):
                await CompetitionReportService().generate(
                    session,
                    deployment_revision_id="deployment:report-test",
                    benchmark_run_ids=["incomplete"],
                    profile="preliminary",
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_report_profile_persists_and_changes_identity() -> None:
    from packages.evaluation.benchmark.report import CompetitionReportService
    from packages.evaluation.benchmark.tests.test_report_and_regression import _database, _seed_run

    engine, factory = await _database()
    try:
        await _seed_run(factory, run_id="complete", tp=1, fp=0, fn=0)
        async with factory() as session, session.begin():
            service = CompetitionReportService()
            finals = await service.generate_and_persist(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["complete"],
            )
            preliminary = await service.generate_and_persist(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["complete"],
                profile="preliminary",
            )
            assert preliminary.profile == "preliminary"
            assert preliminary.report_digest != finals.report_digest
    finally:
        await engine.dispose()


def test_preliminary_rejects_missing_and_duplicate_metric_denominators():
    from types import SimpleNamespace

    from packages.evaluation.benchmark.report import _validate_preliminary_observations

    def obs(case, name, revision="1"):
        return SimpleNamespace(
            case_run_id=case,
            metric_name=name,
            metric_definition_revision=revision,
            subject_ref="turn1",
        )

    valid = [
        (obs("c", "m6.task_correctness"), "r"),
        (obs("c", "m6.multi_hop_correctness", "2"), "r"),
    ]
    _validate_preliminary_observations(valid, {"c"}, {"c": (1, 1)})
    with pytest.raises(ValueError, match="unscored"):
        _validate_preliminary_observations(valid, {"c", "missing"}, {"c": (1, 1)})
    with pytest.raises(ValueError, match="strict QA"):
        _validate_preliminary_observations(valid[:1], {"c"}, {"c": (1, 1)})
    with pytest.raises(ValueError, match="duplicate"):
        _validate_preliminary_observations(valid + valid, {"c"}, {"c": (1, 1)})
    windows = [
        (obs("a", "m1.monitoring.max_seconds"), "r1"),
        (obs("b", "m1.monitoring.max_seconds"), "r2"),
    ]
    with pytest.raises(ValueError, match="monitoring window"):
        _validate_preliminary_observations(windows, {"a", "b"}, {})


def test_adversarial_anchor_requires_complete_class_and_outcome_evidence():
    from packages.evaluation.benchmark.report import _validate_adversarial_anchor
    from packages.evaluation.benchmark.storage import (
        BenchmarkCaseRunModel,
        BenchmarkSuiteModel,
        MetricObservationModel,
    )

    suite = BenchmarkSuiteModel(
        suite_revision=1, scoring_profile_json={"required_classes": ["a", "b"]}
    )
    cases = [
        BenchmarkCaseRunModel(
            case_ref="security-adversarial-a@1", case_run_id="a", status="passed"
        ),
        BenchmarkCaseRunModel(
            case_ref="security-adversarial-b@1", case_run_id="b", status="failed"
        ),
    ]
    metadata = {
        "required_classes": ["a", "b"],
        "covered_classes": ["a", "b"],
        "uncovered_classes": [],
    }
    observations = [
        (
            MetricObservationModel(
                metric_name=name,
                metric_definition_revision="1",
                value=value,
                metadata_json=metadata,
            ),
            "r",
        )
        for name, value in [
            ("security.adversarial_class_coverage", 1),
            ("security.adversarial_case_pass_rate", 0.5),
        ]
    ]
    assert _validate_adversarial_anchor(observations, "r", suite, cases) == {"a", "b"}
    observations[1][0].value = 1
    with pytest.raises(ValueError, match="adversarial aggregate"):
        _validate_adversarial_anchor(observations, "r", suite, cases)
    observations[1][0].value = 0.5
    metadata["covered_classes"] = ["a"]
    with pytest.raises(ValueError, match="adversarial aggregate"):
        _validate_adversarial_anchor(observations, "r", suite, cases)
