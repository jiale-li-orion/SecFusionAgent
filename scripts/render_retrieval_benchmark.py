from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any]) -> str:
    rows = list(payload["query_results"].items())
    latencies = [float(value["execution_time_ms"]) for _, value in rows]
    used = sum(bool(value["index_used"]) for _, value in rows)
    lines = [
        "# Lexical retrieval execution benchmark",
        "",
        (
            f"Run `{payload['benchmark_run_id']}` on `{payload['deployment_revision_id']}` / "
            f"`{payload['world_snapshot_ref']}`. This is a diagnostic M6 retrieval benchmark, "
            "not a direct competition target."
        ),
        "",
        f"Required PostgreSQL expression index: `{payload['required_index']}`.",
        "",
        "| Query | Execution | Index used | Observed indexes |",
        "| --- | ---: | ---: | --- |",
    ]
    for _, item in rows:
        indexes = ", ".join(f"`{index}`" for index in item["observed_indexes"]) or "—"
        lines.append(
            f"| `{item['query']}` | {float(item['execution_time_ms']):.3f} ms | "
            f"{'yes' if item['index_used'] else 'no'} | {indexes} |"
        )
    lines.extend(
        [
            "",
            f"Index-plan coverage: **{used}/{len(rows)}**. "
            f"Latency range: **{min(latencies):.3f}-{max(latencies):.3f} ms**.",
            "",
            "The runner uses the same `to_tsvector('simple', coalesce(text, ''))` predicate as "
            "`LexicalRetrievalOperator` and the migration-owned GIN expression index. A future "
            "query-expression drift therefore becomes a measurable `retrieval.lexical_index_used` "
            "regression instead of a hidden sequential scan.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render lexical retrieval benchmark")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated retrieval benchmark: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
