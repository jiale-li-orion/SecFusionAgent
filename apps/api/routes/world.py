from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from apps.application.views.world import (
    WorldCategoryHealthView,
    WorldHealthCountsView,
    WorldOverviewView,
    WorldSeriesPointView,
    WorldWindowView,
)

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
        windows={
            key: _window_view(rolling[key].get("scheduled_monitoring", {}))
            for key in _WINDOW_KEYS
            if key in rolling
        },
        hourly_series=[
            WorldSeriesPointView.model_validate(item)
            for item in payload.get("hourly_series", [])
        ],
        outbox_delivered=int(pipeline_state.get("outbox", {}).get("delivered", 0)),
        lexical_ready_documents=int(
            pipeline_state.get("document_index", {}).get("lexical_ready", 0)
        ),
        artifact_store_status=artifact_store.get("status"),
        public_epoch_artifact_integrity_rate=artifact_store.get("public_epoch", {}).get(
            "integrity_rate"
        ),
    )


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
        scheduled_runs=int(metrics.get("scheduled_runs", 0)),
        scheduled_run_success_rate=metrics.get("scheduled_run_success_rate"),
        provider_boundary_failure_rate=metrics.get("provider_boundary_failure_rate"),
        runtime_owned_failure_rate=metrics.get("runtime_owned_failure_rate"),
        queue_delay_p95_seconds=metrics.get("queue_delay_p95_seconds"),
        execution_p95_seconds=metrics.get("execution_p95_seconds"),
        fresh_knowledge_latency_p95_seconds=metrics.get("fresh_knowledge_latency_p95_seconds"),
        evidence_integrity_rate=metrics.get("evidence_integrity_rate"),
    )
