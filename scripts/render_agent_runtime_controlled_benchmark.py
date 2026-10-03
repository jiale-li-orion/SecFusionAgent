from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# Controlled M5 Agent runtime benchmark",
        "",
        (
            f"Run `{payload['benchmark_run_id']}` on `{payload['deployment_revision_id']}` / "
            f"suite `{payload['suite_ref']}`."
        ),
        "",
        (
            "Scope: **controlled runtime regression, not a live-external Agent quality score**. "
            "Each case exercises the production owner for one M5 failure-chain property with "
            "deterministic fixtures and persists the result as TD3 "
            "BenchmarkRun/CaseRun/MetricObservation."
        ),
        "",
        "| Case | Metrics |",
        "| --- | --- |",
    ]
    for case_id, item in payload["cases"].items():
        metrics = ", ".join(
            f"`{name}`={float(value):.3f}" for name, value in item["metrics"].items()
        )
        lines.append(f"| `{case_id}` | {metrics} |")
    lines.extend(
        [
            "",
            "The controlled denominator currently covers:",
            "",
            "- Evidence acquisition usefulness/redundancy, source-role and freshness satisfaction;",
            "- Capability selection, canonical arguments and invocation audit;",
            "- Parent/child delegation, budget inheritance and dependency wake/resume;",
            "- Health-ranked capability binding fallback before invocation;",
            "- Conflict preservation in the M4 StatePatch gate;",
            (
                "- Failed InvestigationRole episode → same Case/EvidenceNeed → "
                "successful recovery episode;"
            ),
            "- No-progress and pre-execution deadline bounded-stop behavior.",
            "",
            (
                "Health-ranked fallback does not claim automatic retry after an already-selected "
                "binding fails. Current TD2 semantics choose among eligible bindings using "
                "provider health and `fallback_rank`; invocation-failure retry would be a "
                "separate runtime policy."
            ),
            "",
            (
                "Monetary provider/capability cost is not synthesized here. It remains "
                "`not_evaluated` unless the executing provider/capability returns an exact amount."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render controlled M5 Agent runtime benchmark")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated Agent runtime benchmark: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
