from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from apps.application.views.world import (
    HotBugListView,
    HotBugView,
    WorldCategoryHealthView,
    WorldHealthCountsView,
    WorldOverviewView,
    WorldSeriesPointView,
    WorldSourceHealthView,
    WorldWindowView,
)
from packages.intelligence.hot_cache.contracts import HotBugCacheEntry
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.shared.config import get_settings

router = APIRouter(prefix="/api/v1/world", tags=["world"])

_DATA_PLANE_SNAPSHOT = Path("benchmarks/data-plane/current.json")
_WINDOW_KEYS = ("1h", "6h", "24h", "168h")


@router.get("/overview", response_model=WorldOverviewView)
async def world_overview() -> WorldOverviewView:
    payload = _load_snapshot()
    source_health = payload.get("source_health", {})
    counts = source_health.get("counts", {})
    by_category = source_health.get("by_category", {})
    rolling = payload.get("rolling_windows", {})
    pipeline_state = payload.get("pipeline_state", {})
    storage = payload.get("storage", {})
    artifact_store = storage.get("artifact_store", {})

    return WorldOverviewView(
        schema_version=str(payload.get("schema_version", "unknown")),
        generated_at=payload["generated_at"],
        source_health=WorldHealthCountsView(
            healthy=int(counts.get("healthy", 0)),
            degraded=int(counts.get("degraded", 0)),
            blocked=int(counts.get("blocked", 0)),
        ),
        healthy_rate=float(source_health.get("healthy_rate", 0.0)),
        overdue_sources=int(source_health.get("overdue_sources", 0)),
        backfill_pending_sources=int(source_health.get("backfill_pending_sources", 0)),
        categories=[
            WorldCategoryHealthView(
                category=category,
                healthy=int(states.get("healthy", 0)),
                degraded=int(states.get("degraded", 0)),
                blocked=int(states.get("blocked", 0)),
            )
            for category, states in by_category.items()
        ],
        sources=[
            WorldSourceHealthView.model_validate(item)
            for item in source_health.get("sources", [])
            if isinstance(item, dict)
        ],
        windows={
            key: _window_view(rolling[key].get("scheduled_monitoring", {}))
            for key in _WINDOW_KEYS
            if key in rolling
        },
        hourly_series=[
            WorldSeriesPointView.model_validate(item)
            for item in payload.get("hourly_series", [])
        ],
        category_hourly_series={
            str(category): [
                WorldSeriesPointView.model_validate(item)
                for item in series
            ]
            for category, series in payload.get("category_hourly_series", {}).items()
            if isinstance(series, list)
        },
        outbox_delivered=int(pipeline_state.get("outbox", {}).get("delivered", 0)),
        lexical_ready_documents=int(
            pipeline_state.get("document_index", {}).get("lexical_ready", 0)
        ),
        artifact_store_status=artifact_store.get("status"),
        public_epoch_artifact_integrity_rate=artifact_store.get("public_epoch", {}).get(
            "integrity_rate"
        ),
    )


@router.get("/hot", response_model=HotBugListView)
async def hot_world(limit: int = Query(default=18, ge=1, le=64)) -> HotBugListView:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_hot_cache_url)
    try:
        entries = await RedisHotBugCache(redis).list_ranked(limit=limit)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hot Bug working set is unavailable",
        ) from exc
    finally:
        await redis.aclose()

    return HotBugListView(items=[_hot_view(entry) for entry in entries])


@router.get("/hot/{source_id}/{external_object_id:path}", response_model=HotBugView)
async def hot_world_detail(
    source_id: str,
    external_object_id: str,
) -> HotBugView:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_hot_cache_url)
    try:
        entry = await RedisHotBugCache(redis).get_entry(source_id, external_object_id)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hot Bug working set is unavailable",
        ) from exc
    finally:
        await redis.aclose()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hot Bug object not found",
        )
    return _hot_view(entry)


def _load_snapshot() -> dict[str, Any]:
    try:
        return json.loads(_DATA_PLANE_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data Plane operational snapshot is unavailable",
        ) from exc


def _window_view(metrics: dict[str, Any]) -> WorldWindowView:
    return WorldWindowView(
        observations=int(metrics.get("observations", 0)),
        fresh_external_changes=int(metrics.get("fresh_external_changes", 0)),
        backfill_observations=int(metrics.get("backfill_observations", 0)),
        canonical_writes=int(metrics.get("canonical_writes", 0)),
        document_revisions=int(metrics.get("document_revisions", 0)),
        document_chunks=int(metrics.get("document_chunks", 0)),
        document_text_bytes=int(metrics.get("document_text_bytes", 0)),
        scheduled_runs=int(metrics.get("scheduled_runs", 0)),
        scheduled_run_success_rate=metrics.get("scheduled_run_success_rate"),
        provider_boundary_failure_rate=metrics.get("provider_boundary_failure_rate"),
        runtime_owned_failure_rate=metrics.get("runtime_owned_failure_rate"),
        queue_delay_p95_seconds=metrics.get("queue_delay_p95_seconds"),
        execution_p95_seconds=metrics.get("execution_p95_seconds"),
        fresh_knowledge_latency_p95_seconds=metrics.get("fresh_knowledge_latency_p95_seconds"),
        fresh_contributing_sources=int(metrics.get("fresh_contributing_sources", 0)),
        fresh_contributing_categories=int(metrics.get("fresh_contributing_categories", 0)),
        fresh_top1_source_share=metrics.get("fresh_top1_source_share"),
        evidence_artifacts=int(metrics.get("evidence_artifacts", 0)),
        evidence_artifacts_present=int(metrics.get("evidence_artifacts_present", 0)),
        evidence_integrity_rate=metrics.get("evidence_integrity_rate"),
        evidence_physical_bytes=int(metrics.get("evidence_physical_bytes", 0)),
    )


def _hot_view(entry: HotBugCacheEntry) -> HotBugView:
    record = entry.record
    projection = record.projection
    affected_raw = projection.get("affected_products")
    affected_products = (
        [str(item) for item in affected_raw if isinstance(item, str)]
        if isinstance(affected_raw, list)
        else []
    )
    return HotBugView(
        source_id=record.source_id,
        external_object_id=record.external_object_id,
        external_revision=record.external_revision,
        cve_id=_string_or_none(projection.get("cve_id")),
        title=_string_or_none(projection.get("title")),
        description=_string_or_none(projection.get("description_en")),
        status=_string_or_none(projection.get("status")),
        cvss_score=_float_or_none(projection.get("cvss_score")),
        cvss_severity=_string_or_none(projection.get("cvss_severity")),
        affected_products=affected_products,
        canonical_url=record.canonical_url,
        updated_at=record.updated_at,
        fetched_at=record.fetched_at,
        changed_fields=record.changed_fields,
        priority_signals=record.priority_signals,
        access_count=entry.access_count,
        active=entry.active,
        pinned=entry.pinned,
        ttl_seconds=entry.ttl_seconds,
    )


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
