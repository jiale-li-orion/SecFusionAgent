from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _projection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "public_monitoring_epoch": payload["public_monitoring_epoch"],
        "public_monitoring_epoch_local": payload["public_monitoring_epoch_local"],
        "taxonomy": payload["taxonomy"],
        "source_health": {
            "counts": payload["source_health"]["counts"],
            "by_category": payload["source_health"]["by_category"],
        },
        "pipeline_state": payload["pipeline_state"],
        "storage": {
            "postgres_database_bytes": payload["storage"]["postgres_database_bytes"],
            "artifact_store": payload["storage"]["artifact_store"],
        },
        "rolling_windows": payload["rolling_windows"],
        "hourly_series": payload["hourly_series"],
        "category_hourly_series": payload["category_hourly_series"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project data-plane metrics into static website data"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    projected = _projection(payload)
    expected = (
        "window.DATA_PLANE_RUNTIME = "
        + json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated data-plane website projection: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
