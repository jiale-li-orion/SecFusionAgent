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
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
)
from packages.evaluation.benchmark.storage import MetricDefinitionModel, MetricObservationModel
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _deployment() -> DeploymentRevision:
    return DeploymentRevision(
        deployment_revision_id="deployment:test-v1",
        git_commit="abc123",
        schema_revision="20260927_0023",
        source_inventory_hash="a" * 64,
        vocabulary_revision="enrichment-v1",
        policy_revision="runtime-policy-v1",
        capability_registry_revision="capability-registry-v1",
        skill_registry_revision="skills-v1",
        model_provider_revision="provider:none",
        configuration_digest="b" * 64,
        created_at=NOW,
    )


def _case(case_id: str) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=case_id,
        case_revision=1,
        input={"cve_id": case_id},
        execution_profile="offline_scorer",
        target_refs=[f"cve:{case_id}"],
        expected_behavior={"score": "enrichment"},
        gold_ref=f"gold:{case_id}@1",
        tags=["real-structured"],
        latency_class="offline",
        replay_tier="R0",
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_benchmark_store_freezes_suite_run_case_and_metric_lifecycle() -> None:
    engine, factory = await _database()
    store = BenchmarkStore()
    try:
        async with factory() as session, session.begin():
            await store.register_deployment(session, _deployment())
            await store.register_case(session, _case("CVE-2026-0001"))
            await store.register_case(session, _case("CVE-2026-0002"))
            suite = BenchmarkSuite(
                suite_id="m3-real-structured",
                suite_revision=1,
                domain=BenchmarkDomain.M3_ENRICHMENT,
                purpose="Real structured enrichment regression",
                case_refs=["CVE-2026-0001@1", "CVE-2026-0002@1"],
                gold_revision="provider-snapshot-1",
                evaluator_revision="real-structured-v1",
                scoring_profile={"dimensions": ["severity", "product_package"]},
                created_at=NOW,
            )
            await store.register_suite(session, suite)
            run = await store.start_run(
                session,
                suite_ref="m3-real-structured@1",
                deployment_revision_id="deployment:test-v1",
                execution_mode=BenchmarkExecutionMode.OFFLINE_SCORER,
                environment="test",
                benchmark_run_id="benchmark-run-1",
                now=NOW,
            )
            case_run = await store.start_case_run(
                session,
                benchmark_run_id=run.benchmark_run_id,
                case_ref="CVE-2026-0001@1",
                case_run_id="case-run-1",
                now=NOW,
            )
            metric = await store.observe_metric(
                session,
                case_run_id=case_run.case_run_id,
                metric_name="m3.micro_recall",
                value=0.75,
                direction=MetricDirection.HIGHER_IS_BETTER,
                measurement_source=MeasurementSource.SCORER,
                evidence_refs=["gold:CVE-2026-0001@1"],
                now=NOW,
            )
            assert metric.value == 0.75
            with pytest.raises(ValueError, match="active case runs"):
                await store.finish_run(
                    session,
                    run.benchmark_run_id,
                    status=BenchmarkRunStatus.COMPLETED,
                    now=NOW,
                )
            await store.finish_case_run(
                session,
                case_run.case_run_id,
                status=BenchmarkCaseRunStatus.PASSED,
                now=NOW,
            )
            finished = await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=NOW,
            )
            assert finished.status is BenchmarkRunStatus.COMPLETED

        async with factory() as session:
            metrics = list(await session.scalars(select(MetricObservationModel)))
            assert len(metrics) == 1
            assert metrics[0].metric_name == "m3.micro_recall"
            definition = await session.get(MetricDefinitionModel, "m3.micro_recall@1")
            assert definition is not None
            assert definition.denominator == "evidence-aware closed-set gold facts"
            assert len(definition.definition_digest) == 64
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_benchmark_case_revision_is_immutable_and_suite_membership_is_enforced() -> None:
    engine, factory = await _database()
    store = BenchmarkStore()
    try:
        async with factory() as session, session.begin():
            await store.register_deployment(session, _deployment())
            case = _case("CVE-2026-1000")
            await store.register_case(session, case)
            with pytest.raises(ValueError, match="immutable"):
                await store.register_case(
                    session,
                    case.model_copy(update={"gold_ref": "gold:changed@1"}),
                )
            await store.register_case(session, _case("CVE-2026-2000"))
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id="single-case",
                    suite_revision=1,
                    domain=BenchmarkDomain.M3_ENRICHMENT,
                    purpose="single case",
                    case_refs=["CVE-2026-1000@1"],
                    gold_revision="gold-1",
                    evaluator_revision="eval-1",
                    created_at=NOW,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref="single-case@1",
                deployment_revision_id="deployment:test-v1",
                execution_mode=BenchmarkExecutionMode.OFFLINE_SCORER,
                environment="test",
                now=NOW,
            )
            with pytest.raises(ValueError, match="not part of the frozen suite"):
                await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref="CVE-2026-2000@1",
                    now=NOW,
                )
    finally:
        await engine.dispose()
