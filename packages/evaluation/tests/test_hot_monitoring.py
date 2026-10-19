from copy import deepcopy

import pytest

from packages.evaluation.hot_monitoring import score_hot_monitoring_snapshot


def snapshot():
    return {
        "schema_version": "secfusion-hot-monitoring-frozen-v1",
        "window_start": "2026-10-15T00:00:00+00:00",
        "window_end": "2026-10-16T00:00:00+00:00",
        "source_definitions": [{"source_id": "nvd", "time_semantics": {"updated_at": "modified"}}],
        "acquisition_runs": [
            {
                "run_id": "r",
                "source_id": "nvd",
                "trigger": "scheduled",
                "status": "success",
                "cursor_in_present": True,
                "had_prior_scheduled_success": True,
                "cursor_in_backfill_pending": False,
                "cursor_out_backfill_pending": False,
                "finished_at": "2026-10-15T10:01:00+00:00",
            }
        ],
        "samples": [
            {
                "sample_id": "s",
                "source_id": "nvd",
                "external_object_id": "CVE-1",
                "external_revision": "v1",
                "acquisition_run_id": "r",
                "updated_at": "2026-10-15T09:00:00+00:00",
                "published_at": "2020-01-01T00:00:00Z",
                "fetched_at": "2026-10-15T10:00:00+00:00",
            }
        ],
    }


def test_recompute_upper_bound_does_not_trust_embedded_score():
    data = snapshot()
    data["samples"][0]["event_to_run_finished_upper_bound_seconds"] = 0
    result = score_hot_monitoring_snapshot(data)
    assert result["max_upper_bound_seconds"] == 3660
    assert result["within_6h_rate"] == 1
    assert result["evaluable_count"] == 1
    assert result["expected_event_delivery_status"] == "not_evaluated"


def test_backfill_excluded_but_slow_updates_retained():
    data = snapshot()
    data["samples"][0]["updated_at"] = "2026-10-14T00:00:00Z"
    assert score_hot_monitoring_snapshot(data)["within_6h_rate"] == 0
    data["acquisition_runs"][0]["cursor_out_backfill_pending"] = True
    result = score_hot_monitoring_snapshot(data)
    assert result["excluded_counts"] == {"output_backfill": 1}
    assert result["max_upper_bound_seconds"] is None


def test_missing_time_has_explicit_denominator():
    data = snapshot()
    data["samples"][0]["updated_at"] = None
    data["samples"][0]["published_at"] = None
    result = score_hot_monitoring_snapshot(data)
    assert result["eligible_count"] == 1
    assert result["evaluable_count"] == 0
    assert result["evaluable_coverage"] == 0
    assert result["within_6h_rate"] is None


@pytest.mark.parametrize("fault", ["duplicate", "source_mismatch", "time_order", "outside_window"])
def test_invalid_snapshot_fails_closed(fault):
    data = deepcopy(snapshot())
    if fault == "duplicate":
        data["samples"].append(deepcopy(data["samples"][0]))
    if fault == "source_mismatch":
        data["acquisition_runs"][0]["source_id"] = "other"
    if fault == "time_order":
        data["samples"][0]["fetched_at"] = "2026-10-15T10:02:00Z"
    if fault == "outside_window":
        data["samples"][0]["fetched_at"] = "2026-10-16T10:00:00Z"
    with pytest.raises(ValueError):
        score_hot_monitoring_snapshot(data)


def test_multiple_retained_revisions_of_same_source_object_rejected():
    data = snapshot()
    second = deepcopy(data["samples"][0])
    second["external_revision"] = "v2"
    second["sample_id"] = "s2"
    data["samples"].append(second)
    with pytest.raises(ValueError, match="duplicate"):
        score_hot_monitoring_snapshot(data)
