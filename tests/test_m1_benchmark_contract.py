from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.evaluation.m1_m3 import SourceDeliveryKey
from packages.evaluation.m1_status import (
    render_m1_status_markdown,
    update_m1_readme_status,
)
from packages.sources.contracts import AcquisitionTrigger
from scripts.run_m1_benchmark import (
    M1ExpectedEventManifest,
    _accepted_delivery_keys,
    _monitoring_event_time,
    _monitoring_latency_query,
    _scheduled_observation_query,
    _steady_state_monitoring_rows,
)


def test_monitoring_latency_query_only_accepts_scheduled_acquisition() -> None:
    query = _monitoring_latency_query(
        datetime(2026, 9, 26, tzinfo=UTC),
        datetime(2026, 9, 28, tzinfo=UTC),
    )
    compiled = query.compile()
    values: set[object] = set()
    for value in compiled.params.values():
        if isinstance(value, (list, tuple, set, frozenset)):
            values.update(value)
        else:
            values.add(value)
    assert "acquisition_trigger" in str(compiled)
    assert AcquisitionTrigger.SCHEDULED.value in values
    assert AcquisitionTrigger.ON_DEMAND.value not in values
    assert AcquisitionTrigger.PROMOTION.value not in values


def test_m1_status_markdown_renders_not_evaluated_without_inventing_zeroes() -> None:
    rendered = render_m1_status_markdown(
        {
            "benchmark_run_id": "run-1",
            "deployment_revision_id": "deployment:abc",
            "suite_ref": "m1@7",
            "window_start": "2026-10-01T09:00:00+00:00",
            "window_end": "2026-10-01T12:00:00+00:00",
            "source_category_count": 8,
            "raw_latency_candidate_count": 195,
            "excluded_nonsteady_count": 195,
            "latency": {
                "total_samples": 0,
                "evaluable_samples": 0,
                "evaluable_coverage": None,
                "p50_seconds": None,
                "p95_seconds": None,
                "max_seconds": None,
                "within_6h_rate": None,
            },
            "source_delivery_coverage": "not_evaluated",
            "latency_sample_digest": "deadbeef",
        }
    )
    assert (
        "raw=195, steady_state=0, excluded=195, exclusions=[legacy_result], evaluable=0"
        in rendered
    )
    assert "p50: not_evaluated" in rendered
    assert "Within 6h: not_evaluated" in rendered
    assert "DO NOT EDIT BY HAND" in rendered


def test_m1_readme_status_update_only_replaces_generated_block(tmp_path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "before\n<!-- BEGIN GENERATED M1 STATUS -->\nold\n"
        "<!-- END GENERATED M1 STATUS -->\nafter\n",
        encoding="utf-8",
    )
    update_m1_readme_status(readme, "### generated\n\n- value: 1\n")
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("before\n")
    assert "### generated" in text
    assert "old" not in text
    assert text.endswith("after\n")


def test_monitoring_latency_excludes_bootstrap_and_uses_source_event_time() -> None:
    class Row:
        def __init__(
            self,
            *,
            cursor_in: dict[str, object],
            cursor_out: dict[str, object],
            had_prior_scheduled_success: bool,
            time_semantics: dict[str, object],
            published_at: datetime | None,
            updated_at: datetime | None,
        ) -> None:
            self.cursor_in = cursor_in
            self.cursor_out = cursor_out
            self.had_prior_scheduled_success = had_prior_scheduled_success
            self.time_semantics = time_semantics
            self.published_at = published_at
            self.updated_at = updated_at

    published = datetime(2026, 9, 30, 1, tzinfo=UTC)
    updated = datetime(2026, 10, 1, 8, tzinfo=UTC)
    bootstrap = Row(
        cursor_in={},
        cursor_out={},
        had_prior_scheduled_success=False,
        time_semantics={"updated_at": "provider.updated_at"},
        published_at=published,
        updated_at=updated,
    )
    cursor_seeded = Row(
        cursor_in={"cursor": "r1"},
        cursor_out={"cursor": "r2"},
        had_prior_scheduled_success=False,
        time_semantics={"updated_at": "provider.updated_at"},
        published_at=published,
        updated_at=updated,
    )
    prior_success = Row(
        cursor_in={},
        cursor_out={},
        had_prior_scheduled_success=True,
        time_semantics={"published_at": "provider.published_at"},
        published_at=published,
        updated_at=updated,
    )
    backfill = Row(
        cursor_in={"cursor": "r2", "backfill_pending": True},
        cursor_out={"cursor": "r3"},
        had_prior_scheduled_success=True,
        time_semantics={"published_at": "provider.published_at"},
        published_at=published,
        updated_at=updated,
    )
    discovered_backfill = Row(
        cursor_in={"cursor": "r3"},
        cursor_out={"cursor": "r4", "backfill_pending": True},
        had_prior_scheduled_success=True,
        time_semantics={"published_at": "provider.published_at"},
        published_at=published,
        updated_at=updated,
    )

    assert _steady_state_monitoring_rows(
        [bootstrap, cursor_seeded, prior_success, backfill, discovered_backfill]
    ) == [cursor_seeded, prior_success]
    assert _monitoring_event_time(cursor_seeded) == updated
    assert _monitoring_event_time(prior_success) == published


def test_delivery_query_only_accepts_scheduled_observations_in_window() -> None:
    query = _scheduled_observation_query(
        datetime(2026, 9, 26, tzinfo=UTC),
        datetime(2026, 9, 28, tzinfo=UTC),
    )
    compiled = query.compile()
    values = set(compiled.params.values())
    assert "acquisition_trigger" in str(compiled)
    assert "observed_at" in str(compiled)
    assert AcquisitionTrigger.SCHEDULED.value in values
    assert AcquisitionTrigger.ON_DEMAND.value not in values


def test_expected_event_manifest_requires_independent_complete_snapshot() -> None:
    start = datetime(2026, 9, 26, tzinfo=UTC)
    end = datetime(2026, 9, 27, tzinfo=UTC)
    event = SourceDeliveryKey(
        source_id="source-a",
        external_object_id="item-1",
        external_revision="r1",
    )
    manifest = M1ExpectedEventManifest(
        manifest_id="m1-provider-window-1",
        provider_snapshot_ref="provider-snapshot:abc123",
        captured_at=end,
        window_start=start,
        window_end=end,
        events=[event],
    )
    assert manifest.events == [event]

    with pytest.raises(ValidationError, match="captured at or after window_end"):
        M1ExpectedEventManifest(
            manifest_id="early",
            provider_snapshot_ref="provider-snapshot:abc123",
            captured_at=end.replace(hour=0) - (end - start) / 2,
            window_start=start,
            window_end=end,
            events=[event],
        )
    with pytest.raises(ValidationError, match="independent provider-snapshot"):
        M1ExpectedEventManifest(
            manifest_id="self-derived",
            provider_snapshot_ref="observation:self-gold",
            captured_at=end,
            window_start=start,
            window_end=end,
            events=[event],
        )
    with pytest.raises(ValidationError, match="duplicate SourceDeliveryKey"):
        M1ExpectedEventManifest(
            manifest_id="duplicate",
            provider_snapshot_ref="artifact:frozen-provider-baseline",
            captured_at=end,
            window_start=start,
            window_end=end,
            events=[event, event],
        )


def test_accepted_delivery_keys_match_expected_revision_or_hash_without_double_count() -> None:
    class Row:
        def __init__(
            self,
            source_id: str,
            external_object_id: str,
            external_revision: str | None,
            content_hash: str,
        ) -> None:
            self.source_id = source_id
            self.external_object_id = external_object_id
            self.external_revision = external_revision
            self.content_hash = content_hash

    by_revision = SourceDeliveryKey(
        source_id="source-a",
        external_object_id="item-1",
        external_revision="r1",
    )
    by_hash = SourceDeliveryKey(
        source_id="source-b",
        external_object_id="item-2",
        content_hash="hash-2",
    )
    accepted = _accepted_delivery_keys(
        [
            Row("source-a", "item-1", "r1", "other-hash"),
            Row("source-b", "item-2", "provider-r2", "hash-2"),
            Row("source-extra", "extra", "r3", "hash-3"),
        ],
        [by_revision, by_hash],
    )
    assert accepted == [
        by_revision,
        by_hash,
        SourceDeliveryKey(
            source_id="source-extra",
            external_object_id="extra",
            external_revision="r3",
        ),
    ]
