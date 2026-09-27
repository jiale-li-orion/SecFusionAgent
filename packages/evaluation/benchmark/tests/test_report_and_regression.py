from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    CompetitionReportService,
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
    RegressionGate,
    RegressionRule,
    RegressionStatus,
    TargetCheckStatus,
)
from packages.evaluation.benchmark.storage import CompetitionReportModel
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 16, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_run(factory, *, run_id: str, tp: float, fp: float, fn: float):
    store = BenchmarkStore()
    async with factory() as session, session.begin():
        await store.register_deployment(
            session,
            DeploymentRevision(
                deployment_revision_id="deployment:report-test",
                git_commit="abc",
                schema_revision="0024",
                source_inventory_hash="a" * 64,
                vocabulary_revision="enrichment-v1",
                policy_revision="policy-v1",
                capability_registry_revision="unbound",
                model_provider_revision="unconfigured",
                configuration_digest="b" * 64,
                created_at=NOW,
            ),
        )
        await store.register_case(
            session,
            BenchmarkCase(
                case_id=f"case-{run_id}",
                case_revision=1,
                input={"run": run_id},
                execution_profile="offline_scorer",
                gold_ref=f"gold:{run_id}",
                latency_class="offline",
                replay_tier="R0",
                created_at=NOW,
            ),
        )
        await store.register_suite(
            session,
            BenchmarkSuite(
                suite_id=f"suite-{run_id}",
                suite_revision=1,
                domain=BenchmarkDomain.M3_ENRICHMENT,
                purpose="report test",
                case_refs=[f"case-{run_id}@1"],
                gold_revision=f"gold-{run_id}",
                evaluator_revision="eval-v1",
                created_at=NOW,
            ),
        )
        run = await store.start_run(
            session,
            suite_ref=f"suite-{run_id}@1",
            deployment_revision_id="deployment:report-test",
            execution_mode=BenchmarkExecutionMode.OFFLINE_SCORER,
            environment="test",
            benchmark_run_id=run_id,
            now=NOW,
        )
        case_run = await store.start_case_run(
            session,
            benchmark_run_id=run.benchmark_run_id,
            case_ref=f"case-{run_id}@1",
            case_run_id=f"case-run-{run_id}",
            now=NOW,
        )
        for name, value, direction in (
            ("m3.micro_precision", 0.0, MetricDirection.HIGHER_IS_BETTER),
            ("m3.micro_recall", 0.0, MetricDirection.HIGHER_IS_BETTER),
            ("m3.true_positive", tp, MetricDirection.INFORMATIONAL),
            ("m3.false_positive", fp, MetricDirection.LOWER_IS_BETTER),
            ("m3.false_negative", fn, MetricDirection.LOWER_IS_BETTER),
        ):
            await store.observe_metric(
                session,
                case_run_id=case_run.case_run_id,
                metric_name=name,
                value=value,
                direction=direction,
                measurement_source=MeasurementSource.SCORER,
                now=NOW,
            )
        await store.finish_case_run(
            session,
            case_run.case_run_id,
            status=BenchmarkCaseRunStatus.PASSED,
            now=NOW,
        )
        await store.finish_run(
            session,
            run.benchmark_run_id,
            status=BenchmarkRunStatus.COMPLETED,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_competition_report_derives_global_m3_precision_recall_and_target_checks() -> None:
    engine, factory = await _database()
    try:
        await _seed_run(factory, run_id="run-a", tp=4, fp=0, fn=1)
        await _seed_run(factory, run_id="run-b", tp=6, fp=1, fn=0)
        async with factory() as session:
            report = await CompetitionReportService().generate(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["run-a", "run-b"],
                now=NOW,
            )
        metrics = {item.metric_name: item.value for item in report.metrics}
        assert metrics["m3.micro_precision"] == pytest.approx(10 / 11)
        assert metrics["m3.micro_recall"] == pytest.approx(10 / 11)
        assert len(report.report_digest) == 64
        checks = {item.target_name: item for item in report.target_checks}
        assert checks["enrichment_precision"].status is TargetCheckStatus.FAIL
        assert checks["qa_accuracy"].status is TargetCheckStatus.NOT_EVALUATED
        assert "M6 QA quality" in report.unevaluated_competition_areas
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_competition_report_persistence_is_idempotent_by_logical_digest() -> None:
    engine, factory = await _database()
    try:
        await _seed_run(factory, run_id="persistent", tp=20, fp=0, fn=0)
        async with factory() as session, session.begin():
            service = CompetitionReportService()
            first = await service.generate_and_persist(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["persistent"],
                artifact_refs=["artifact:report-json"],
                now=NOW,
            )
            second = await service.generate_and_persist(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["persistent"],
                artifact_refs=["artifact:ignored-second-export"],
                now=NOW,
            )
            assert second.report_id == first.report_id
            assert second.report_digest == first.report_digest
            assert second.artifact_refs == ["artifact:report-json"]
        async with factory() as session:
            rows = list(await session.scalars(select(CompetitionReportModel)))
            assert len(rows) == 1
            assert rows[0].metric_definition_refs_json
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_regression_gate_respects_metric_direction_and_hard_floor() -> None:
    engine, factory = await _database()
    try:
        await _seed_run(factory, run_id="baseline", tp=19, fp=1, fn=1)
        await _seed_run(factory, run_id="candidate", tp=20, fp=0, fn=0)
        async with factory() as session:
            service = CompetitionReportService()
            baseline = await service.generate(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["baseline"],
                now=NOW,
            )
            candidate = await service.generate(
                session,
                deployment_revision_id="deployment:report-test",
                benchmark_run_ids=["candidate"],
                now=NOW,
            )
        result = RegressionGate().evaluate(
            baseline=baseline,
            candidate=candidate,
            rules=[
                RegressionRule(
                    metric_name="m3.micro_precision",
                    max_regression=0.0,
                    hard_floor=0.95,
                ),
                RegressionRule(
                    metric_name="m3.micro_recall",
                    max_regression=0.0,
                    hard_floor=0.95,
                ),
            ],
        )
        assert result.passed is True
        assert all(item.status is RegressionStatus.PASS for item in result.results)
    finally:
        await engine.dispose()
