"""Replay retained Hot Pool timestamps without claiming complete event delivery."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from math import ceil
from typing import Any


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("monitoring timestamps require timezone")
    return result.astimezone(UTC)


def score_hot_monitoring_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Recompute conservative availability bounds from a complete frozen snapshot.

    Successful acquisition completion bounds awaited cache writes. Retained latest
    revisions are a survivorship-limited population, not independent delivery gold.
    Precomputed sample scores/exclusion labels are deliberately never trusted.
    """
    if snapshot.get("schema_version") != "secfusion-hot-monitoring-frozen-v1":
        raise ValueError("unsupported hot monitoring snapshot schema")
    start, end = _time(snapshot["window_start"]), _time(snapshot["window_end"])
    if end <= start:
        raise ValueError("invalid monitoring window")
    sources = {s["source_id"]: s for s in snapshot["source_definitions"]}
    runs = {r["run_id"]: r for r in snapshot["acquisition_runs"]}
    if len(sources) != len(snapshot["source_definitions"]) or len(runs) != len(
        snapshot["acquisition_runs"]
    ):
        raise ValueError("duplicate source or acquisition identity")
    seen: set[tuple[str, str]] = set()
    excluded: Counter[str] = Counter()
    unavailable: Counter[str] = Counter()
    bounds: list[float] = []
    eligible = 0
    for sample in snapshot["samples"]:
        key = (sample["source_id"], sample["external_object_id"])
        if key in seen:
            raise ValueError("duplicate retained source/object")
        seen.add(key)
        fetched = _time(sample["fetched_at"])
        if not start <= fetched < end:
            raise ValueError("sample outside frozen window")
        run = runs.get(sample["acquisition_run_id"])
        if run is None:
            raise ValueError("sample has no frozen acquisition run")
        if run["source_id"] != sample["source_id"]:
            raise ValueError("source/acquisition identity mismatch")
        source = sources[sample["source_id"]]
        reason = (
            "not_scheduled"
            if run["trigger"] != "scheduled"
            else "input_backfill"
            if run["cursor_in_backfill_pending"]
            else "output_backfill"
            if run["cursor_out_backfill_pending"]
            else "first_admission"
            if not (run["cursor_in_present"] or run["had_prior_scheduled_success"])
            else None
        )
        if reason:
            excluded[reason] += 1
            continue
        eligible += 1
        event_value = (
            sample.get("updated_at") if source["time_semantics"].get("updated_at") else None
        ) or sample.get("published_at")
        if event_value is None:
            unavailable["missing_event_time"] += 1
            continue
        if run["status"] != "success" or not run.get("finished_at"):
            unavailable["no_successful_completion"] += 1
            continue
        event, finish = _time(event_value), _time(run["finished_at"])
        if not event <= fetched <= finish:
            raise ValueError("invalid event/fetch/completion time order")
        bounds.append((finish - event).total_seconds())
    bounds.sort()
    return {
        "schema_version": "secfusion-hot-monitoring-score-v1",
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "sample_count": len(seen),
        "eligible_count": eligible,
        "evaluable_count": len(bounds),
        "excluded_counts": dict(excluded),
        "unavailable_counts": dict(unavailable),
        "evaluable_coverage": len(bounds) / eligible if eligible else None,
        "p50_upper_bound_seconds": bounds[max(0, ceil(len(bounds) * 0.50) - 1)] if bounds else None,
        "p95_upper_bound_seconds": bounds[max(0, ceil(len(bounds) * 0.95) - 1)] if bounds else None,
        "max_upper_bound_seconds": max(bounds) if bounds else None,
        "within_6h_rate": sum(b <= 21600 for b in bounds) / len(bounds) if bounds else None,
        "exact_availability_status": "not_evaluated",
        "expected_event_delivery_status": "not_evaluated",
        "population": "retained latest source/object revisions in the frozen fetch window",
        "limitations": [
            "Overwritten or expired versions are absent; no complete delivery-recall denominator.",
            "Run completion is an upper bound, not the exact first cache availability timestamp.",
            "Failed acquisitions must be reported separately from resident-record latency.",
        ],
    }
