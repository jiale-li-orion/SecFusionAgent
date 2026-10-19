"""Export prospective publication latency using a read-only PostgreSQL snapshot."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.evaluation.monitoring_window import (
    MonitoringWindowManifest,
    score_monitoring_window,
    validate_provider_snapshot,
)
from packages.monitoring.storage.models import (
    AcquisitionRunModel,
    HotAdmissionReceiptModel,
    SourceStateModel,
)
from packages.shared.db import create_engine
from packages.sources.storage.models import SourceModel


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("monitoring timestamps require timezone")
    return value.astimezone(UTC)


def _json_row(row: Any) -> dict[str, Any]:
    # SQLite drops timezone metadata in deterministic storage tests. Production
    # PostgreSQL timestamps retain it; every stored monitoring timestamp is UTC.
    return {
        key: (value.replace(tzinfo=UTC) if value.tzinfo is None else _utc(value)).isoformat()
        if isinstance(value, datetime)
        else value
        for key, value in row.items()
    }


async def load_monitoring_window_snapshot(
    connection: AsyncConnection,
    manifest: dict[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Read receipt evidence plus source/run health; caller owns a read-only snapshot.

    All source receipts admitted during [start, as_of] are retained for diagnostics,
    plus earlier receipts for expected identities so revision selection is unbiased.
    Run health covers runs overlapping [start, as_of], including partial failed runs.
    """
    window = MonitoringWindowManifest.model_validate(manifest)
    now = _utc(as_of)
    source = (
        (
            await connection.execute(
                select(
                    SourceModel.source_id,
                    SourceModel.adapter_type,
                    SourceModel.source_class,
                    SourceModel.enabled,
                    SourceModel.retention_mode,
                    SourceModel.definition_hash,
                    SourceModel.schedule_policy,
                ).where(SourceModel.source_id == window.source_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if source is None or source["adapter_type"] != "nvd":
        raise ValueError("declared source must exist and use the NVD adapter")
    state = (
        (
            await connection.execute(
                select(
                    SourceStateModel.last_attempt_at,
                    SourceStateModel.last_success_at,
                    SourceStateModel.next_due_at,
                    SourceStateModel.consecutive_failures,
                    SourceStateModel.backoff_until,
                    SourceStateModel.cursor,
                ).where(SourceStateModel.source_id == window.source_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    state_json = _json_row(state) if state else None
    if state_json is not None:
        state_json["backfill_pending"] = state_json.pop("cursor").get("backfill_pending") is True
    expected_ids = [r.external_object_id for r in window.records or []]
    receipt_rows = (
        (
            await connection.execute(
                select(HotAdmissionReceiptModel.__table__)
                .where(
                    HotAdmissionReceiptModel.source_id == window.source_id,
                    HotAdmissionReceiptModel.available_at <= now,
                    or_(
                        HotAdmissionReceiptModel.available_at >= window.window_start,
                        HotAdmissionReceiptModel.external_object_id.in_(expected_ids),
                    ),
                )
                .order_by(
                    HotAdmissionReceiptModel.available_at,
                    HotAdmissionReceiptModel.receipt_id,
                )
            )
        )
        .mappings()
        .all()
    )
    receipts = [_json_row(row) for row in receipt_rows]
    run_rows = (
        (
            await connection.execute(
                select(
                    AcquisitionRunModel.status,
                    AcquisitionRunModel.trigger,
                    AcquisitionRunModel.error_code,
                    func.count().label("count"),
                )
                .where(
                    AcquisitionRunModel.source_id == window.source_id,
                    AcquisitionRunModel.created_at <= now,
                    or_(
                        AcquisitionRunModel.finished_at.is_(None),
                        AcquisitionRunModel.finished_at >= window.window_start,
                    ),
                )
                .group_by(
                    AcquisitionRunModel.status,
                    AcquisitionRunModel.trigger,
                    AcquisitionRunModel.error_code,
                )
                .order_by(AcquisitionRunModel.status, AcquisitionRunModel.trigger)
            )
        )
        .mappings()
        .all()
    )
    counts: dict[str, int] = {}
    for row in run_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + row["count"]
    return {
        "schema_version": "secfusion-monitoring-window-evidence-v1",
        "manifest": manifest,
        "as_of": now.isoformat(),
        "receipts": receipts,
        "operational_diagnostics": {
            "source_count": 1,
            "source_definition": _json_row(source),
            "source_state": state_json,
            "run_window_start": window.window_start.isoformat(),
            "run_window_end": now.isoformat(),
            "run_count": sum(counts.values()),
            "run_status_counts": counts,
            "failed_run_count": sum(
                n
                for status, n in counts.items()
                if status
                not in {
                    "success",
                    "no_change",
                    "queued",
                    "running",
                }
            ),
            "run_groups": [_json_row(row) for row in run_rows],
            "note": "Run/source status reflects the database snapshot; receipt time is immutable.",
        },
        "score": score_monitoring_window(manifest, receipts, as_of=now),
    }


async def export(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    window = MonitoringWindowManifest.model_validate(manifest)
    if window.records is not None:
        if args.provider_snapshot is None:
            raise ValueError("frozen expected population requires --provider-snapshot")
        validate_provider_snapshot(manifest, args.provider_snapshot.read_bytes())
    elif args.provider_snapshot is not None:
        raise ValueError("provider snapshot supplied before expected population is frozen")
    now = datetime.now(UTC)
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else now
    if as_of.tzinfo is None or as_of > now:
        raise ValueError("--as-of must have timezone and cannot be in the future")
    engine = create_engine()
    try:
        if engine.dialect.name != "postgresql":
            raise ValueError("monitoring evidence export requires PostgreSQL")
        async with engine.connect() as connection:
            connection = await connection.execution_options(
                isolation_level="REPEATABLE READ",
                postgresql_readonly=True,
            )
            async with connection.begin():
                result = await load_monitoring_window_snapshot(connection, manifest, as_of=as_of)
        result["manifest_sha256"] = sha256(raw).hexdigest()
        result["exported_at"] = datetime.now(UTC).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Frozen outputs are append-only artifacts. Choose a new filename to rescore.
        with args.output.open("x") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
        return result
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--provider-snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", help="Timezone-aware cutoff; defaults to current UTC")
    args = parser.parse_args()
    result = asyncio.run(export(args))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "score": result["score"],
                "operational_diagnostics": result["operational_diagnostics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
