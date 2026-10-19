"""Prospective NVD publication cohorts over durable hot-admission receipts.

This evidence export is independent of the canonical M1/CompetitionReport score.
Receipt time is exact for the recorded admission; receipt history can be left-censored.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

DEADLINE_SECONDS = 21600


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("monitoring timestamps require timezone")
    return value.astimezone(UTC)


class ExpectedPublication(BaseModel):
    external_object_id: str = Field(pattern=r"^CVE-[0-9]{4}-[0-9]{4,}$")
    published_at: datetime

    _timestamp = field_validator("published_at")(_utc)


class ProviderSnapshot(BaseModel):
    source_url: str
    raw_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_url")
    @classmethod
    def authoritative_nvd(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "services.nvd.nist.gov"
            or parsed.path != "/rest/json/cves/2.0"
            or parsed.fragment
        ):
            raise ValueError("expected population requires authoritative NVD source URL")
        return value


class MonitoringWindowManifest(BaseModel):
    schema_version: Literal["secfusion-monitoring-window-v1"]
    source_id: str = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    declared_at: datetime
    provider_retrieved_at: datetime | None
    provider_snapshot: ProviderSnapshot | None
    records: list[ExpectedPublication] | None

    @field_validator("window_start", "window_end", "declared_at", "provider_retrieved_at")
    @classmethod
    def timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def coherent_window(self) -> MonitoringWindowManifest:
        if not self.declared_at < self.window_start < self.window_end:
            raise ValueError("require declared_at < window_start < window_end")
        frozen_fields = (self.records, self.provider_snapshot, self.provider_retrieved_at)
        if any(v is not None for v in frozen_fields):
            if any(v is None for v in frozen_fields):
                raise ValueError("expected population must be frozen with complete provenance")
            assert self.records is not None and self.provider_retrieved_at is not None
            if self.provider_retrieved_at < self.window_end:
                raise ValueError("provider snapshot must be retrieved after window closes")
            assert self.provider_snapshot is not None
            query = parse_qs(
                urlsplit(self.provider_snapshot.source_url).query, keep_blank_values=True
            )
            allowed = {"pubStartDate", "pubEndDate", "resultsPerPage", "startIndex"}
            if (
                not {"pubStartDate", "pubEndDate"} <= query.keys()
                or not query.keys() <= allowed
                or any(len(values) != 1 for values in query.values())
                or query.get("startIndex", ["0"]) != ["0"]
            ):
                raise ValueError("NVD publication query must be unfiltered and start at page zero")
            try:
                bounds = [
                    datetime.fromisoformat(query[k][0]) for k in ("pubStartDate", "pubEndDate")
                ]
                bounds = [v.replace(tzinfo=UTC) if v.tzinfo is None else _utc(v) for v in bounds]
                page_size = int(query.get("resultsPerPage", ["2000"])[0])
            except ValueError as error:
                raise ValueError("invalid NVD publication query") from error
            if bounds != [self.window_start, self.window_end] or not 1 <= page_size <= 2000:
                raise ValueError("NVD publication query must exactly match the declared window")
            identities = [r.external_object_id for r in self.records]
            if len(set(identities)) != len(identities):
                raise ValueError("duplicate expected source/object identity")
            if any(not self.window_start <= r.published_at < self.window_end for r in self.records):
                raise ValueError("expected publication outside declared window")
        return self


class AdmissionReceipt(BaseModel):
    receipt_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    external_object_id: str = Field(min_length=1)
    external_revision: str | None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_at: datetime | None
    updated_at: datetime | None
    fetched_at: datetime
    available_at: datetime
    acquisition_run_id: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    source_definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_backfill_pending: bool
    output_backfill_pending: bool

    @field_validator("published_at", "updated_at", "fetched_at", "available_at")
    @classmethod
    def timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def admission_order(self) -> AdmissionReceipt:
        if self.fetched_at > self.available_at:
            raise ValueError("receipt availability precedes fetch")
        return self


def validate_provider_snapshot(manifest: dict[str, Any], raw: bytes) -> None:
    """Verify frozen bytes and full NVD pagination against the independently supplied gold.

    Raw input is one NVD API response or a JSON array of all page responses. NVD's
    timezone-less publication strings are UTC; the portable manifest requires offsets.
    """
    window = MonitoringWindowManifest.model_validate(manifest)
    if window.provider_snapshot is None or window.records is None:
        raise ValueError("provider snapshot requires frozen expected population")
    if sha256(raw).hexdigest() != window.provider_snapshot.raw_content_sha256:
        raise ValueError("provider snapshot digest mismatch")
    payload = json.loads(raw)
    pages = payload if isinstance(payload, list) else [payload]
    if not pages or not all(isinstance(p, dict) for p in pages):
        raise ValueError("invalid NVD pagination")
    offset, total = 0, pages[0].get("totalResults")
    if type(total) is not int or total < 0:
        raise ValueError("invalid NVD pagination totalResults")
    actual: dict[str, datetime] = {}
    seen: set[str] = set()
    for page in pages:
        records = page.get("vulnerabilities")
        if (
            page.get("startIndex") != offset
            or page.get("totalResults") != total
            or not isinstance(records, list)
        ):
            raise ValueError("incomplete or inconsistent NVD pagination")
        for item in records:
            cve = item["cve"]
            value = datetime.fromisoformat(cve["published"].replace("Z", "+00:00"))
            value = value.replace(tzinfo=UTC) if value.tzinfo is None else _utc(value)
            record = ExpectedPublication(external_object_id=cve["id"], published_at=value)
            if record.external_object_id in seen:
                raise ValueError("duplicate provider population identity")
            seen.add(record.external_object_id)
            if window.window_start <= value < window.window_end:
                actual[record.external_object_id] = value
        offset += len(records)
    if offset != total:
        raise ValueError("incomplete NVD pagination")
    expected = {r.external_object_id: r.published_at for r in window.records}
    if actual != expected:
        raise ValueError("manifest population differs from complete provider snapshot")


def score_monitoring_window(
    manifest: dict[str, Any],
    receipts: Sequence[dict[str, Any]],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Score all independent expected publications; no backfill/outcome exclusions.

    Final delivery rate uses the complete expected population. Accepted-only latency
    and its rate remain diagnostic while missing publications stay in the denominator.
    """
    window = MonitoringWindowManifest.model_validate(manifest)
    now = _utc(as_of)
    if now < window.declared_at:
        raise ValueError("as_of precedes window declaration")
    if window.provider_retrieved_at is not None and window.provider_retrieved_at > now:
        raise ValueError("provider snapshot was not available as_of evaluation")
    parsed = [AdmissionReceipt.model_validate(r) for r in receipts]
    ids: set[str] = set()
    versions: set[tuple[str, str, str, str]] = set()
    earliest: dict[str, AdmissionReceipt] = {}
    for r in parsed:
        key = (
            r.source_id,
            r.external_object_id,
            "revision" if r.external_revision else "hash",
            r.external_revision or r.content_hash,
        )
        if r.source_id != window.source_id:
            raise ValueError("receipt source differs from declared source")
        if r.receipt_id in ids or key in versions:
            raise ValueError("duplicate receipt identity or source/object/version")
        ids.add(r.receipt_id)
        versions.add(key)
        if r.available_at > now:
            continue
        previous = earliest.get(r.external_object_id)
        if previous is None or (r.available_at, r.receipt_id) < (
            previous.available_at,
            previous.receipt_id,
        ):
            earliest[r.external_object_id] = r

    pending_reasons = []
    if now < window.window_end:
        pending_reasons.append("window_open")
    if window.records is None:
        pending_reasons.append("awaiting_independent_expected_population")
    if now < window.window_end + timedelta(seconds=DEADLINE_SECONDS):
        pending_reasons.append("awaiting_deadline_maturity")

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    timely = late = missed = pending = backfill = 0
    expected_ids = {r.external_object_id for r in window.records or []}
    for event in sorted(window.records or [], key=lambda r: (r.published_at, r.external_object_id)):
        deadline = event.published_at + timedelta(seconds=DEADLINE_SECONDS)
        accepted = earliest.get(event.external_object_id)
        seconds = None
        if accepted is None:
            outcome = "missed" if now >= deadline else "pending"
            missed += outcome == "missed"
            pending += outcome == "pending"
        else:
            seconds = (accepted.available_at - event.published_at).total_seconds()
            if seconds < 0:
                raise ValueError("receipt availability precedes authoritative publication")
            latencies.append(seconds)
            outcome = "within_6h" if seconds <= DEADLINE_SECONDS else "late"
            timely += outcome == "within_6h"
            late += outcome == "late"
            backfill += accepted.input_backfill_pending or accepted.output_backfill_pending
        rows.append(
            {
                "external_object_id": event.external_object_id,
                "published_at": event.published_at.isoformat(),
                "deadline": deadline.isoformat(),
                "outcome": outcome,
                "receipt_id": accepted.receipt_id if accepted else None,
                "available_at": accepted.available_at.isoformat() if accepted else None,
                "latency_seconds": seconds,
            }
        )
    latencies.sort()
    count = len(window.records) if window.records is not None else None
    status = "pending" if pending_reasons else "complete" if count else "empty"
    observed = [r for r in parsed if r.available_at <= now]
    result = {
        "schema_version": "secfusion-monitoring-window-score-v1",
        "source_id": window.source_id,
        "window_start": window.window_start.isoformat(),
        "window_end": window.window_end.isoformat(),
        "as_of": now.isoformat(),
        "status": status,
        "pending_reasons": pending_reasons,
        "deadline_seconds": DEADLINE_SECONDS,
        "expected_count": count,
        "accepted_count": len(latencies) if count is not None else None,
        "within_6h_count": timely if count is not None else None,
        "late_count": late if count is not None else None,
        "missed_count": missed if count is not None else None,
        "pending_count": pending if count is not None else None,
        "within_6h_rate": timely / count if count and status == "complete" else None,
        "within_6h_rate_bounds": {
            "lower": timely / count if count else None,
            "upper": (timely + pending) / count if count else None,
        },
        "accepted_within_6h_rate": timely / len(latencies) if latencies else None,
        "latency_seconds": {
            "count": len(latencies),
            "p50": latencies[ceil(len(latencies) * 0.50) - 1] if latencies else None,
            "p95": latencies[ceil(len(latencies) * 0.95) - 1] if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "diagnostics": {
            "receipt_count": len(observed),
            "future_receipt_count": len(parsed) - len(observed),
            "accepted_backfill_count": backfill,
            "out_of_cohort_receipt_count": sum(
                r.published_at is not None
                and not window.window_start <= r.published_at < window.window_end
                and r.external_object_id not in expected_ids
                for r in observed
            ),
            "unexpected_object_count": (
                len(set(earliest) - expected_ids) if count is not None else None
            ),
        },
        "records": rows,
        "limitations": [
            "Availability is the timestamp after the recorded successful cache admission.",
            "Earliest recorded admission across revisions is not proof of first-ever collection; "
            "receipt history before instrumentation may be left-censored.",
            "Latency percentiles and accepted_within_6h_rate use accepted records only; "
            "within_6h_rate uses every independent expected publication, including misses.",
            "Backfill flags are diagnostic; fresh publications in backfill runs stay in cohort.",
            "This prospective evidence does not replace canonical M1 or a CompetitionReport.",
        ],
    }
    return result
