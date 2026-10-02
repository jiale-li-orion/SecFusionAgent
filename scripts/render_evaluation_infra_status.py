from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# Evaluation infrastructure status",
        "",
        (
            f"Snapshot `{payload['generated_at']}`. This is an infrastructure/readiness "
            "projection, not a competition score."
        ),
        (
            "Observation readiness is evaluated against the current MetricDefinition revision. "
            "Older observations remain historical evidence but do not satisfy a revised contract."
        ),
        "",
        "## Metric contract coverage",
        "",
        (
            "| Group | Owner | Implementation | Observation status | "
            "Observed / Contract | Open metrics |"
        ),
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for group in payload["metric_groups"]:
        open_metrics = ", ".join(f"`{item}`" for item in group["unobserved_metrics"]) or "—"
        lines.append(
            f"| `{group['group_id']}` | {group['owner']} | `{group['implementation']}` | "
            f"**{group['status']}** | "
            f"{len(group['observed_metrics'])}/{group['metric_count']} | {open_metrics} |"
        )
    pending_denominators = [
        group for group in payload["metric_groups"] if group.get("next_denominator")
    ]
    if pending_denominators:
        lines.extend(["", "## Next legal denominators", ""])
        for group in pending_denominators:
            lines.append(
                f"- `{group['group_id']}`: {group['next_denominator']}"
            )
    trace = payload["trace_substrate"]
    lines.extend(
        [
            "",
            "## Durable trace substrate",
            "",
            "| Owner record | Rows |",
            "| --- | ---: |",
        ]
    )
    for key, value in trace.items():
        lines.append(f"| `{key}` | {value} |")

    coverage = payload["benchmark_case_trace_coverage"]
    evidence = payload["metric_evidence_binding"]
    replay = payload["replay_artifact_readiness"]
    latest = payload.get("latest_live_qa_closure")
    latest_investigation = payload.get("latest_live_investigation_closure")
    lines.extend(
        [
            "",
            "## Provenance closure",
            "",
            "| Check | Coverage |",
            "| --- | ---: |",
            f"| CaseRun has artifact refs | {_pct(coverage['with_artifact_refs_rate'])} |",
            f"| CaseRun can reach TaskRun | {_pct(coverage['with_task_ref_rate'])} |",
            f"| CaseRun can reach Execution | {_pct(coverage['with_execution_ref_rate'])} |",
            f"| CaseRun can reach Decision | {_pct(coverage['with_decision_ref_rate'])} |",
            (
                "| All MetricObservation rows carrying EvidenceRefs | "
                f"{_pct(evidence['with_evidence_refs_rate'])} |"
            ),
            (
                "| Citation/groundedness metrics carrying EvidenceRefs | "
                f"{_pct(evidence['citation_metrics_with_evidence_refs_rate'])} |"
            ),
            "",
            (
                "A low global metric→Evidence rate is not automatically a defect: latency/count/"
                "runtime metrics do not require EvidenceRefs. Citation/groundedness metrics do, "
                "so that row is the stronger evidence-chain readiness check."
            ),
            "",
            "## Frozen model-input replay readiness",
            "",
            "| Artifact boundary | Coverage |",
            "| --- | ---: |",
            f"| ModelRequest request artifact | {_pct(replay['model_request_artifact_rate'])} |",
            f"| ModelAttempt response artifact | {_pct(replay['model_response_artifact_rate'])} |",
            (
                "| PromptAssembly request artifact | "
                f"{_pct(replay['prompt_assembly_artifact_rate'])} |"
            ),
            "",
            (
                "These three rows expose the R1 replay gap directly. Hashes/metadata alone support "
                "audit identity, but exact frozen model-input replay requires durable normalized "
                "request/response artifacts."
            ),
        ]
    )
    if latest is not None:
        lines.extend(
            [
                "",
                "## Latest live QA provenance closure",
                "",
                f"BenchmarkRun `{latest['benchmark_run_id']}` / `{latest['suite_ref']}`.",
                "",
                "| Check | Coverage |",
                "| --- | ---: |",
                (
                    "| Citation/groundedness metrics → EvidenceRefs | "
                    f"{_pct(latest['citation_metric_evidence_rate'])} |"
                ),
                (
                    "| ModelRequest → durable request artifact | "
                    f"{_pct(latest['model_request_artifact_rate'])} |"
                ),
                (
                    "| Successful ModelAttempt → durable response artifact | "
                    f"{_pct(latest['model_response_artifact_rate'])} |"
                ),
                f"| Runtime MetricObservation rows | {latest['runtime_metric_observations']} |",
                "",
                (
                    "This scope is intentionally separate from the historical cumulative rows "
                    "above: old BenchmarkRuns remain immutable evidence of earlier infrastructure "
                    "gaps, while the latest live run shows whether the current runner contract "
                    "is closed."
                ),
            ]
        )
    if latest_investigation is not None:
        lines.extend(
            [
                "",
                "## Latest live Long Investigation provenance closure",
                "",
                (
                    f"BenchmarkRun `{latest_investigation['benchmark_run_id']}` / "
                    f"`{latest_investigation['suite_ref']}`."
                ),
                "",
                "| Check | Coverage |",
                "| --- | ---: |",
                (
                    "| M5 planner ModelRequest → durable request artifact | "
                    f"{_pct(latest_investigation['m5_model_request_artifact_rate'])} |"
                ),
                (
                    "| M5 planner successful ModelAttempt → durable response artifact | "
                    f"{_pct(latest_investigation['m5_model_response_artifact_rate'])} |"
                ),
                (
                    "| PromptAssembly → direct request artifact binding | "
                    f"{_pct(latest_investigation['prompt_assembly_artifact_rate'])} |"
                ),
                (
                    "| M6 Decision requests with an ExecutionRun coordinate | "
                    f"{_pct(latest_investigation['m6_decision_execution_coordinate_rate'])} |"
                ),
                (
                    "| Execution-owned M6 Decision request artifact | "
                    f"{_pct(latest_investigation['m6_decision_request_artifact_rate'])} |"
                ),
                (
                    "| Decision EvidenceRef → Observation → EvidenceArtifact | "
                    f"{_pct(latest_investigation['decision_evidence_chain_rate'])} |"
                ),
                "",
                (
                    "M5 planner artifacts are execution-owned and therefore required for current "
                    "runs. Standalone Case-owned M6 Decision calls currently have no independent "
                    "ExecutionRun; their raw payload artifact rate is shown as not applicable "
                    "rather than inventing a new Task/Execution owner. Historical episode debt "
                    "is never backfilled."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Status semantics",
            "",
            "- `observed`: every metric in the group has at least one durable MetricObservation.",
            (
                "- `partial`: the contract exists and some metrics have real observations, but the "
                "group is not complete."
            ),
            (
                "- `contract_ready`: all metric definitions are registered, while a real frozen "
                "denominator/runner is still absent."
            ),
            "",
            (
                "Use `scripts/query_benchmark_evidence.py` with a CompetitionReport or explicit "
                "`--run-id`; `--require-closed` fails when the selected live trace cannot resolve "
                "its model/runtime/Evidence chain."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render evaluation infrastructure status")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    expected = render(payload)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != expected:
            raise SystemExit(f"stale generated evaluation infra report: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
