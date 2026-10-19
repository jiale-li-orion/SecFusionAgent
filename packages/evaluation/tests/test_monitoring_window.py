import json
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from packages.evaluation.monitoring_window import (
    score_monitoring_window,
    validate_provider_snapshot,
)


def manifest():
    return {
        "schema_version": "secfusion-monitoring-window-v1",
        "source_id": "nvd",
        "window_start": "2026-10-17T00:00:00Z",
        "window_end": "2026-10-17T01:00:00Z",
        "declared_at": "2026-10-16T23:59:00Z",
        "provider_retrieved_at": "2026-10-17T01:01:00Z",
        "provider_snapshot": {
            "source_url": "https://services.nvd.nist.gov/rest/json/cves/2.0"
            "?pubStartDate=2026-10-17T00:00:00Z&pubEndDate=2026-10-17T01:00:00Z",
            "raw_content_sha256": "a" * 64,
        },
        "records": [
            {"external_object_id": "CVE-2026-1001", "published_at": "2026-10-17T00:00:00Z"},
            {"external_object_id": "CVE-2026-1002", "published_at": "2026-10-17T00:30:00Z"},
            {"external_object_id": "CVE-2026-1003", "published_at": "2026-10-17T00:50:00Z"},
        ],
    }


def receipt(object_id="CVE-2026-1001", available_at="2026-10-17T00:10:00Z", **changes):
    return {
        "receipt_id": "receipt-1",
        "source_id": "nvd",
        "external_object_id": object_id,
        "external_revision": "v1",
        "content_hash": "b" * 64,
        "published_at": "2026-10-17T00:00:00Z",
        "updated_at": "2026-10-17T00:00:00Z",
        "fetched_at": available_at,
        "available_at": available_at,
        "acquisition_run_id": "run-1",
        "trigger": "scheduled",
        "source_definition_hash": "c" * 64,
        "input_backfill_pending": True,
        "output_backfill_pending": True,
        **changes,
    }


def score(data=None, receipts=(), hour=7, minute=0):
    return score_monitoring_window(
        manifest() if data is None else data,
        receipts,
        as_of=datetime(2026, 10, 17, hour, minute, tzinfo=UTC),
    )


def test_fresh_backfill_is_included_earliest_revision_wins_and_missing_stays_in_denominator():
    first = receipt()
    later = receipt(
        available_at="2026-10-17T00:40:00Z", receipt_id="receipt-2", external_revision="v2"
    )
    late = receipt("CVE-2026-1002", "2026-10-17T06:31:00Z", receipt_id="receipt-3")
    old = receipt("CVE-2020-1000", receipt_id="receipt-4", published_at="2020-01-01T00:00:00Z")
    data = manifest()
    data["expected_count"] = 999
    result = score(data, [later, first, late, old])
    assert result["status"] == "complete"
    assert result["expected_count"] == 3
    assert result["accepted_count"] == 2
    assert result["missed_count"] == 1
    assert result["late_count"] == 1
    assert result["within_6h_count"] == 1
    assert result["within_6h_rate"] == 1 / 3
    assert result["accepted_within_6h_rate"] == 1 / 2
    assert result["latency_seconds"] == {"count": 2, "p50": 600, "p95": 21660, "max": 21660}
    assert result["diagnostics"]["accepted_backfill_count"] == 2
    assert result["diagnostics"]["out_of_cohort_receipt_count"] == 1
    assert result["records"][0]["receipt_id"] == "receipt-1"


def test_missing_deadlines_are_pending_until_each_publication_deadline():
    result = score(receipts=[receipt()], hour=6, minute=30)
    assert result["status"] == "pending"
    assert result["missed_count"] == 1
    assert result["pending_count"] == 1
    assert result["within_6h_rate"] is None
    assert result["within_6h_rate_bounds"] == {"lower": 1 / 3, "upper": 2 / 3}
    assert "awaiting_deadline_maturity" in result["pending_reasons"]


def test_unfrozen_window_never_infers_expected_population_from_receipts():
    data = manifest()
    data.update(provider_retrieved_at=None, provider_snapshot=None, records=None)
    result = score(data, [receipt()], hour=0, minute=30)
    assert result["status"] == "pending"
    assert result["expected_count"] is None
    assert result["accepted_count"] is None
    assert result["within_6h_rate"] is None
    assert result["pending_reasons"] == [
        "window_open",
        "awaiting_independent_expected_population",
        "awaiting_deadline_maturity",
    ]
    assert result["diagnostics"]["receipt_count"] == 1


def test_empty_complete_population_has_no_vacuous_success():
    data = manifest()
    data["records"] = []
    result = score(data)
    assert result["status"] == "empty"
    assert result["within_6h_rate"] is None
    assert result["accepted_within_6h_rate"] is None
    assert result["latency_seconds"]["p95"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "naive_time",
        "late_declaration",
        "duplicate_expected",
        "wrong_source",
        "bad_hash",
        "outside_window",
        "early_provider",
        "partial_provider",
        "duplicate_receipt",
        "time_order",
        "wrong_receipt_source",
        "duplicate_version",
    ],
)
def test_invalid_identity_time_and_provenance_fail_closed(fault):
    data, receipts = manifest(), [receipt()]
    if fault == "naive_time":
        data["window_start"] = "2026-10-17T00:00:00"
    elif fault == "late_declaration":
        data["declared_at"] = data["window_start"]
    elif fault == "duplicate_expected":
        data["records"].append(deepcopy(data["records"][0]))
    elif fault == "wrong_source":
        data["source_id"] = "other"
    elif fault == "bad_hash":
        data["provider_snapshot"]["raw_content_sha256"] = "unverified"
    elif fault == "outside_window":
        data["records"][0]["published_at"] = data["window_end"]
    elif fault == "early_provider":
        data["provider_retrieved_at"] = data["window_start"]
    elif fault == "partial_provider":
        data["provider_snapshot"] = None
    elif fault == "duplicate_receipt":
        receipts.append(deepcopy(receipts[0]))
    elif fault == "duplicate_version":
        receipts.append(receipt(receipt_id="another"))
    elif fault == "time_order":
        receipts[0]["available_at"] = "2026-10-17T00:09:00Z"
    elif fault == "wrong_receipt_source":
        receipts[0]["source_id"] = "other"
    with pytest.raises(ValueError):
        score(data, receipts)


def test_future_receipts_do_not_resolve_pending_or_missed_records():
    late = receipt(available_at="2026-10-17T08:00:00Z")
    result = score(receipts=[late])
    assert result["missed_count"] == 3
    assert result["accepted_count"] == 0


def provider_bytes(data):
    return json.dumps(
        {
            "startIndex": 0,
            "totalResults": len(data["records"]),
            "vulnerabilities": [
                {
                    "cve": {
                        "id": r["external_object_id"],
                        "published": r["published_at"].removesuffix("Z"),
                    }
                }
                for r in data["records"]
            ],
        }
    ).encode()


def test_raw_provider_hash_and_complete_population_are_verified():
    data = manifest()
    raw = provider_bytes(data)
    data["provider_snapshot"]["raw_content_sha256"] = sha256(raw).hexdigest()
    validate_provider_snapshot(data, raw)
    with pytest.raises(ValueError, match="digest"):
        validate_provider_snapshot(data, raw + b" ")
    data["records"].pop()
    with pytest.raises(ValueError, match="population"):
        validate_provider_snapshot(data, raw)


def test_incomplete_provider_pagination_cannot_freeze_denominator():
    data = manifest()
    raw_data = json.loads(provider_bytes(data))
    raw_data["totalResults"] = 10
    raw = json.dumps(raw_data).encode()
    data["provider_snapshot"]["raw_content_sha256"] = sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="pagination"):
        validate_provider_snapshot(data, raw)


@pytest.mark.parametrize(
    "query",
    [
        "cveId=CVE-2026-1001",
        "pubStartDate=2026-10-17T00:00:00Z&pubEndDate=2026-10-17T01:00:00Z&keywordSearch=only-one",
        "pubStartDate=2026-10-17T00:30:00Z&pubEndDate=2026-10-17T01:00:00Z",
        "pubStartDate=2026-10-17T00:00:00Z&pubEndDate=2026-10-17T01:00:00Z&startIndex=2",
        "pubStartDate=2026-10-17T00:00:00Z&pubEndDate=2026-10-17T01:00:00Z&pubEndDate=other",
    ],
)
def test_filtered_or_mismatched_provider_query_cannot_define_expected_population(query):
    data = manifest()
    data["provider_snapshot"]["source_url"] = (
        "https://services.nvd.nist.gov/rest/json/cves/2.0?" + query
    )
    with pytest.raises(ValueError, match="publication query"):
        score(data)


def test_exact_six_hour_admission_is_timely():
    data = manifest()
    data["records"] = data["records"][:1]
    result = score(data, [receipt(available_at="2026-10-17T06:00:00Z")])
    assert result["within_6h_rate"] == 1
    assert result["latency_seconds"]["max"] == 21600


def test_revision_and_content_hash_identity_namespaces_remain_distinct():
    revision = receipt(external_revision="b" * 64)
    fallback = receipt(external_revision=None, receipt_id="fallback-hash")
    result = score(receipts=[revision, fallback])
    assert result["accepted_count"] == 1
    assert result["diagnostics"]["receipt_count"] == 2


@pytest.mark.asyncio
async def test_database_snapshot_retains_failed_runs_and_their_successful_admissions():
    from sqlalchemy import insert
    from sqlalchemy.ext.asyncio import create_async_engine

    from packages.monitoring.storage.models import (
        AcquisitionRunModel,
        HotAdmissionReceiptModel,
        SourceStateModel,
    )
    from packages.shared.db import Base
    from packages.sources.storage.models import SourceModel
    from scripts.export_monitoring_window import load_monitoring_window_snapshot

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    at = datetime(2026, 10, 17, 0, 10, tzinfo=UTC)
    source = dict(
        source_id="nvd",
        adapter_type="nvd",
        source_class="vulnerability",
        source_role="authority",
        source_family="nvd",
        access_mode="api",
        update_semantics="mutable",
        retention_mode="hot_window",
        schema_version="1",
        definition_hash="c" * 64,
        updated_at=at,
    )
    try:
        async with engine.begin() as connection:
            for model in (
                SourceModel,
                SourceStateModel,
                AcquisitionRunModel,
                HotAdmissionReceiptModel,
            ):
                await connection.run_sync(Base.metadata.tables[model.__tablename__].create)
            await connection.execute(insert(SourceModel), source)
            await connection.execute(
                insert(SourceStateModel),
                {
                    "source_id": "nvd",
                    "cursor": {"backfill_pending": True},
                    "consecutive_failures": 1,
                },
            )
            await connection.execute(
                insert(AcquisitionRunModel),
                {
                    "run_id": "run-1",
                    "source_id": "nvd",
                    "trigger": "scheduled",
                    "status": "fetch_failed",
                    "error_code": "timeout",
                    "created_at": at,
                    "finished_at": at,
                },
            )
            raw = receipt()
            for key in ("published_at", "updated_at", "fetched_at", "available_at"):
                raw[key] = datetime.fromisoformat(raw[key])
            await connection.execute(insert(HotAdmissionReceiptModel), raw)
        async with engine.connect() as connection:
            snapshot = await load_monitoring_window_snapshot(
                connection, manifest(), as_of=datetime(2026, 10, 17, 7, tzinfo=UTC)
            )
        assert snapshot["operational_diagnostics"]["run_status_counts"] == {"fetch_failed": 1}
        assert snapshot["operational_diagnostics"]["failed_run_count"] == 1
        assert snapshot["operational_diagnostics"]["source_state"]["backfill_pending"] is True
        assert snapshot["score"]["accepted_count"] == 1
        assert snapshot["score"]["missed_count"] == 2
        assert len(snapshot["receipts"]) == 1
    finally:
        await engine.dispose()
