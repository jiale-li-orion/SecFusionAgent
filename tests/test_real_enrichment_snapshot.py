from __future__ import annotations

import pytest

from scripts.evaluate_real_enrichment import (
    PROVIDER_SNAPSHOT_SCHEMA,
    _load_provider_snapshot,
    _provider_snapshot_revision,
    _snapshot_fetched_at,
    _validate_provider_snapshot,
    _visible_at_revision,
    _write_provider_snapshot,
)


def _snapshot() -> dict[str, object]:
    return {
        "snapshot_schema": PROVIDER_SNAPSHOT_SCHEMA,
        "fetched_at": "2026-09-27T00:00:00+00:00",
        "cisa_catalog_version": "2026.09.27",
        "cases": {
            "CVE-2026-42424": {
                "nvd": {"id": "CVE-2026-42424"},
                "github": [],
                "osv": [],
                "first_epss": None,
                "known_exploited": False,
            }
        },
    }


def test_provider_snapshot_revision_is_deterministic() -> None:
    first = _snapshot()
    second = _snapshot()
    assert _provider_snapshot_revision(first) == _provider_snapshot_revision(second)
    assert _provider_snapshot_revision(first).startswith("provider-snapshot:")


def test_provider_snapshot_validation_rejects_case_drift() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="case set does not match"):
        _validate_provider_snapshot(snapshot, ["CVE-2026-99999"])


def test_provider_snapshot_validation_rejects_schema_drift() -> None:
    snapshot = _snapshot()
    snapshot["snapshot_schema"] = "future-schema"
    with pytest.raises(ValueError, match="unsupported provider snapshot schema"):
        _validate_provider_snapshot(snapshot, ["CVE-2026-42424"])


def test_provider_snapshot_round_trip_preserves_revision(tmp_path) -> None:
    snapshot = _snapshot()
    path = tmp_path / "provider-snapshot.json"
    _write_provider_snapshot(path, snapshot)
    loaded = _load_provider_snapshot(path)
    assert loaded == snapshot
    assert _provider_snapshot_revision(loaded) == _provider_snapshot_revision(snapshot)


def test_snapshot_fetched_at_requires_timezone() -> None:
    assert _snapshot_fetched_at(_snapshot()).isoformat() == "2026-09-27T00:00:00+00:00"
    snapshot = _snapshot()
    snapshot["fetched_at"] = "2026-09-27T00:00:00"
    with pytest.raises(ValueError, match="must include timezone"):
        _snapshot_fetched_at(snapshot)


def test_revision_visibility_is_point_in_time() -> None:
    assert _visible_at_revision(
        created_revision=10,
        superseded_revision=None,
        knowledge_revision=10,
    )
    assert not _visible_at_revision(
        created_revision=11,
        superseded_revision=None,
        knowledge_revision=10,
    )
    assert _visible_at_revision(
        created_revision=8,
        superseded_revision=12,
        knowledge_revision=11,
    )
    assert not _visible_at_revision(
        created_revision=8,
        superseded_revision=12,
        knowledge_revision=12,
    )
