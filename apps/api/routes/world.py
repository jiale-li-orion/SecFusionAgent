from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from apps.api.dependencies import SessionDep
from apps.application.queries.world import list_world_knowledge_changes, world_source_names
from apps.application.queries.world_formation import read_world_formation
from apps.application.views.world import (
    HotBugListView,
    HotBugView,
    WorldCategoryHealthView,
    WorldFormationView,
    WorldHealthCountsView,
    WorldIncidentCandidateListView,
    WorldIncidentCandidateView,
    WorldKnowledgeChangeListView,
    WorldOverviewView,
    WorldSeriesPointView,
    WorldSourceHealthView,
    WorldStoryListView,
    WorldWindowView,
)
from packages.intelligence.hot_cache.contracts import HotBugCacheEntry
from packages.intelligence.hot_cache.redis import RedisHotBugCache
from packages.intelligence.incident.contracts import IncidentCandidate, SignalItem
from packages.intelligence.incident.relevance import is_presentable_incident_signal
from packages.monitoring.data_plane_status import data_plane_status
from packages.shared.config import get_settings

router = APIRouter(prefix="/api/v1/world", tags=["world"])

_WINDOW_KEYS = ("1h", "6h", "24h", "168h")
_WORLD_OVERVIEW_TTL_SECONDS = 15.0
_WORLD_OVERVIEW_MAX_AGE_SECONDS = 60.0
_WORLD_OVERVIEW_READ_TIMEOUT_SECONDS = 10.0
_world_overview_cache: tuple[float, dict[str, Any]] | None = None
_world_overview_lock = asyncio.Lock()
_world_overview_refresh: asyncio.Task[dict[str, Any]] | None = None
_logger = logging.getLogger(__name__)


@router.get("/overview", response_model=WorldOverviewView)
async def world_overview() -> WorldOverviewView:
    payload = await _live_overview_payload()
    source_health = payload.get("source_health", {})
    counts = source_health.get("counts", {})
    by_category = source_health.get("by_category", {})
    rolling = payload.get("rolling_windows", {})
    pipeline_state = payload.get("pipeline_state", {})
    storage = payload.get("storage", {})
    artifact_store = storage.get("artifact_store", {})
    names = world_source_names()

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
            WorldSourceHealthView.model_validate(
                {**item, "source_name": names.get(str(item.get("source_id", "")))}
            )
            for item in source_health.get("sources", [])
            if isinstance(item, dict)
        ],
        windows={
            key: _window_view(rolling[key].get("scheduled_monitoring", {}))
            for key in _WINDOW_KEYS
            if key in rolling
        },
        hourly_series=[
            WorldSeriesPointView.model_validate(item) for item in payload.get("hourly_series", [])
        ],
        category_hourly_series={
            str(category): [WorldSeriesPointView.model_validate(item) for item in series]
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


@router.get("/knowledge-changes", response_model=WorldKnowledgeChangeListView)
async def world_knowledge_changes(
    session: SessionDep,
    limit: int = Query(default=12, ge=1, le=64),
) -> WorldKnowledgeChangeListView:
    return await list_world_knowledge_changes(session, limit=limit)


@router.get("/formation", response_model=WorldFormationView)
async def world_formation(session: SessionDep) -> WorldFormationView:
    return await read_world_formation(session)


@router.get("/stories", response_model=WorldStoryListView)
async def world_stories(
    request: Request,
    limit: int = Query(default=10, ge=4, le=18),
) -> WorldStoryListView:
    return await request.app.state.world_story_reader.read(limit=limit)


@router.get("/incident-candidates", response_model=WorldIncidentCandidateListView)
async def world_incident_candidates(
    limit: int = Query(default=24, ge=1, le=64),
) -> WorldIncidentCandidateListView:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_hot_cache_url)
    try:
        cursor = 0
        keys: list[bytes] = []
        while True:
            cursor, batch = await redis.scan(cursor, match="incident:cluster:*", count=256)
            keys.extend(batch)
            if cursor == 0:
                break
        raw_candidates = await redis.mget(keys) if keys else []
        candidates = [
            IncidentCandidate.model_validate_json(raw) for raw in raw_candidates if raw is not None
        ]
        candidates.sort(
            key=lambda item: (item.watch_priority, item.last_material_change),
            reverse=True,
        )
        candidates = [item for item in candidates if item.signal_ids]
        raw_signals = (
            await redis.mget([f"incident:signal:{item.signal_ids[-1]}" for item in candidates])
            if candidates
            else []
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Incident candidate working set is unavailable",
        ) from exc
    finally:
        await redis.aclose()

    presentable = [
        (candidate, signal)
        for candidate, raw in zip(candidates, raw_signals, strict=True)
        if candidate.promotion_state == "candidate"
        if raw is not None
        if (signal := SignalItem.model_validate_json(raw))
        if is_presentable_incident_signal(signal)
    ]
    names = world_source_names()
    return WorldIncidentCandidateListView(
        total=len(presentable),
        unfiltered_total=len(candidates),
        total_signals=sum(len(item.signal_ids) for item, _ in presentable),
        multi_source_candidates=sum(item.independent_source_count > 1 for item, _ in presentable),
        anchored_candidates=sum(bool(item.anchor_set) for item, _ in presentable),
        items=[
            WorldIncidentCandidateView(
                candidate_id=item.candidate_id,
                signal_id=signal.signal_id,
                incident_type=item.incident_type,
                promotion_state=item.promotion_state,
                headline=signal.title,
                summary=signal.summary,
                source_id=signal.source_id,
                source_role=signal.source_role.value,
                source_name=names.get(signal.source_id),
                canonical_url=signal.canonical_url,
                published_at=signal.published_at,
                observed_at=signal.observed_at,
                signal_count=len(item.signal_ids),
                independent_source_count=item.independent_source_count,
                anchor_count=sum(len(values) for values in item.anchor_set.values()),
                watch_priority=item.watch_priority,
                pinned=item.pinned,
                last_material_change=item.last_material_change,
                next_poll_at=item.next_poll_at,
                unresolved_question_count=len(item.unresolved_questions),
            )
            for item, signal in presentable[:limit]
        ],
    )


@router.get("/hot", response_model=HotBugListView)
async def hot_world(limit: int = Query(default=18, ge=1, le=64)) -> HotBugListView:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_hot_cache_url)
    try:
        cache = RedisHotBugCache(redis)
        entries, resident_total = await asyncio.gather(
            cache.list_ranked(limit=limit),
            cache.resident_count(),
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hot Bug working set is unavailable",
        ) from exc
    finally:
        await redis.aclose()

    names = world_source_names()
    return HotBugListView(
        resident_total=resident_total,
        items=[_hot_view(entry, names.get(entry.record.source_id)) for entry in entries],
    )


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
    return _hot_view(entry, world_source_names().get(entry.record.source_id))


async def _live_overview_payload() -> dict[str, Any]:
    if _world_overview_cache is None:
        return await _wait_for_overview_refresh()
    cached_at, payload = _world_overview_cache
    age = _overview_age(cached_at, payload)
    if age >= _WORLD_OVERVIEW_MAX_AGE_SECONDS:
        # After idle traffic or failed refreshes, wait for one shared current read.
        # A successful response must not retain an arbitrarily old measurement.
        return await _wait_for_overview_refresh()
    if age >= _WORLD_OVERVIEW_TTL_SECONDS:
        _overview_refresh_task()
    # generated_at remains the original measurement time; the UI can show its age.
    return payload


async def _wait_for_overview_refresh() -> dict[str, Any]:
    try:
        payload = await asyncio.wait_for(
            asyncio.shield(_overview_refresh_task()), _WORLD_OVERVIEW_READ_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live Data Plane aggregation timed out",
        ) from exc
    if _overview_age(monotonic(), payload) >= _WORLD_OVERVIEW_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live Data Plane measurement is too old",
        )
    return payload


def _overview_age(cached_at: float, payload: dict[str, Any]) -> float:
    measured_at = datetime.fromisoformat(str(payload["generated_at"]).replace("Z", "+00:00"))
    return max(monotonic() - cached_at, (datetime.now(UTC) - measured_at).total_seconds())


def _overview_refresh_task() -> asyncio.Task[dict[str, Any]]:
    global _world_overview_refresh

    if _world_overview_refresh is None or _world_overview_refresh.done():
        _world_overview_refresh = asyncio.create_task(_refresh_overview_payload())
        _world_overview_refresh.add_done_callback(_observe_refresh)
    return _world_overview_refresh


def _observe_refresh(task: asyncio.Task[dict[str, Any]]) -> None:
    if not task.cancelled() and (error := task.exception()) is not None:
        _logger.warning("World overview refresh failed; retaining measured snapshot: %s", error)


def _aggregate_overview() -> dict[str, Any]:
    # Aggregation owns its engine and does CPU-heavy series assembly; isolate its event loop.
    return asyncio.run(data_plane_status(operational=True))


async def _refresh_overview_payload() -> dict[str, Any]:
    global _world_overview_cache

    if _world_overview_cache is not None:
        cached_at, payload = _world_overview_cache
        if _overview_age(cached_at, payload) < _WORLD_OVERVIEW_TTL_SECONDS:
            return payload

    async with _world_overview_lock:
        if _world_overview_cache is not None:
            cached_at, payload = _world_overview_cache
            if _overview_age(cached_at, payload) < _WORLD_OVERVIEW_TTL_SECONDS:
                return payload
        try:
            payload = await asyncio.to_thread(_aggregate_overview)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live Data Plane aggregation is unavailable",
            ) from exc
        _world_overview_cache = (monotonic(), payload)
        return payload


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


def _hot_view(entry: HotBugCacheEntry, source_name: str | None = None) -> HotBugView:
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
        source_name=source_name,
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
