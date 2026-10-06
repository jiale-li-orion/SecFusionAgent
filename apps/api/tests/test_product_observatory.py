from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseModel,
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    BenchmarkSuiteModel,
    DeploymentRevisionModel,
    MetricObservationModel,
)
from packages.shared.db import Base

NOW = datetime(2026, 10, 5, 1, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        deployment = DeploymentRevisionModel(
            deployment_revision_id="deployment:test",
            git_commit="deadbeef",
            container_image_digest=None,
            schema_revision="schema:test",
            source_inventory_hash="a" * 64,
            vocabulary_revision="vocab:test",
            policy_revision="policy:test",
            capability_registry_revision="capability:test",
            skill_registry_revision="skill:test",
            model_provider_revision="model:test",
            configuration_digest="b" * 64,
            created_at=NOW,
        )
        suite = BenchmarkSuiteModel(
            suite_version_id="suite-version-1",
            suite_id="suite:test",
            suite_revision=1,
            domain="product",
            purpose="product proof fixture",
            case_refs_json=["case:test@1"],
            gold_revision="gold:test",
            evaluator_revision="evaluator:test",
            default_world_snapshot_ref="world:test",
            scoring_profile_json={},
            content_hash="c" * 64,
            created_at=NOW,
        )
        case = BenchmarkCaseModel(
            case_version_id="case-version-1",
            case_id="case:test",
            case_revision=1,
            input_json={"question": "fixture"},
            execution_profile="VERIFY",
            target_refs_json=["object:test"],
            world_snapshot_ref="world:test",
            fixture_refs_json=[],
            expected_behavior_json={},
            gold_ref="gold:test",
            tags_json=["product"],
            latency_class="interactive",
            replay_tier="core",
            content_hash="d" * 64,
            created_at=NOW,
        )
        run = BenchmarkRunModel(
            benchmark_run_id="run-1",
            suite_version_id=suite.suite_version_id,
            suite_ref="suite:test@1",
            gold_revision="gold:test",
            deployment_revision_id=deployment.deployment_revision_id,
            model_config_ref="model:test",
            world_snapshot_ref="world:test",
            started_at=NOW,
            finished_at=NOW,
            status="completed",
            execution_mode="replay",
            warm_cold_condition="warm",
            environment="test",
        )
        case_run = BenchmarkCaseRunModel(
            case_run_id="case-run-1",
            benchmark_run_id=run.benchmark_run_id,
            case_version_id=case.case_version_id,
            case_ref="case:test@1",
            task_run_id=None,
            execution_id=None,
            decision_ref="decision:test",
            replay_checkpoint_ref="checkpoint:test",
            started_at=NOW,
            finished_at=NOW,
            status="passed",
            failure_class=None,
            artifact_refs_json=["artifact:test"],
        )
        metric = MetricObservationModel(
            metric_observation_id="metric-observation-1",
            metric_name="m6.groundedness",
            metric_definition_revision="metric:test@1",
            value=1.0,
            unit="ratio",
            direction="higher_is_better",
            measurement_source="deterministic_evaluator",
            case_run_id=case_run.case_run_id,
            subject_ref="decision:test",
            evidence_refs_json=["evidence:test"],
            metadata_json={},
            created_at=NOW,
        )
        session.add_all([deployment, suite, case, run, case_run, metric])
    return engine, factory


@pytest.mark.asyncio
async def test_product_observatory_run_drills_into_cases_metrics_and_refs() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/observatory/proof/runs/run-1")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["run"]["benchmark_run_id"] == "run-1"
        assert body["run"]["deployment_revision_id"] == "deployment:test"
        assert body["deployment"]["git_commit"] == "deadbeef"
        assert body["deployment"]["configuration_digest"] == "b" * 64
        assert body["run"]["case_count"] == 1
        assert body["run"]["passed_case_count"] == 1
        assert body["cases"][0]["target_refs"] == ["object:test"]
        assert body["cases"][0]["execution_profile"] == "VERIFY"
        assert body["cases"][0]["decision_ref"] == "decision:test"
        assert body["cases"][0]["replay_checkpoint_ref"] == "checkpoint:test"
        assert body["cases"][0]["artifact_refs"] == ["artifact:test"]
        assert body["metrics"][0]["metric_name"] == "m6.groundedness"
        assert body["metrics"][0]["evidence_refs"] == ["evidence:test"]
    finally:
        await engine.dispose()
