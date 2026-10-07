# ruff: noqa: E501
from __future__ import annotations

import argparse
import asyncio
import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import boto3
from sqlalchemy import text

from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.sources.inventory import load_source_inventory
from packages.sources.taxonomy import SOURCE_PORTFOLIO_CATEGORY_ORDER

PUBLIC_TIMEZONE = ZoneInfo("Asia/Singapore")
SUCCESS_STATUSES = {"success", "no_change"}
BLOCKED_STATUSES = {"auth_failed", "schema_changed", "provider_blocked"}
PROVIDER_BOUNDARY_FAILURE_STATUSES = {
    "fetch_failed",
    "rate_limited",
    "auth_failed",
    "schema_changed",
    "provider_blocked",
}
RUNTIME_OWNED_FAILURE_STATUSES = {
    "failed",
    "dependency_unavailable",
    "internal_error",
}
TERMINAL_FAILURE_STATUSES = (
    PROVIDER_BOUNDARY_FAILURE_STATUSES | RUNTIME_OWNED_FAILURE_STATUSES
)


def _ratio(num: int | float, den: int | float) -> float | None:
    return float(num) / float(den) if den else None


def _nearest_rank(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _event_class(
    *,
    observed_at: datetime,
    published_at: datetime | None,
    updated_at: datetime | None,
    cursor_in: dict[str, object],
    cursor_out: dict[str, object],
    fresh_seconds: int,
    recent_seconds: int,
) -> tuple[str, float | None]:
    if cursor_in.get("backfill_pending") is True or cursor_out.get("backfill_pending") is True:
        return "backfill", None
    event_time = updated_at or published_at
    if event_time is None:
        return "unclocked_first_seen", None
    age_seconds = (observed_at - event_time).total_seconds()
    if age_seconds < -300:
        return "clock_skew", age_seconds
    if age_seconds <= fresh_seconds:
        return "fresh", max(0.0, age_seconds)
    if age_seconds <= recent_seconds:
        return "recent_backlog", age_seconds
    return "old_first_seen", age_seconds


def _source_category_map() -> tuple[dict[str, str], dict[str, int]]:
    inventory = load_source_inventory()
    physical = inventory.physical_source_categories()
    categories = {
        source_id: inventory.measurement_category(source_id).value for source_id in physical
    }
    entry_counts = Counter(item.category for item in inventory.entries)
    return categories, dict(entry_counts)


def _artifact_inventory(settings: Any) -> tuple[dict[str, int], int, int]:
    if settings.artifact_store_backend == "filesystem":
        bucket_root = Path(settings.artifact_root) / settings.s3_bucket
        if not bucket_root.exists():
            return {}, 0, 0
        filesystem_uris: dict[str, int] = {}
        total_bytes = 0
        for path in bucket_root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            key = path.relative_to(bucket_root).as_posix()
            size = path.stat().st_size
            filesystem_uris[f"artifact://{settings.s3_bucket}/{key}"] = size
            filesystem_uris[f"s3://{settings.s3_bucket}/{key}"] = size
            total_bytes += size
        return filesystem_uris, total_bytes, len(filesystem_uris) // 2

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    s3_uris: dict[str, int] = {}
    total_bytes = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            size = int(item.get("Size", 0))
            s3_uris[f"s3://{settings.s3_bucket}/{key}"] = size
            total_bytes += size
    return s3_uris, total_bytes, len(s3_uris)


async def data_plane_status() -> dict[str, Any]:
    settings = get_settings()
    inventory = load_source_inventory()
    contract = inventory.monitoring_measurement
    epoch = contract.public_epoch.astimezone(UTC)
    category_by_source, entry_counts = _source_category_map()

    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            now = await session.scalar(text("SELECT now()"))
            assert isinstance(now, datetime)

            source_rows = (
                await session.execute(
                    text(
                        "SELECT source_id, enabled, schedule_policy FROM sources ORDER BY source_id"
                    )
                )
            ).all()
            latest_run_rows = (
                await session.execute(
                    text(
                        "SELECT DISTINCT ON (source_id) source_id,status,created_at,error_code "
                        "FROM acquisition_runs WHERE trigger='scheduled' "
                        "ORDER BY source_id,created_at DESC"
                    )
                )
            ).all()
            scheduled_sources = {
                str(source_id)
                for source_id, enabled, schedule_policy in source_rows
                if bool(enabled)
                and isinstance(schedule_policy, dict)
                and schedule_policy.get("enabled", True) is not False
            }
            executable_sources = {str(row[0]) for row in source_rows}

            state_rows = (
                await session.execute(
                    text(
                        "SELECT source_id, cursor, last_attempt_at, last_success_at, last_change_at, "
                        "next_due_at, consecutive_failures, backoff_until FROM source_state"
                    )
                )
            ).all()
            states = {str(row[0]): row for row in state_rows}

            run_rows = (
                await session.execute(
                    text(
                        "SELECT run_id, source_id, trigger, status, cursor_in, cursor_out, created_at, "
                        "started_at, finished_at, error_code FROM acquisition_runs "
                        "WHERE created_at >= :epoch ORDER BY created_at"
                    ),
                    {"epoch": epoch},
                )
            ).all()

            observation_rows = (
                await session.execute(
                    text(
                        "SELECT o.observation_id, o.source_id, o.acquisition_trigger, o.observed_at, "
                        "o.published_at, o.updated_at, r.cursor_in, r.cursor_out, "
                        "(SELECT min(k.committed_at) FROM knowledge_revisions k "
                        " WHERE k.cause_observation_id=o.observation_id) AS first_knowledge_commit "
                        "FROM observations o "
                        "LEFT JOIN acquisition_runs r ON r.run_id = o.acquisition_run_id "
                        "WHERE o.observed_at >= :epoch "
                        "ORDER BY o.observed_at"
                    ),
                    {"epoch": epoch},
                )
            ).all()

            write_rows = (
                await session.execute(
                    text(
                        "SELECT source_id, acquisition_trigger, committed_at, sum(write_count) FROM ("
                        "SELECT o.source_id, o.acquisition_trigger, k.committed_at, count(*) AS write_count "
                        "FROM objects x JOIN knowledge_revisions k ON k.revision=x.created_revision "
                        "JOIN observations o ON o.observation_id=k.cause_observation_id "
                        "WHERE k.committed_at>=:epoch "
                        "GROUP BY o.source_id,o.acquisition_trigger,k.committed_at "
                        "UNION ALL "
                        "SELECT o.source_id, o.acquisition_trigger, k.committed_at, count(*) FROM claims x "
                        "JOIN knowledge_revisions k ON k.revision=x.created_revision "
                        "JOIN observations o ON o.observation_id=k.cause_observation_id "
                        "WHERE k.committed_at>=:epoch "
                        "GROUP BY o.source_id,o.acquisition_trigger,k.committed_at "
                        "UNION ALL "
                        "SELECT o.source_id, o.acquisition_trigger, k.committed_at, count(*) FROM relations x "
                        "JOIN knowledge_revisions k ON k.revision=x.created_revision "
                        "JOIN observations o ON o.observation_id=k.cause_observation_id "
                        "WHERE k.committed_at>=:epoch "
                        "GROUP BY o.source_id,o.acquisition_trigger,k.committed_at"
                        ") q GROUP BY source_id, acquisition_trigger, committed_at"
                    ),
                    {"epoch": epoch},
                )
            ).all()

            document_rows = (
                await session.execute(
                    text(
                        "SELECT o.source_id, o.acquisition_trigger, dr.created_at, "
                        "count(dc.chunk_id), coalesce(sum(octet_length(dc.text)),0) "
                        "FROM document_revisions dr "
                        "JOIN observations o ON o.observation_id=dr.observation_id "
                        "LEFT JOIN document_chunks dc ON dc.document_revision_id=dr.document_revision_id "
                        "WHERE dr.created_at>=:epoch "
                        "GROUP BY o.source_id,o.acquisition_trigger,dr.document_revision_id,dr.created_at"
                    ),
                    {"epoch": epoch},
                )
            ).all()

            artifact_rows = (
                await session.execute(
                    text(
                        "SELECT o.source_id,o.acquisition_trigger,a.storage_uri,a.created_at "
                        "FROM evidence_artifacts a "
                        "JOIN observations o ON o.observation_id=a.observation_id"
                    )
                )
            ).all()
            outbox_rows = (
                await session.execute(
                    text(
                        "SELECT status,count(*) FROM outbox_events GROUP BY status ORDER BY status"
                    )
                )
            ).all()
            chunk_status_rows = (
                await session.execute(
                    text(
                        "SELECT index_status,count(*) FROM document_chunks "
                        "GROUP BY index_status ORDER BY index_status"
                    )
                )
            ).all()
            database_bytes = int(
                (await session.scalar(text("SELECT pg_database_size(current_database())"))) or 0
            )

        # Build event records outside the session; all required rows are detached scalar data.
        observations: list[dict[str, Any]] = []
        for row in observation_rows:
            (
                observation_id,
                source_id,
                trigger,
                observed_at,
                published_at,
                updated_at,
                cursor_in,
                cursor_out,
                knowledge_commit,
            ) = row
            observed_at = cast(datetime, observed_at)
            published_at = cast(datetime | None, published_at)
            updated_at = cast(datetime | None, updated_at)
            cursor_in = cast(dict[str, object] | None, cursor_in)
            cursor_out = cast(dict[str, object] | None, cursor_out)
            knowledge_commit = cast(datetime | None, knowledge_commit)
            event_class, discovery_latency = _event_class(
                observed_at=observed_at,
                published_at=published_at,
                updated_at=updated_at,
                cursor_in=cursor_in or {},
                cursor_out=cursor_out or {},
                fresh_seconds=contract.fresh_event_max_age_seconds,
                recent_seconds=contract.recent_event_max_age_seconds,
            )
            event_time = updated_at or published_at
            knowledge_latency = (
                (knowledge_commit - event_time).total_seconds()
                if event_time is not None and knowledge_commit is not None
                else None
            )
            observations.append(
                {
                    "observation_id": str(observation_id),
                    "source_id": str(source_id),
                    "category": category_by_source.get(str(source_id)),
                    "trigger": str(trigger),
                    "observed_at": observed_at,
                    "event_class": event_class,
                    "discovery_latency_seconds": discovery_latency,
                    "knowledge_latency_seconds": knowledge_latency,
                    "knowledge_revision_count": 1 if knowledge_commit is not None else 0,
                }
            )

        writes: list[dict[str, Any]] = [
            {
                "source_id": str(source_id),
                "category": category_by_source.get(str(source_id)),
                "trigger": str(trigger),
                "at": cast(datetime, committed_at),
                "count": int(cast(int, count)),
            }
            for source_id, trigger, committed_at, count in write_rows
        ]
        documents: list[dict[str, Any]] = [
            {
                "source_id": str(source_id),
                "category": category_by_source.get(str(source_id)),
                "trigger": str(trigger),
                "at": cast(datetime, created_at),
                "document_revisions": 1,
                "chunks": int(cast(int, chunk_count)),
                "text_bytes": int(cast(int, text_bytes)),
            }
            for source_id, trigger, created_at, chunk_count, text_bytes in document_rows
        ]
        scheduled_runs: list[dict[str, Any]] = [
            {
                "source_id": str(row[1]),
                "category": category_by_source.get(str(row[1])),
                "status": str(row[3]),
                "created_at": cast(datetime, row[6]),
                "started_at": cast(datetime | None, row[7]),
                "finished_at": cast(datetime | None, row[8]),
                "error_code": row[9],
            }
            for row in run_rows
            if str(row[2]) == "scheduled"
        ]

        def aggregate(cutoff: datetime, *, scheduled_only: bool) -> dict[str, Any]:
            obs = [
                item
                for item in observations
                if item["observed_at"] >= cutoff
                and (not scheduled_only or item["trigger"] == "scheduled")
            ]
            source_ids = {item["source_id"] for item in obs}
            runs = [item for item in scheduled_runs if item["created_at"] >= cutoff]
            relevant_writes = [
                item
                for item in writes
                if item["at"] >= cutoff
                and (
                    not scheduled_only
                    or (item["trigger"] == "scheduled" and item["source_id"] in source_ids)
                )
            ]
            relevant_docs = [
                item
                for item in documents
                if item["at"] >= cutoff and (not scheduled_only or item["trigger"] == "scheduled")
            ]
            class_counts = Counter(item["event_class"] for item in obs)
            fresh = [item for item in obs if item["event_class"] == "fresh"]
            fresh_by_source = Counter(item["source_id"] for item in fresh)
            discovery_latencies = [
                float(item["discovery_latency_seconds"])
                for item in fresh
                if item["discovery_latency_seconds"] is not None
            ]
            knowledge_latencies = [
                float(item["knowledge_latency_seconds"])
                for item in fresh
                if item["knowledge_latency_seconds"] is not None
                and item["knowledge_latency_seconds"] >= 0
            ]
            terminal_runs = [item for item in runs if item["status"] not in {"queued", "running"}]
            successful_runs = [item for item in terminal_runs if item["status"] in SUCCESS_STATUSES]
            changed_runs = [item for item in terminal_runs if item["status"] == "success"]
            failed_runs = [
                item for item in terminal_runs if item["status"] in TERMINAL_FAILURE_STATUSES
            ]
            provider_failed_runs = [
                item
                for item in terminal_runs
                if item["status"] in PROVIDER_BOUNDARY_FAILURE_STATUSES
            ]
            runtime_failed_runs = [
                item
                for item in terminal_runs
                if item["status"] in RUNTIME_OWNED_FAILURE_STATUSES
            ]
            terminal_status_counts = Counter(item["status"] for item in terminal_runs)
            queue_delays = [
                (item["started_at"] - item["created_at"]).total_seconds()
                for item in runs
                if item["started_at"] is not None
            ]
            execution_durations = [
                (item["finished_at"] - item["started_at"]).total_seconds()
                for item in terminal_runs
                if item["started_at"] is not None and item["finished_at"] is not None
            ]
            canonical_writes = sum(item["count"] for item in relevant_writes)
            chunk_count = sum(item["chunks"] for item in relevant_docs)
            text_bytes = sum(item["text_bytes"] for item in relevant_docs)
            document_revisions = sum(item["document_revisions"] for item in relevant_docs)
            source_counts = sorted(fresh_by_source.values(), reverse=True)
            fresh_categories = {item["category"] for item in fresh if item["category"] is not None}
            fresh_knowledge_commits = sum(item["knowledge_revision_count"] for item in fresh)
            elapsed_hours = max((now - cutoff).total_seconds() / 3600, 1 / 3600)

            def latency_sla_rate(limit_seconds: float) -> float | None:
                return _ratio(
                    sum(1 for value in knowledge_latencies if value <= limit_seconds),
                    len(knowledge_latencies),
                )

            return {
                "window_hours": elapsed_hours,
                "observations": len(obs),
                "fresh_external_changes": len(fresh),
                "fresh_changes_per_hour": len(fresh) / elapsed_hours,
                "fresh_share_of_observations": _ratio(len(fresh), len(obs)),
                "backfill_observations": class_counts["backfill"],
                "recent_backlog": class_counts["recent_backlog"],
                "old_first_seen": class_counts["old_first_seen"],
                "unclocked_first_seen": class_counts["unclocked_first_seen"],
                "clock_skew": class_counts["clock_skew"],
                "knowledge_revisions": sum(item["knowledge_revision_count"] for item in obs),
                "canonical_writes": canonical_writes,
                "document_revisions": document_revisions,
                "document_chunks": chunk_count,
                "document_text_bytes": text_bytes,
                "scheduled_runs": len(runs),
                "scheduled_runs_per_hour": len(runs) / elapsed_hours,
                "scheduled_terminal_runs": len(terminal_runs),
                "scheduled_successful_runs": len(successful_runs),
                "scheduled_changed_runs": len(changed_runs),
                "scheduled_failed_runs": len(failed_runs),
                "scheduled_run_success_rate": _ratio(len(successful_runs), len(terminal_runs)),
                "provider_boundary_failed_runs": len(provider_failed_runs),
                "provider_boundary_failure_rate": _ratio(
                    len(provider_failed_runs), len(terminal_runs)
                ),
                "runtime_owned_failed_runs": len(runtime_failed_runs),
                "runtime_owned_failure_rate": _ratio(
                    len(runtime_failed_runs), len(terminal_runs)
                ),
                "terminal_status_counts": dict(sorted(terminal_status_counts.items())),
                "change_poll_yield": _ratio(len(changed_runs), len(successful_runs)),
                "queue_delay_p50_seconds": _nearest_rank(queue_delays, 0.50),
                "queue_delay_p95_seconds": _nearest_rank(queue_delays, 0.95),
                "execution_p50_seconds": _nearest_rank(execution_durations, 0.50),
                "execution_p95_seconds": _nearest_rank(execution_durations, 0.95),
                "knowledge_revision_per_observation": _ratio(
                    sum(item["knowledge_revision_count"] for item in obs), len(obs)
                ),
                "fresh_knowledge_commit_rate": _ratio(fresh_knowledge_commits, len(fresh)),
                "canonical_writes_per_observation": _ratio(canonical_writes, len(obs)),
                "chunks_per_document_revision": _ratio(chunk_count, document_revisions),
                "fresh_discovery_latency_p50_seconds": _nearest_rank(discovery_latencies, 0.50),
                "fresh_discovery_latency_p95_seconds": _nearest_rank(discovery_latencies, 0.95),
                "fresh_knowledge_latency_p50_seconds": _nearest_rank(knowledge_latencies, 0.50),
                "fresh_knowledge_latency_p95_seconds": _nearest_rank(knowledge_latencies, 0.95),
                "fresh_knowledge_within_15m_rate": latency_sla_rate(15 * 60),
                "fresh_knowledge_within_1h_rate": latency_sla_rate(60 * 60),
                "fresh_knowledge_within_6h_rate": latency_sla_rate(6 * 60 * 60),
                "fresh_contributing_sources": len(fresh_by_source),
                "fresh_contributing_categories": len(fresh_categories),
                "fresh_top1_source_share": _ratio(source_counts[0], len(fresh))
                if source_counts
                else None,
                "fresh_top5_source_share": (
                    _ratio(sum(source_counts[:5]), len(fresh)) if source_counts else None
                ),
            }

        def aggregate_category(cutoff: datetime, category: str) -> dict[str, Any]:
            obs = [
                item
                for item in observations
                if item["observed_at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["category"] == category
            ]
            source_ids = {item["source_id"] for item in obs}
            runs = [
                item
                for item in scheduled_runs
                if item["created_at"] >= cutoff and item["category"] == category
            ]
            relevant_writes = [
                item
                for item in writes
                if item["at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["source_id"] in source_ids
            ]
            relevant_docs = [
                item
                for item in documents
                if item["at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["category"] == category
            ]
            classes = Counter(item["event_class"] for item in obs)
            fresh = [item for item in obs if item["event_class"] == "fresh"]
            fresh_by_source = Counter(item["source_id"] for item in fresh)
            fresh_categories = {item["category"] for item in fresh if item["category"] is not None}
            knowledge_latencies = [
                float(item["knowledge_latency_seconds"])
                for item in fresh
                if item["knowledge_latency_seconds"] is not None
                and item["knowledge_latency_seconds"] >= 0
            ]
            terminal = [item for item in runs if item["status"] not in {"queued", "running"}]
            successful = [item for item in terminal if item["status"] in SUCCESS_STATUSES]
            provider_failed = [
                item
                for item in terminal
                if item["status"] in PROVIDER_BOUNDARY_FAILURE_STATUSES
            ]
            runtime_failed = [
                item
                for item in terminal
                if item["status"] in RUNTIME_OWNED_FAILURE_STATUSES
            ]
            queue_delays = [
                (item["started_at"] - item["created_at"]).total_seconds()
                for item in runs
                if item["started_at"] is not None
            ]
            execution_durations = [
                (item["finished_at"] - item["started_at"]).total_seconds()
                for item in terminal
                if item["started_at"] is not None and item["finished_at"] is not None
            ]
            source_counts = sorted(fresh_by_source.values(), reverse=True)
            return {
                "observations": len(obs),
                "fresh_external_changes": classes["fresh"],
                "backfill_observations": classes["backfill"],
                "other_first_seen": len(obs) - classes["fresh"] - classes["backfill"],
                "canonical_writes": sum(item["count"] for item in relevant_writes),
                "document_chunks": sum(item["chunks"] for item in relevant_docs),
                "document_text_bytes": sum(item["text_bytes"] for item in relevant_docs),
                "scheduled_runs": len(runs),
                "scheduled_run_success_rate": _ratio(len(successful), len(terminal)),
                "provider_boundary_failure_rate": _ratio(len(provider_failed), len(terminal)),
                "runtime_owned_failure_rate": _ratio(len(runtime_failed), len(terminal)),
                "queue_delay_p95_seconds": _nearest_rank(queue_delays, 0.95),
                "execution_p95_seconds": _nearest_rank(execution_durations, 0.95),
                "fresh_knowledge_latency_p95_seconds": _nearest_rank(knowledge_latencies, 0.95),
                "fresh_contributing_sources": len(fresh_by_source),
                "fresh_contributing_categories": len(fresh_categories),
                "fresh_top1_source_share": (
                    _ratio(source_counts[0], len(fresh)) if source_counts else None
                ),
            }

        def aggregate_source(cutoff: datetime, source_id: str) -> dict[str, Any]:
            obs = [
                item
                for item in observations
                if item["observed_at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["source_id"] == source_id
            ]
            runs = [
                item
                for item in scheduled_runs
                if item["created_at"] >= cutoff and item["source_id"] == source_id
            ]
            relevant_writes = [
                item
                for item in writes
                if item["at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["source_id"] == source_id
            ]
            relevant_docs = [
                item
                for item in documents
                if item["at"] >= cutoff
                and item["trigger"] == "scheduled"
                and item["source_id"] == source_id
            ]
            classes = Counter(item["event_class"] for item in obs)
            terminal = [item for item in runs if item["status"] not in {"queued", "running"}]
            successful = [item for item in terminal if item["status"] in SUCCESS_STATUSES]
            changed = [item for item in terminal if item["status"] == "success"]
            provider_failed = [
                item
                for item in terminal
                if item["status"] in PROVIDER_BOUNDARY_FAILURE_STATUSES
            ]
            runtime_failed = [
                item
                for item in terminal
                if item["status"] in RUNTIME_OWNED_FAILURE_STATUSES
            ]
            return {
                "measurement_category": category_by_source.get(source_id),
                "observations": len(obs),
                "fresh_external_changes": classes["fresh"],
                "backfill_observations": classes["backfill"],
                "other_first_seen": len(obs) - classes["fresh"] - classes["backfill"],
                "canonical_writes": sum(item["count"] for item in relevant_writes),
                "document_chunks": sum(item["chunks"] for item in relevant_docs),
                "document_text_bytes": sum(item["text_bytes"] for item in relevant_docs),
                "scheduled_runs": len(runs),
                "scheduled_run_success_rate": _ratio(len(successful), len(terminal)),
                "provider_boundary_failure_rate": _ratio(len(provider_failed), len(terminal)),
                "runtime_owned_failure_rate": _ratio(len(runtime_failed), len(terminal)),
                "change_poll_yield": _ratio(len(changed), len(successful)),
            }

        rolling: dict[str, Any] = {}
        for hours in contract.rolling_windows_hours:
            cutoff = max(epoch, now - timedelta(hours=hours))
            key = f"{hours}h"
            rolling[key] = {
                "window_start": cutoff.isoformat(),
                "window_end": now.isoformat(),
                "scheduled_monitoring": aggregate(cutoff, scheduled_only=True),
                "all_ingestion": aggregate(cutoff, scheduled_only=False),
                "categories": {
                    category.value: aggregate_category(cutoff, category.value)
                    for category in SOURCE_PORTFOLIO_CATEGORY_ORDER
                },
                "sources": {
                    source_id: aggregate_source(cutoff, source_id)
                    for source_id in sorted(scheduled_sources)
                },
            }

        # Hour-aligned curve. Values are event counts in each bucket, not cumulative totals.
        bucket_start = _hour(epoch)
        bucket_end = _hour(now)
        buckets: list[datetime] = []
        cursor = bucket_start
        while cursor <= bucket_end:
            buckets.append(cursor)
            cursor += timedelta(hours=1)

        def hourly_row(start: datetime, category: str | None = None) -> dict[str, Any]:
            end = start + timedelta(hours=1)
            obs = [
                item
                for item in observations
                if start <= item["observed_at"] < end
                and item["trigger"] == "scheduled"
                and (category is None or item["category"] == category)
            ]
            source_ids = {item["source_id"] for item in obs}
            runs = [
                item
                for item in scheduled_runs
                if start <= item["created_at"] < end
                and (category is None or item["category"] == category)
            ]
            docs = [
                item
                for item in documents
                if start <= item["at"] < end
                and item["trigger"] == "scheduled"
                and (category is None or item["category"] == category)
            ]
            wr = [
                item
                for item in writes
                if start <= item["at"] < end
                and item["trigger"] == "scheduled"
                and item["source_id"] in source_ids
            ]
            classes = Counter(item["event_class"] for item in obs)
            fresh = [item for item in obs if item["event_class"] == "fresh"]
            fresh_by_source = Counter(item["source_id"] for item in fresh)
            fresh_categories = {
                item["category"] for item in fresh if item["category"] is not None
            }
            knowledge_latencies = [
                float(item["knowledge_latency_seconds"])
                for item in fresh
                if item["knowledge_latency_seconds"] is not None
                and item["knowledge_latency_seconds"] >= 0
            ]
            terminal = [item for item in runs if item["status"] not in {"queued", "running"}]
            successful = [item for item in terminal if item["status"] in SUCCESS_STATUSES]
            provider_failed = [
                item
                for item in terminal
                if item["status"] in PROVIDER_BOUNDARY_FAILURE_STATUSES
            ]
            runtime_failed = [
                item
                for item in terminal
                if item["status"] in RUNTIME_OWNED_FAILURE_STATUSES
            ]
            queue_delays = [
                (item["started_at"] - item["created_at"]).total_seconds()
                for item in runs
                if item["started_at"] is not None
            ]
            execution_durations = [
                (item["finished_at"] - item["started_at"]).total_seconds()
                for item in terminal
                if item["started_at"] is not None and item["finished_at"] is not None
            ]
            source_counts = sorted(fresh_by_source.values(), reverse=True)
            return {
                "hour_start": start.isoformat(),
                "observations": len(obs),
                "fresh_external_changes": classes["fresh"],
                "backfill_observations": classes["backfill"],
                "canonical_writes": sum(item["count"] for item in wr),
                "document_chunks": sum(item["chunks"] for item in docs),
                "document_text_bytes": sum(item["text_bytes"] for item in docs),
                "scheduled_runs": len(runs),
                "scheduled_run_success_rate": _ratio(len(successful), len(terminal)),
                "provider_boundary_failure_rate": _ratio(len(provider_failed), len(terminal)),
                "runtime_owned_failure_rate": _ratio(len(runtime_failed), len(terminal)),
                "queue_delay_p95_seconds": _nearest_rank(queue_delays, 0.95),
                "execution_p95_seconds": _nearest_rank(execution_durations, 0.95),
                "fresh_knowledge_latency_p95_seconds": _nearest_rank(
                    knowledge_latencies, 0.95
                ),
                "fresh_contributing_sources": len(fresh_by_source),
                "fresh_contributing_categories": len(fresh_categories),
                "fresh_top1_source_share": (
                    _ratio(source_counts[0], len(fresh)) if source_counts else None
                ),
            }

        hourly_series = [hourly_row(start) for start in buckets]
        category_hourly_series = {
            category.value: [hourly_row(start, category.value) for start in buckets]
            for category in SOURCE_PORTFOLIO_CATEGORY_ORDER
        }
        latest_by_source: dict[str, dict[str, Any]] = {
            str(source_id): {
                "source_id": str(source_id),
                "status": str(status),
                "created_at": created_at,
                "error_code": error_code,
            }
            for source_id, status, created_at, error_code in latest_run_rows
        }
        active_run_sources = {
            item["source_id"] for item in scheduled_runs if item["status"] in {"queued", "running"}
        }
        source_health: list[dict[str, Any]] = []
        health_counts: Counter[str] = Counter()
        for source_id in sorted(scheduled_sources):
            state = states.get(source_id)
            latest = latest_by_source.get(source_id)
            cursor_value = state[1] if state is not None and isinstance(state[1], dict) else {}
            next_due_at = state[5] if state is not None else None
            consecutive_failures = int(state[6] if state is not None else 0)
            backoff_until = state[7] if state is not None else None
            backoff_active = backoff_until is not None and backoff_until > now
            overdue = bool(
                next_due_at is not None
                and next_due_at
                < now - timedelta(seconds=max(settings.scheduler_tick_seconds * 3, 30))
                and not backoff_active
                and source_id not in active_run_sources
            )
            latest_status = latest["status"] if latest is not None else None
            if latest_status in BLOCKED_STATUSES:
                health = "blocked"
            elif overdue or consecutive_failures > 0 or latest_status not in SUCCESS_STATUSES:
                health = "degraded" if latest is not None else "warming"
            elif latest is None:
                health = "warming"
            else:
                health = "healthy"
            health_counts[health] += 1
            source_health.append(
                {
                    "source_id": source_id,
                    "measurement_category": category_by_source.get(source_id),
                    "health": health,
                    "latest_scheduled_status": latest_status,
                    "consecutive_failures": consecutive_failures,
                    "backfill_pending": cursor_value.get("backfill_pending") is True,
                    "last_success_at": _iso(state[3] if state is not None else None),
                    "next_due_at": _iso(next_due_at),
                    "backoff_until": _iso(backoff_until),
                    "overdue": overdue,
                    "latest_error_code": latest.get("error_code") if latest else None,
                }
            )

        category_health: dict[str, dict[str, int]] = {}
        for category in SOURCE_PORTFOLIO_CATEGORY_ORDER:
            counter: Counter[str] = Counter(
                item["health"]
                for item in source_health
                if item["measurement_category"] == category.value
            )
            category_health[category.value] = dict(sorted(counter.items()))

        category_taxonomy: dict[str, Any] = {}
        for category in SOURCE_PORTFOLIO_CATEGORY_ORDER:
            value = category.value
            physical_sources = {
                source_id for source_id, mapped in category_by_source.items() if mapped == value
            }
            category_taxonomy[value] = {
                "catalog_entries": int(entry_counts.get(value, 0)),
                "measurement_sources": len(physical_sources),
                "scheduled_monitors": len(physical_sources & scheduled_sources),
                "on_demand_or_resolver_sources": len(physical_sources - scheduled_sources),
            }

        try:
            physical_uri_sizes, physical_bytes, physical_object_count = await asyncio.to_thread(
                _artifact_inventory, settings
            )
            physical_uris = set(physical_uri_sizes)
            referenced_all = {str(uri) for _, _, uri, _ in artifact_rows}
            referenced_epoch = {
                str(uri)
                for _, _, uri, created_at in artifact_rows
                if cast(datetime, created_at) >= epoch
            }
            for _key, window in rolling.items():
                cutoff = datetime.fromisoformat(str(window["window_start"]))
                window_artifacts = [
                    (str(source_id), str(trigger), str(uri), cast(datetime, created_at))
                    for source_id, trigger, uri, created_at in artifact_rows
                    if cast(datetime, created_at) >= cutoff
                ]
                scheduled_artifacts = [item for item in window_artifacts if item[1] == "scheduled"]
                scheduled_present = [
                    item for item in scheduled_artifacts if item[2] in physical_uri_sizes
                ]
                scheduled = window["scheduled_monitoring"]
                scheduled["evidence_artifacts"] = len(scheduled_artifacts)
                scheduled["evidence_artifacts_present"] = len(scheduled_present)
                scheduled["evidence_integrity_rate"] = _ratio(
                    len(scheduled_present), len(scheduled_artifacts)
                )
                scheduled["evidence_physical_bytes"] = sum(
                    physical_uri_sizes[item[2]] for item in scheduled_present
                )

                for category in SOURCE_PORTFOLIO_CATEGORY_ORDER:
                    category_items = [
                        item
                        for item in scheduled_artifacts
                        if category_by_source.get(item[0]) == category.value
                    ]
                    category_present = [
                        item for item in category_items if item[2] in physical_uri_sizes
                    ]
                    category_flow = window["categories"][category.value]
                    category_flow["evidence_artifacts"] = len(category_items)
                    category_flow["evidence_artifacts_present"] = len(category_present)
                    category_flow["evidence_integrity_rate"] = _ratio(
                        len(category_present), len(category_items)
                    )
                    category_flow["evidence_physical_bytes"] = sum(
                        physical_uri_sizes[item[2]] for item in category_present
                    )

                for source_id, source_flow in window["sources"].items():
                    source_items = [item for item in scheduled_artifacts if item[0] == source_id]
                    source_present = [
                        item for item in source_items if item[2] in physical_uri_sizes
                    ]
                    source_flow["evidence_artifacts"] = len(source_items)
                    source_flow["evidence_artifacts_present"] = len(source_present)
                    source_flow["evidence_integrity_rate"] = _ratio(
                        len(source_present), len(source_items)
                    )
                    source_flow["evidence_physical_bytes"] = sum(
                        physical_uri_sizes[item[2]] for item in source_present
                    )
            artifact_integrity = {
                "status": "available",
                "backend": settings.artifact_store_backend,
                "physical_objects": physical_object_count,
                "physical_bytes": physical_bytes,
                "all_corpus": {
                    "referenced_objects": len(referenced_all),
                    "present_objects": len(referenced_all & physical_uris),
                    "integrity_rate": _ratio(
                        len(referenced_all & physical_uris), len(referenced_all)
                    ),
                },
                "public_epoch": {
                    "referenced_objects": len(referenced_epoch),
                    "present_objects": len(referenced_epoch & physical_uris),
                    "integrity_rate": _ratio(
                        len(referenced_epoch & physical_uris), len(referenced_epoch)
                    ),
                },
            }
        except Exception as exc:  # operator metric: dependency failure must remain visible
            artifact_integrity = {
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            }

        scheduled_categories = {
            category_by_source[source_id]
            for source_id in scheduled_sources
            if source_id in category_by_source
        }
        overdue_sources = sum(1 for item in source_health if item["overdue"])
        backfill_pending_sources = sum(1 for item in source_health if item["backfill_pending"])
        healthy_sources = health_counts["healthy"]
        return {
            "schema_version": "1",
            "generated_at": now.isoformat(),
            "public_monitoring_epoch": epoch.isoformat(),
            "public_monitoring_epoch_local": epoch.astimezone(PUBLIC_TIMEZONE).isoformat(),
            "measurement_contract": {
                "monitoring_traffic_trigger": "scheduled",
                "pre_epoch_semantics": "bootstrap_corpus_prefill_excluded_from_public_runtime_metrics",
                "event_time": "updated_at ?? published_at",
                "fresh_event_max_age_seconds": contract.fresh_event_max_age_seconds,
                "recent_event_max_age_seconds": contract.recent_event_max_age_seconds,
                "measurement_category": "exactly_one_category_per_executable_source",
            },
            "taxonomy": {
                "portfolio_categories": len(SOURCE_PORTFOLIO_CATEGORY_ORDER),
                "catalog_entries": len(inventory.entries),
                "executable_sources": len(executable_sources),
                "scheduled_monitors": len(scheduled_sources),
                "scheduled_categories": len(scheduled_categories),
                "categories": category_taxonomy,
            },
            "source_health": {
                "counts": dict(sorted(health_counts.items())),
                "healthy_rate": _ratio(healthy_sources, len(scheduled_sources)),
                "overdue_sources": overdue_sources,
                "backfill_pending_sources": backfill_pending_sources,
                "by_category": category_health,
                "sources": source_health,
            },
            "pipeline_state": {
                "outbox": {str(status): int(cast(int, count)) for status, count in outbox_rows},
                "document_index": {
                    str(status): int(cast(int, count)) for status, count in chunk_status_rows
                },
            },
            "storage": {
                "postgres_database_bytes": database_bytes,
                "artifact_store": artifact_integrity,
            },
            "rolling_windows": rolling,
            "hourly_series": hourly_series,
            "category_hourly_series": category_hourly_series,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect and export long-running data-plane metrics"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = asyncio.run(data_plane_status())
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
