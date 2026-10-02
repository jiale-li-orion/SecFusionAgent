from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(payload: dict[str, object]) -> str:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    cases = payload["cases"]
    assert isinstance(cases, dict)
    lines = [
        "# M2 Controlled Diagnostics",
        "",
        f"BenchmarkRun `{payload['benchmark_run_id']}` / `{payload['suite_ref']}`.",
        "",
        (
            "This is a deterministic controlled diagnostic suite. It does not replace M3 "
            "competition precision/recall."
        ),
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for name, value in sorted(metrics.items()):
        lines.append(f"| `{name}` | {float(value):.3f} |")
    lines.extend(["", "## Cases", "", "| Case | Passed |", "| --- | --- |"])
    for case_id, item in cases.items():
        assert isinstance(item, dict)
        lines.append(f"| `{case_id}` | {'PASS' if item['passed'] else 'FAIL'} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    rendered = render(payload)
    if args.check:
        if not args.output.exists() or args.output.read_text() != rendered:
            raise SystemExit(f"{args.output} is stale; rerun m2 diagnostics renderer")
        return
    args.output.write_text(rendered)


if __name__ == "__main__":
    main()
