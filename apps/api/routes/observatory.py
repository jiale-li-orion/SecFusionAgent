from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select

from apps.api.dependencies import SessionDep
from apps.application.queries.system import get_delivery_backlogs
from apps.application.views.observatory import (
    CompetitionProofView,
    ProofCaseRunView,
    ProofDeploymentRevisionView,
    ProofMetricObservationView,
    ProofMetricView,
    ProofRunDetailView,
    ProofRunSummaryView,
    ProofTargetView,
)
from apps.application.views.system import SystemDependencyView, SystemOverviewView
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseModel,
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    DeploymentRevisionModel,
    MetricObservationModel,
)
from packages.shared.config import get_settings

router = APIRouter(prefix="/api/v1/observatory", tags=["observatory"])

_COMPETITION_REPORT = Path("benchmarks/competition/current.json")
_EVAL_INFRA = Path("benchmarks/evaluation-infra/current.json")
_HEADLINE_METRICS = {
    "m1.monitoring.within_6h_rate",
    "m1.source_delivery_coverage",
    "m3.true_positive",
    "m3.false_positive",
    "m3.false_negative",
    "m3.micro_precision",
    "m3.micro_recall",
    "m6.answer_accuracy",
    "m6.groundedness",
    "m6.citation_correctness",
    "m6.citation_completeness",
    "m6.interactive_latency_seconds",
    "m6.session_context_chain_correctness",
    "m6.session_target_carry_correctness",
    "m6.session_retrieval_invocation_coverage",
    "m6.session_retrieval_reuse_rate",
    "engineering.fault_recovery_success",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _redis_ping(component: str, url: str) -> SystemDependencyView:
    client = Redis.from_url(url, decode_responses=True)
    started = perf_counter()
    try:
        await client.ping()
    except RedisError as exc:
        return SystemDependencyView(
            component=component,
            status="unhealthy",
            latency_ms=round((perf_counter() - started) * 1000, 2),
            detail_code=type(exc).__name__,
        )
    finally:
        await client.aclose()
    return SystemDependencyView(
        component=component,
        status="healthy",
        latency_ms=round((perf_counter() - started) * 1000, 2),
    )


async def _task_stream_pending(
    redis: Redis,
    *,
    stream_name: str,
    group_name: str,
) -> int | None:
    try:
        pending = await redis.xpending(stream_name, group_name)
    except RedisError:
        return None
    if isinstance(pending, dict):
        value = pending.get("pending")
        return int(value) if value is not None else None
    return None


@router.get("/system", response_model=SystemOverviewView)
async def system_overview(session: SessionDep) -> SystemOverviewView:
    settings = get_settings()
    outbox, task_delivery = await get_delivery_backlogs(session)

    redis_results = await asyncio.gather(
        _redis_ping("redis_broker", settings.redis_broker_url),
        _redis_ping("redis_hot_cache", settings.redis_hot_cache_url),
        _redis_ping("redis_task_bus", settings.redis_task_bus_url),
    )
    task_bus = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    try:
        stream_pending = await _task_stream_pending(
            task_bus,
            stream_name=settings.task_event_stream_name,
            group_name=settings.task_event_scheduler_group,
        )
    finally:
        await task_bus.aclose()

    dependencies = [
        SystemDependencyView(component="postgresql", status="healthy"),
        *redis_results,
    ]
    runtime_policy_status = "healthy" if settings.runtime_policy_path.is_file() else "missing"
    model_provider_status = (
        "configured" if settings.model_base_url and settings.model_name else "disabled"
    )
    unhealthy = any(item.status == "unhealthy" for item in dependencies)
    degraded = runtime_policy_status != "healthy" or any(
        item.status == "degraded" for item in dependencies
    )
    overall = "unhealthy" if unhealthy else "degraded" if degraded else "healthy"
    return SystemOverviewView(
        generated_at=_utc_now(),
        overall=overall,
        dependencies=dependencies,
        outbox=outbox,
        task_event_delivery=task_delivery,
        task_event_stream_pending=stream_pending,
        runtime_policy_status=runtime_policy_status,
        model_provider_status=model_provider_status,
        measurement_boundaries={
            "worker_process_health": "unavailable_no_heartbeat_contract",
            "model_provider_status": "configuration_only_not_live_probe",
            "artifact_store_health": "use_world_operational_snapshot",
        },
    )


@router.get("/proof", response_model=CompetitionProofView)
async def competition_proof(session: SessionDep) -> CompetitionProofView:
    report = _load_json(_COMPETITION_REPORT)
    infra = _load_json(_EVAL_INFRA)
    run_ids = list(report.get("benchmark_run_ids", []))

    completed_runs = int(
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkRunModel)
            .where(
                BenchmarkRunModel.benchmark_run_id.in_(run_ids),
                BenchmarkRunModel.status == "completed",
            )
        )
        or 0
    )
    passed_cases = int(
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkCaseRunModel)
            .where(
                BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids),
                BenchmarkCaseRunModel.status == "passed",
            )
        )
        or 0
    )

    groups = list(infra.get("metric_groups", []))
    run_models = list(
        await session.scalars(
            select(BenchmarkRunModel)
            .where(BenchmarkRunModel.benchmark_run_id.in_(run_ids))
            .order_by(BenchmarkRunModel.started_at)
        )
    )
    case_models = list(
        await session.scalars(
            select(BenchmarkCaseRunModel).where(
                BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids)
            )
        )
    )
    case_counts: dict[str, tuple[int, int]] = {}
    for item in case_models:
        count, passed = case_counts.get(item.benchmark_run_id, (0, 0))
        case_counts[item.benchmark_run_id] = (
            count + 1,
            passed + (1 if item.status == "passed" else 0),
        )
    return CompetitionProofView(
        report_id=str(report["report_id"]),
        report_digest=str(report["report_digest"]),
        deployment_revision_id=str(report["deployment_revision_id"]),
        generated_at=report["generated_at"],
        benchmark_runs_completed=completed_runs,
        case_runs_passed=passed_cases,
        registered_core_metrics=int(infra.get("registered_core_metric_count", 0)),
        observed_core_metrics=int(infra.get("observed_metric_name_count", 0)),
        metric_groups=int(infra.get("contract_group_count", len(groups))),
        observed_metric_groups=sum(1 for group in groups if group.get("status") == "observed"),
        partial_metric_groups=sum(1 for group in groups if group.get("status") == "partial"),
        unevaluated_core_metrics=[
            name
            for name, count in infra.get("observed_metric_counts", {}).items()
            if int(count) == 0
        ],
        headline_metrics=[
            ProofMetricView(
                metric_name=str(metric["metric_name"]),
                value=float(metric["value"]),
                unit=metric.get("unit"),
                direction=str(metric.get("direction", "informational")),
            )
            for metric in report.get("metrics", [])
            if metric.get("metric_name") in _HEADLINE_METRICS
        ],
        target_checks=[
            ProofTargetView(
                target_name=str(item["target_name"]),
                requirement=str(item["requirement"]),
                metric_name=str(item["metric_name"]),
                observed_value=float(item["observed_value"]),
                threshold=float(item["threshold"]),
                comparator=str(item["comparator"]),
                status=str(item["status"]),
            )
            for item in report.get("target_checks", [])
        ],
        runs=[
            _proof_run_summary(
                model,
                case_count=case_counts.get(model.benchmark_run_id, (0, 0))[0],
                passed_case_count=case_counts.get(model.benchmark_run_id, (0, 0))[1],
            )
            for model in run_models
        ],
    )


@router.get("/proof/runs/{run_id}", response_model=ProofRunDetailView)
async def competition_proof_run(run_id: str, session: SessionDep) -> ProofRunDetailView:
    run = await session.get(BenchmarkRunModel, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="benchmark run not found")
    deployment = await session.get(DeploymentRevisionModel, run.deployment_revision_id)
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="benchmark run deployment revision missing",
        )
    cases = list(
        await session.scalars(
            select(BenchmarkCaseRunModel)
            .where(BenchmarkCaseRunModel.benchmark_run_id == run_id)
            .order_by(BenchmarkCaseRunModel.started_at)
        )
    )
    case_versions = (
        list(
            await session.scalars(
                select(BenchmarkCaseModel).where(
                    BenchmarkCaseModel.case_version_id.in_(
                        [item.case_version_id for item in cases]
                    )
                )
            )
        )
        if cases
        else []
    )
    case_by_version = {item.case_version_id: item for item in case_versions}
    case_ids = [item.case_run_id for item in cases]
    metrics = (
        list(
            await session.scalars(
                select(MetricObservationModel)
                .where(MetricObservationModel.case_run_id.in_(case_ids))
                .order_by(MetricObservationModel.created_at, MetricObservationModel.metric_name)
            )
        )
        if case_ids
        else []
    )
    passed = sum(1 for item in cases if item.status == "passed")
    return ProofRunDetailView(
        run=_proof_run_summary(run, case_count=len(cases), passed_case_count=passed),
        deployment=ProofDeploymentRevisionView(
            deployment_revision_id=deployment.deployment_revision_id,
            git_commit=deployment.git_commit,
            container_image_digest=deployment.container_image_digest,
            schema_revision=deployment.schema_revision,
            source_inventory_hash=deployment.source_inventory_hash,
            vocabulary_revision=deployment.vocabulary_revision,
            policy_revision=deployment.policy_revision,
            capability_registry_revision=deployment.capability_registry_revision,
            skill_registry_revision=deployment.skill_registry_revision,
            model_provider_revision=deployment.model_provider_revision,
            configuration_digest=deployment.configuration_digest,
            created_at=deployment.created_at,
        ),
        cases=[
            ProofCaseRunView(
                case_run_id=item.case_run_id,
                case_ref=item.case_ref,
                target_refs=list(
                    case_by_version[item.case_version_id].target_refs_json
                )
                if item.case_version_id in case_by_version
                else [],
                execution_profile=(
                    case_by_version[item.case_version_id].execution_profile
                    if item.case_version_id in case_by_version
                    else None
                ),
                status=item.status,
                failure_class=item.failure_class,
                task_run_id=item.task_run_id,
                execution_id=item.execution_id,
                decision_ref=item.decision_ref,
                replay_checkpoint_ref=item.replay_checkpoint_ref,
                artifact_refs=list(item.artifact_refs_json),
                started_at=item.started_at,
                finished_at=item.finished_at,
            )
            for item in cases
        ],
        metrics=[
            ProofMetricObservationView(
                metric_observation_id=item.metric_observation_id,
                metric_name=item.metric_name,
                value=item.value,
                unit=item.unit,
                direction=item.direction,
                measurement_source=item.measurement_source,
                case_run_id=item.case_run_id,
                subject_ref=item.subject_ref,
                evidence_refs=list(item.evidence_refs_json),
                created_at=item.created_at,
            )
            for item in metrics
        ],
    )


def _proof_run_summary(
    model: BenchmarkRunModel,
    *,
    case_count: int,
    passed_case_count: int,
) -> ProofRunSummaryView:
    return ProofRunSummaryView(
        benchmark_run_id=model.benchmark_run_id,
        suite_ref=model.suite_ref,
        deployment_revision_id=model.deployment_revision_id,
        world_snapshot_ref=model.world_snapshot_ref,
        status=model.status,
        execution_mode=model.execution_mode,
        environment=model.environment,
        started_at=model.started_at,
        finished_at=model.finished_at,
        case_count=case_count,
        passed_case_count=passed_case_count,
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"observatory artifact unavailable: {path.name}",
        ) from exc
