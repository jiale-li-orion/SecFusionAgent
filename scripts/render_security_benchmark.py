from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render(payload: dict[str, Any]) -> str:
    cases = payload["cases"]
    lines = [
        "# Controlled security runtime benchmark",
        "",
        (
            f"Run `{payload['benchmark_run_id']}` on `{payload['deployment_revision_id']}` / "
            f"suite `{payload['suite_ref']}`."
        ),
        "",
        (
            "Scope: **controlled runtime regression, not red-team coverage**. The cases exercise "
            "real authorization/redaction owners with deterministic fixtures and no external "
            "model or provider call."
        ),
        "",
        "| Case | Authority violations | Secret exposures | Policy conformance |",
        "| --- | ---: | ---: | ---: |",
    ]
    for case_id, item in cases.items():
        conformance = item["policy_conformance"]
        rendered_conformance = "—" if conformance is None else f"{float(conformance):.3f}"
        lines.append(
            f"| `{case_id}` | {int(item['authority_violation_count'])} | "
            f"{int(item['secret_exposure_count'])} | {rendered_conformance} |"
        )
    lines.extend(
        [
            "",
            f"Authority violation count: **{int(payload['authority_violation_count'])}**.",
            "",
            f"Secret exposure count: **{int(payload['secret_exposure_count'])}**.",
            "",
            f"Policy conformance: **{float(payload['policy_conformance']):.3f}**.",
            (
                "Controlled gate result: **PASS**."
                if payload["controlled_gate_pass"]
                else "Controlled gate result: **FAIL**."
            ),
            "",
            "The authority cases require CapabilityBroker to reject an out-of-envelope capability "
            "and an implicit-deny invocation before the executor is called. The secret case runs "
            "the production RecordedModelProvider + RuntimeArtifactService on an isolated runtime "
            "substrate and verifies that sentinel credentials are absent from both SQL audit "
            "metadata and the durable normalized request artifact.",
            "",
            "A zero here does not claim resistance to arbitrary prompt injection, exfiltration, "
            "sandbox escape or provider compromise. Those require separate adversarial suites.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render controlled security benchmark")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated security benchmark: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
