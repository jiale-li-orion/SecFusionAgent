from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
    MetricDirection,
)
from packages.evaluation.m1_m3 import (
    MonitoringLatencySample,
    monitoring_latency_report,
    source_coverage_report,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.contracts import AcquisitionTrigger
from packages.sources.inventory import load_source_inventory


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("window timestamp must include timezone")
    return parsed.astimezone(UTC)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


def _monitoring_latency_query(window_start: datetime, window_end: datetime):
    earliest_commit = (
        select(
            KnowledgeRevisionModel.cause_observation_id.label("observation_id"),
            func.min(KnowledgeRevisionModel.committed_at).label("committed_at"),
        )
        .where(KnowledgeRevisionModel.cause_observation_id.is_not(None))
        .group_by(KnowledgeRevisionModel.cause_observation_id)
        .subquery()
    )
    return (
        select(
            ObservationModel.observation_id,
            ObservationModel.source_id,
            ObservationModel.external_object_id,
            ObservationModel.external_revision,
            ObservationModel.content_hash,
            ObservationModel.published_at,
            earliest_commit.c.committed_at,
        )
        .join(
            earliest_commit,
            earliest_commit.c.observation_id == ObservationModel.observation_id,
        )
        .where(
            ObservationModel.acquisition_trigger == AcquisitionTrigger.SCHEDULED.value,
            earliest_commit.c.committed_at >= window_start,
            earliest_commit.c.committed_at < window_end,
        )
        .order_by(earliest_commit.c.committed_at, ObservationModel.observation_id)
    )


async def _run(
    *,
    window_start: datetime,
    window_end: datetime,
    suite_id: str,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, Any]:
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    now = datetime.now(UTC)
    inventory = load_source_inventory()
    coverage = source_coverage_report(inventory)

    try:
        async with factory() as session:
            rows = (
                await session.execute(_monitoring_latency_query(window_start, window_end))
            ).all()

        samples = [
            MonitoringLatencySample(
                sample_id=row.observation_id,
                published_at=row.published_at,
                available_at=row.committed_at,
            )
            for row in rows
        ]
        latency = monitoring_latency_report(samples)
        sample_manifest = [
            {
                "observation_id": row.observation_id,
                "source_id": row.source_id,
                "external_object_id": row.external_object_id,
                "external_revision": row.external_revision,
                "content_hash": row.content_hash,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "committed_at": row.committed_at.isoformat(),
                "acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
            }
            for row in rows
        ]
        sample_digest = _digest(sample_manifest)
        inventory_bytes = await asyncio.to_thread(Path("config/source-inventory.json").read_bytes)
        inventory_digest = sha256(inventory_bytes).hexdigest()
        gold_revision = "m1:" + _digest(
            {
                "source_inventory": inventory_digest,
                "latency_samples": sample_digest,
            }
        )

        portfolio_case_id = f"m1-source-portfolio:{inventory_digest[:16]}"
        latency_case_id = (
            "m1-latency-window:"
            f"{window_start.strftime('%Y%m%dT%H%M%SZ')}:"
            f"{window_end.strftime('%Y%m%dT%H%M%SZ')}"
        )
        case_refs = [
            f"{portfolio_case_id}@{suite_revision}",
            f"{latency_case_id}@{suite_revision}",
        ]

        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            await store.register_case(
                session,
                BenchmarkCase(
                    case_id=portfolio_case_id,
                    case_revision=suite_revision,
                    input={"source_inventory": "config/source-inventory.json"},
                    execution_profile="offline_scorer",
                    target_refs=["source-portfolio"],
                    expected_behavior={
                        "taxonomy_size": 8,
                        "competition_category_target": 7,
                    },
                    gold_ref=f"source-inventory:{inventory_digest}",
                    tags=["m1", "source-coverage", "deterministic"],
                    latency_class="offline",
                    replay_tier="R0",
                    created_at=now,
                ),
            )
            await store.register_case(
                session,
                BenchmarkCase(
                    case_id=latency_case_id,
                    case_revision=suite_revision,
                    input={
                        "window_start": window_start.isoformat(),
                        "window_end": window_end.isoformat(),
                    },
                    execution_profile="offline_scorer",
                    target_refs=["observations", "knowledge-revisions"],
                    expected_behavior={
                        "latency_semantics": "published_at->earliest_knowledge_committed_at",
                        "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
                        "sample_count": len(sample_manifest),
                        "evaluable_sample_count": latency.evaluable_samples,
                    },
                    gold_ref=f"m1-latency-samples:{sample_digest}",
                    tags=["m1", "monitoring-latency", "fixed-window"],
                    latency_class="offline",
                    replay_tier="R0",
                    created_at=now,
                ),
            )
            suite = BenchmarkSuite(
                suite_id=suite_id,
                suite_revision=suite_revision,
                domain=BenchmarkDomain.M1_MONITORING,
                purpose="M1 source-category coverage and fixed-window monitoring latency",
                case_refs=case_refs,
                gold_revision=gold_revision,
                evaluator_revision="m1-monitoring-v1",
                scoring_profile={
                    "latency_semantics": "published_at->earliest_knowledge_committed_at",
                    "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
                    "source_inventory_digest": inventory_digest,
                    "latency_sample_digest": sample_digest,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "source_delivery_coverage": "not_evaluated_without_expected_event_manifest",
                },
                created_at=now,
            )
            await store.register_suite(session, suite)
            run = await store.start_run(
                session,
                suite_ref=f"{suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.OFFLINE_SCORER,
                environment=settings.environment,
                now=now,
            )

            portfolio_run = await store.start_case_run(
                session,
                benchmark_run_id=run.benchmark_run_id,
                case_ref=f"{portfolio_case_id}@{suite_revision}",
                now=now,
            )
            await store.observe_metric(
                session,
                case_run_id=portfolio_run.case_run_id,
                metric_name="m1.source_category_count",
                value=float(coverage.source_category_count),
                direction=MetricDirection.HIGHER_IS_BETTER,
                measurement_source=MeasurementSource.EXACT,
                subject_ref="source-portfolio",
                evidence_refs=[f"source-inventory:{inventory_digest}"],
                metadata={
                    "supported": [item.value for item in coverage.supported_source_categories],
                    "unsupported": [item.value for item in coverage.unsupported_source_categories],
                },
                now=now,
            )
            await store.finish_case_run(
                session,
                portfolio_run.case_run_id,
                status=BenchmarkCaseRunStatus.PASSED,
                now=now,
            )

            latency_run = await store.start_case_run(
                session,
                benchmark_run_id=run.benchmark_run_id,
                case_ref=f"{latency_case_id}@{suite_revision}",
                now=now,
            )
            if latency.total_samples:
                await store.observe_metric(
                    session,
                    case_run_id=latency_run.case_run_id,
                    metric_name="m1.monitoring.evaluable_coverage",
                    value=latency.evaluable_coverage,
                    direction=MetricDirection.HIGHER_IS_BETTER,
                    measurement_source=MeasurementSource.EXACT,
                    subject_ref=f"m1-window:{sample_digest}",
                    evidence_refs=[f"m1-latency-samples:{sample_digest}"],
                    metadata={
                        "total_samples": latency.total_samples,
                        "evaluable_samples": latency.evaluable_samples,
                    },
                    now=now,
                )
                for metric_name, value, direction in (
                    (
                        "m1.monitoring.p50_seconds",
                        latency.p50_seconds,
                        MetricDirection.LOWER_IS_BETTER,
                    ),
                    (
                        "m1.monitoring.p95_seconds",
                        latency.p95_seconds,
                        MetricDirection.LOWER_IS_BETTER,
                    ),
                    (
                        "m1.monitoring.max_seconds",
                        latency.max_seconds,
                        MetricDirection.LOWER_IS_BETTER,
                    ),
                    (
                        "m1.monitoring.within_6h_rate",
                        latency.within_6h_rate,
                        MetricDirection.HIGHER_IS_BETTER,
                    ),
                ):
                    if value is None:
                        continue
                    await store.observe_metric(
                        session,
                        case_run_id=latency_run.case_run_id,
                        metric_name=metric_name,
                        value=value,
                        direction=direction,
                        measurement_source=MeasurementSource.EXACT,
                        subject_ref=f"m1-window:{sample_digest}",
                        evidence_refs=[f"m1-latency-samples:{sample_digest}"],
                        now=now,
                    )
            await store.finish_case_run(
                session,
                latency_run.case_run_id,
                status=(
                    BenchmarkCaseRunStatus.PASSED
                    if latency.total_samples
                    else BenchmarkCaseRunStatus.SKIPPED
                ),
                failure_class=(None if latency.total_samples else "no_scheduled_samples"),
                artifact_refs=[f"m1-latency-samples:{sample_digest}"],
                now=now,
            )
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )

        return {
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{suite_id}@{suite_revision}",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "source_category_count": coverage.source_category_count,
            "supported_source_categories": [
                item.value for item in coverage.supported_source_categories
            ],
            "latency_sample_digest": sample_digest,
            "latency": latency.model_dump(mode="json"),
            "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
            "source_delivery_coverage": "not_evaluated",
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen M1 monitoring benchmark")
    parser.add_argument("--window-start", required=True, type=_parse_datetime)
    parser.add_argument("--window-end", required=True, type=_parse_datetime)
    parser.add_argument("--suite-id", default="m1-monitoring-window")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(
        _run(
            window_start=args.window_start,
            window_end=args.window_end,
            suite_id=args.suite_id,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
