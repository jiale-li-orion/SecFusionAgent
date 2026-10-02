from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any]) -> str:
    covered = payload["covered_classes"]
    uncovered = payload["uncovered_classes"]
    lines = [
        "# M7 adversarial security coverage benchmark",
        "",
        (
            f"Run `{payload['benchmark_run_id']}` / suite `{payload['suite_ref']}` on "
            f"`{payload['deployment_revision_id']}`."
        ),
        "",
        (
            "Frozen profile: TD3 v1 adversarial classes. Coverage measures how much of that "
            "profile has a production-boundary probe; pass rate is computed only across covered "
            "classes. Uncovered classes remain explicit gaps and are not counted as passes."
        ),
        "",
        f"Class coverage: **{float(payload['adversarial_class_coverage']):.3f}** "
        f"({len(covered)}/{len(payload['required_classes'])}).",
        "",
        f"Executed covered cases: **{int(payload['executed_case_count'])}**.",
        "",
        f"Covered-case pass rate: **{float(payload['adversarial_case_pass_rate']):.3f}**.",
        "",
        "| Adversarial class | Coverage | Verdict |",
        "| --- | --- | --- |",
    ]
    for adversarial_class in payload["required_classes"]:
        item = payload["cases"][adversarial_class]
        if not item["covered"]:
            verdict = "NOT_EVALUATED"
        else:
            verdict = "PASS" if item["passed"] else "FAIL"
        lines.append(
            f"| `{adversarial_class}` | "
            f"{'covered' if item['covered'] else 'uncovered'} | {verdict} |"
        )
    lines.extend(
        [
            "",
            "Covered classes: " + ", ".join(f"`{item}`" for item in covered) + ".",
            "",
            "Uncovered classes: "
            + (", ".join(f"`{item}`" for item in uncovered) if uncovered else "none")
            + ".",
            "",
        ]
    )
    if uncovered:
        lines.append(
            "A perfect covered-case pass rate does not mean the adversarial suite is complete. "
            "Class coverage is the breadth signal; uncovered classes remain NOT_EVALUATED."
        )
    else:
        lines.append(
            "All frozen TD3 v1 adversarial classes now have production-boundary probes. A 1.0 "
            "pass rate means this frozen profile currently passes; future adversarial classes or "
            "stronger attack variants require a new suite revision rather than reinterpretation."
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render M7 adversarial security benchmark")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated adversarial security benchmark: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
