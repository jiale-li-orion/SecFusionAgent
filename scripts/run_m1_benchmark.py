from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import exists, func, select
from sqlalchemy.orm import aliased

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
    SourceDeliveryCoverageReport,
    SourceDeliveryKey,
    monitoring_latency_report,
    source_coverage_report,
    source_delivery_coverage,
)
from packages.evaluation.m1_status import (
    render_m1_status_markdown,
    update_m1_readme_status,
)
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.contracts import AcquisitionTrigger
from packages.sources.inventory import load_source_inventory
from packages.sources.storage.models import SourceModel


class M1ExpectedEventManifest(BaseModel):
    manifest_id: str = Field(min_length=1)
    provider_snapshot_ref: str = Field(min_length=1)
    captured_at: datetime
    window_start: datetime
    window_end: datetime
    events: list[SourceDeliveryKey]

    @field_validator("captured_at", "window_start", "window_end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("M1 expected-event timestamps must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_manifest(self) -> M1ExpectedEventManifest:
        if self.window_end <= self.window_start:
            raise ValueError("expected-event window_end must be after window_start")
        if self.captured_at < self.window_end:
            raise ValueError("provider snapshot must be captured at or after window_end")
        if not self.provider_snapshot_ref.startswith(("provider-snapshot:", "artifact:")):
            raise ValueError(
                "provider_snapshot_ref must be an independent provider-snapshot: or artifact: ref"
            )
        if len(set(self.events)) != len(self.events):
            raise ValueError("expected-event manifest contains duplicate SourceDeliveryKey values")
        return self


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
    prior_run = aliased(AcquisitionRunModel)
    current_run = aliased(AcquisitionRunModel)
    had_prior_scheduled_success = exists().where(
        prior_run.source_id == ObservationModel.source_id,
        prior_run.trigger == AcquisitionTrigger.SCHEDULED.value,
        prior_run.status.in_(("success", "no_change")),
        prior_run.created_at < current_run.created_at,
    )
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
            ObservationModel.updated_at,
            ObservationModel.observed_at,
            SourceModel.time_semantics,
            current_run.run_id,
            current_run.created_at.label("run_created_at"),
            current_run.started_at.label("run_started_at"),
            current_run.finished_at.label("run_finished_at"),
            current_run.cursor_in,
            current_run.cursor_out,
            had_prior_scheduled_success.label("had_prior_scheduled_success"),
            earliest_commit.c.committed_at,
        )
        .join(current_run, current_run.run_id == ObservationModel.acquisition_run_id)
        .join(SourceModel, SourceModel.source_id == ObservationModel.source_id)
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


def _steady_state_monitoring_rows(rows: Sequence[Any]) -> list[Any]:
    return [row for row in rows if _monitoring_exclusion_reason(row) is None]


def _is_backfill_cursor(cursor: Any) -> bool:
    return isinstance(cursor, dict) and cursor.get("backfill_pending") is True


def _monitoring_exclusion_reason(row: Any) -> str | None:
    if _is_backfill_cursor(row.cursor_in):
        return "input_backfill"
    if _is_backfill_cursor(row.cursor_out):
        return "output_backfill"
    if not bool(row.cursor_in) and not bool(row.had_prior_scheduled_success):
        return "bootstrap"
    return None


def _monitoring_event_time(row: Any) -> datetime | None:
    semantics = row.time_semantics if isinstance(row.time_semantics, dict) else {}
    if "updated_at" in semantics and row.updated_at is not None:
        return row.updated_at
    return row.published_at


def _isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _seconds_between(later: datetime | None, earlier: datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds()


def _monitoring_row_diagnostic(row: Any) -> dict[str, Any]:
    event_time = _monitoring_event_time(row)
    return {
        "observation_id": row.observation_id,
        "source_id": row.source_id,
        "external_object_id": row.external_object_id,
        "run_id": row.run_id,
        "exclusion_reason": _monitoring_exclusion_reason(row),
        "event_time": _isoformat_or_none(event_time),
        "observed_at": row.observed_at.isoformat(),
        "committed_at": row.committed_at.isoformat(),
        "run_created_at": row.run_created_at.isoformat(),
        "run_started_at": _isoformat_or_none(row.run_started_at),
        "run_finished_at": _isoformat_or_none(row.run_finished_at),
        "end_to_end_seconds": _seconds_between(row.committed_at, event_time),
        "provider_discovery_seconds": _seconds_between(row.observed_at, event_time),
        "ingestion_commit_seconds": _seconds_between(row.committed_at, row.observed_at),
        "queue_dispatch_seconds": _seconds_between(row.run_started_at, row.run_created_at),
    }


def _duration_distribution(values: Sequence[float | None]) -> dict[str, float | int | None]:
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return {"count": 0, "p50_seconds": None, "p95_seconds": None, "max_seconds": None}

    def nearest_rank(percentile: float) -> float:
        rank = max(1, ceil(percentile * len(ordered)))
        return ordered[rank - 1]

    return {
        "count": len(ordered),
        "p50_seconds": nearest_rank(0.50),
        "p95_seconds": nearest_rank(0.95),
        "max_seconds": ordered[-1],
    }


def _monitoring_diagnostics(rows: Sequence[Any]) -> dict[str, Any]:
    exclusion_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    eligible_source_counts: dict[str, int] = {}
    excluded: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for row in rows:
        source_counts[row.source_id] = source_counts.get(row.source_id, 0) + 1
        diagnostic = _monitoring_row_diagnostic(row)
        reason = diagnostic["exclusion_reason"]
        if isinstance(reason, str):
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
            excluded.append(diagnostic)
        else:
            eligible_source_counts[row.source_id] = (
                eligible_source_counts.get(row.source_id, 0) + 1
            )
            eligible.append(diagnostic)
    excluded.sort(
        key=lambda item: (
            item["end_to_end_seconds"] is None,
            -(item["end_to_end_seconds"] or 0.0),
            item["observation_id"],
        )
    )
    eligible_timing = {
        field: _duration_distribution(
            [
                item.get(field) if isinstance(item.get(field), (int, float)) else None
                for item in eligible
            ]
        )
        for field in (
            "end_to_end_seconds",
            "provider_discovery_seconds",
            "queue_dispatch_seconds",
            "ingestion_commit_seconds",
        )
    }
    return {
        "raw_candidate_count": len(rows),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "source_candidate_counts": dict(sorted(source_counts.items())),
        "eligible_source_counts": dict(sorted(eligible_source_counts.items())),
        "eligible_timing": eligible_timing,
        "eligible_samples": eligible,
        "excluded_examples": excluded[:10],
    }


def _scheduled_observation_query(window_start: datetime, window_end: datetime):
    return (
        select(
            ObservationModel.source_id,
            ObservationModel.external_object_id,
            ObservationModel.external_revision,
            ObservationModel.content_hash,
        )
        .where(
            ObservationModel.acquisition_trigger == AcquisitionTrigger.SCHEDULED.value,
            ObservationModel.observed_at >= window_start,
            ObservationModel.observed_at < window_end,
        )
        .order_by(ObservationModel.observed_at, ObservationModel.observation_id)
    )


def _scheduled_observation_query_for_sources(
    window_start: datetime,
    window_end: datetime,
    source_ids: set[str],
):
    if not source_ids:
        raise ValueError("delivery observation query requires at least one source id")
    return _scheduled_observation_query(window_start, window_end).where(
        ObservationModel.source_id.in_(sorted(source_ids))
    )


def _accepted_delivery_keys(
    rows: Sequence[Any],
    expected_keys: list[SourceDeliveryKey],
) -> list[SourceDeliveryKey]:
    expected_by_identity: dict[tuple[str, str], list[SourceDeliveryKey]] = {}
    for item in expected_keys:
        expected_by_identity.setdefault(
            (item.source_id, item.external_object_id), []
        ).append(item)

    accepted: list[SourceDeliveryKey] = []
    for row in rows:
        candidates = expected_by_identity.get((row.source_id, row.external_object_id), [])
        matched = next(
            (
                item
                for item in candidates
                if (
                    item.external_revision is not None
                    and row.external_revision == item.external_revision
                )
                or (
                    item.content_hash is not None
                    and row.content_hash == item.content_hash
                )
            ),
            None,
        )
        if matched is not None:
            accepted.append(matched)
            continue
        if row.external_revision:
            accepted.append(
                SourceDeliveryKey(
                    source_id=row.source_id,
                    external_object_id=row.external_object_id,
                    external_revision=row.external_revision,
                )
            )
        else:
            accepted.append(
                SourceDeliveryKey(
                    source_id=row.source_id,
                    external_object_id=row.external_object_id,
                    content_hash=row.content_hash,
                )
            )
    return accepted


def _finalize_delivery_report(
    *,
    expected_keys: list[SourceDeliveryKey],
    accepted_keys: list[SourceDeliveryKey],
    now: datetime,
    deadline: datetime,
) -> tuple[SourceDeliveryCoverageReport | None, str, SourceDeliveryCoverageReport]:
    provisional = source_delivery_coverage(
        expected_keys=expected_keys,
        accepted_keys=accepted_keys,
    )
    if provisional.missed_items == 0:
        return provisional, "evaluated_complete", provisional
    if now >= deadline:
        return provisional, "evaluated_deadline", provisional
    return None, "awaiting_delivery_grace", provisional


async def _run(
    *,
    window_start: datetime,
    window_end: datetime,
    suite_id: str,
    suite_revision: int,
    deployment_revision_id: str | None,
    expected_events_manifest: M1ExpectedEventManifest | None = None,
    delivery_grace_seconds: int = 6 * 60 * 60,
) -> dict[str, Any]:
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    if expected_events_manifest is not None and (
        expected_events_manifest.window_start != window_start
        or expected_events_manifest.window_end != window_end
    ):
        raise ValueError("expected-event manifest window must exactly match benchmark window")
    if delivery_grace_seconds < 0:
        raise ValueError("delivery_grace_seconds must be non-negative")
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    now = datetime.now(UTC)
    delivery_deadline = (
        window_end + timedelta(seconds=delivery_grace_seconds)
        if expected_events_manifest is not None
        else None
    )
    delivery_observation_end = (
        min(now, delivery_deadline) if delivery_deadline is not None else None
    )
    inventory = load_source_inventory()
    coverage = source_coverage_report(inventory)

    try:
        async with factory() as session:
            rows = (
                await session.execute(_monitoring_latency_query(window_start, window_end))
            ).all()
            delivery_rows = (
                (
                    await session.execute(
                        _scheduled_observation_query_for_sources(
                            window_start,
                            delivery_observation_end or window_end,
                            {
                                item.source_id
                                for item in expected_events_manifest.events
                            },
                        )
                    )
                ).all()
                if expected_events_manifest is not None
                else []
            )

        steady_state_rows = _steady_state_monitoring_rows(rows)
        monitoring_diagnostics = _monitoring_diagnostics(rows)
        samples = [
            MonitoringLatencySample(
                sample_id=row.observation_id,
                published_at=_monitoring_event_time(row),
                available_at=row.committed_at,
            )
            for row in steady_state_rows
        ]
        latency = monitoring_latency_report(samples)
        delivery = None
        provisional_delivery = None
        delivery_status = "not_evaluated_without_expected_event_manifest"
        accepted_delivery_keys: list[SourceDeliveryKey] = []
        expected_manifest_digest: str | None = None
        if expected_events_manifest is not None:
            accepted_delivery_keys = _accepted_delivery_keys(
                delivery_rows,
                expected_events_manifest.events,
            )
            if delivery_deadline is None:
                raise RuntimeError("delivery deadline missing for expected-event manifest")
            delivery, delivery_status, provisional_delivery = _finalize_delivery_report(
                expected_keys=expected_events_manifest.events,
                accepted_keys=accepted_delivery_keys,
                now=now,
                deadline=delivery_deadline,
            )
            expected_manifest_digest = _digest(
                expected_events_manifest.model_dump(mode="json")
            )
        sample_manifest = [
            {
                "observation_id": row.observation_id,
                "source_id": row.source_id,
                "external_object_id": row.external_object_id,
                "external_revision": row.external_revision,
                "content_hash": row.content_hash,
                "event_time": _isoformat_or_none(_monitoring_event_time(row)),
                "event_time_semantics": (
                    "updated_at"
                    if isinstance(row.time_semantics, dict)
                    and "updated_at" in row.time_semantics
                    and row.updated_at is not None
                    else "published_at"
                ),
                "committed_at": row.committed_at.isoformat(),
                "acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
                "steady_state": True,
            }
            for row in steady_state_rows
        ]
        sample_digest = _digest(sample_manifest)
        inventory_bytes = await asyncio.to_thread(Path("config/source-inventory.json").read_bytes)
        inventory_digest = sha256(inventory_bytes).hexdigest()
        gold_revision = "m1:" + _digest(
            {
                "source_inventory": inventory_digest,
                "latency_samples": sample_digest,
                "expected_event_manifest": expected_manifest_digest,
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
        delivery_case_id: str | None = None
        if expected_events_manifest is not None:
            delivery_case_id = (
                "m1-delivery-window:"
                f"{window_start.strftime('%Y%m%dT%H%M%SZ')}:"
                f"{window_end.strftime('%Y%m%dT%H%M%SZ')}"
            )
            case_refs.append(f"{delivery_case_id}@{suite_revision}")

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
                        "latency_semantics": (
                            "source_event_time->earliest_knowledge_committed_at"
                        ),
                        "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
                        "steady_state_only": True,
                        "backfill_exclusion": "cursor_in_or_cursor_out.backfill_pending",
                        "raw_candidate_count": len(rows),
                        "excluded_nonsteady_count": len(rows) - len(steady_state_rows),
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
            if expected_events_manifest is not None and delivery_case_id is not None:
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=delivery_case_id,
                        case_revision=suite_revision,
                        input={
                            "window_start": window_start.isoformat(),
                            "window_end": window_end.isoformat(),
                            "delivery_grace_seconds": delivery_grace_seconds,
                            "delivery_deadline": (
                                delivery_deadline.isoformat()
                                if delivery_deadline is not None
                                else None
                            ),
                            "provider_snapshot_ref": (
                                expected_events_manifest.provider_snapshot_ref
                            ),
                            "expected_event_manifest_id": (
                                expected_events_manifest.manifest_id
                            ),
                        },
                        execution_profile="offline_scorer",
                        target_refs=["scheduled-observations"],
                        expected_behavior={
                            "expected_items": len(expected_events_manifest.events),
                            "observation_scope": "manifest_source_ids_only",
                            "delivery_grace_seconds": delivery_grace_seconds,
                            "identity": (
                                "source_id + external_object_id + "
                                "external_revision|content_hash"
                            ),
                        },
                        gold_ref=(
                            f"m1-expected-events:{expected_manifest_digest}"
                        ),
                        fixture_refs=[expected_events_manifest.provider_snapshot_ref],
                        tags=["m1", "source-delivery", "fixed-window"],
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
                evaluator_revision="m1-monitoring-v4",
                scoring_profile={
                    "latency_semantics": (
                        "source_event_time->earliest_knowledge_committed_at"
                    ),
                    "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
                    "steady_state_only": True,
                    "raw_candidate_count": len(rows),
                    "excluded_nonsteady_count": len(rows) - len(steady_state_rows),
                    "steady_state_rule": (
                        "NOT cursor_in.backfill_pending AND "
                        "NOT cursor_out.backfill_pending AND "
                        "(cursor_in_nonempty OR prior_successful_scheduled_run)"
                    ),
                    "event_time_rule": (
                        "Observation.updated_at when Source.time_semantics declares updated_at; "
                        "otherwise Observation.published_at"
                    ),
                    "source_inventory_digest": inventory_digest,
                    "latency_sample_digest": sample_digest,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "source_delivery_coverage": (
                        delivery_status
                        if expected_events_manifest is not None
                        else "not_evaluated_without_expected_event_manifest"
                    ),
                    "delivery_grace_seconds": delivery_grace_seconds,
                    "delivery_deadline": (
                        delivery_deadline.isoformat()
                        if delivery_deadline is not None
                        else None
                    ),
                    "delivery_observation_end": (
                        delivery_observation_end.isoformat()
                        if delivery_observation_end is not None
                        else None
                    ),
                    "delivery_observation_scope": "manifest_source_ids_only",
                    "expected_event_manifest_digest": expected_manifest_digest,
                    "provider_snapshot_ref": (
                        expected_events_manifest.provider_snapshot_ref
                        if expected_events_manifest is not None
                        else None
                    ),
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
            if expected_events_manifest is not None and delivery_case_id is not None:
                delivery_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{delivery_case_id}@{suite_revision}",
                    now=now,
                )
                if delivery is not None:
                    await store.observe_metric(
                        session,
                        case_run_id=delivery_run.case_run_id,
                        metric_name="m1.source_delivery_coverage",
                        value=delivery.coverage,
                        direction=MetricDirection.HIGHER_IS_BETTER,
                        measurement_source=MeasurementSource.EXACT,
                        subject_ref=f"m1-delivery:{expected_manifest_digest}",
                        evidence_refs=[expected_events_manifest.provider_snapshot_ref],
                        metadata={
                            "expected_items": delivery.expected_items,
                            "accepted_expected_items": delivery.accepted_expected_items,
                            "missed_items": delivery.missed_items,
                            "unexpected_items": delivery.unexpected_items,
                            "delivery_status": delivery_status,
                            "delivery_grace_seconds": delivery_grace_seconds,
                            "delivery_deadline": (
                                delivery_deadline.isoformat()
                                if delivery_deadline is not None
                                else None
                            ),
                            "delivery_observation_end": (
                                delivery_observation_end.isoformat()
                                if delivery_observation_end is not None
                                else None
                            ),
                            "accepted_keys": [
                                item.model_dump(mode="json")
                                for item in accepted_delivery_keys
                            ],
                        },
                        now=now,
                    )
                await store.finish_case_run(
                    session,
                    delivery_run.case_run_id,
                    status=(
                        BenchmarkCaseRunStatus.PASSED
                        if delivery is not None
                        else BenchmarkCaseRunStatus.SKIPPED
                    ),
                    failure_class=(None if delivery is not None else delivery_status),
                    artifact_refs=[expected_events_manifest.provider_snapshot_ref],
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
                if latency.evaluable_coverage is None:
                    raise RuntimeError(
                        "non-empty M1 latency denominator has no evaluable coverage"
                    )
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
            "raw_latency_candidate_count": len(rows),
            "excluded_nonsteady_count": len(rows) - len(steady_state_rows),
            "monitoring_diagnostics": monitoring_diagnostics,
            "latency": latency.model_dump(mode="json"),
            "eligible_acquisition_trigger": AcquisitionTrigger.SCHEDULED.value,
            "source_delivery_coverage": (
                delivery.model_dump(mode="json") if delivery is not None else "not_evaluated"
            ),
            "source_delivery_status": delivery_status,
            "source_delivery_provisional": (
                provisional_delivery.model_dump(mode="json")
                if provisional_delivery is not None
                else None
            ),
            "delivery_grace_seconds": delivery_grace_seconds,
            "delivery_deadline": (
                delivery_deadline.isoformat() if delivery_deadline is not None else None
            ),
            "delivery_observation_end": (
                delivery_observation_end.isoformat()
                if delivery_observation_end is not None
                else None
            ),
            "expected_event_manifest_id": (
                expected_events_manifest.manifest_id
                if expected_events_manifest is not None
                else None
            ),
            "expected_event_manifest_digest": expected_manifest_digest,
            "provider_snapshot_ref": (
                expected_events_manifest.provider_snapshot_ref
                if expected_events_manifest is not None
                else None
            ),
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
    parser.add_argument("--expected-events-manifest", type=Path)
    parser.add_argument("--delivery-grace-seconds", type=int, default=6 * 60 * 60)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--readme-status",
        type=Path,
        help="replace the generated M1 status block in this README",
    )
    args = parser.parse_args()
    expected_events_manifest = (
        M1ExpectedEventManifest.model_validate_json(
            args.expected_events_manifest.read_text(encoding="utf-8")
        )
        if args.expected_events_manifest is not None
        else None
    )
    result = asyncio.run(
        _run(
            window_start=args.window_start,
            window_end=args.window_end,
            suite_id=args.suite_id,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
            expected_events_manifest=expected_events_manifest,
            delivery_grace_seconds=args.delivery_grace_seconds,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    status_markdown = render_m1_status_markdown(result)
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(status_markdown, encoding="utf-8")
    if args.readme_status is not None:
        update_m1_readme_status(args.readme_status, status_markdown)
    print(rendered, end="")


if __name__ == "__main__":
    main()
