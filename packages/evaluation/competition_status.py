from __future__ import annotations

from packages.evaluation.benchmark import CompetitionReport


def render_competition_report_markdown(report: CompetitionReport) -> str:
    lines = [
        "<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->",
        "# SecFusionAgent Competition Evaluation Report",
        "",
        f"- Report: `{report.report_id}`",
        f"- Digest: `{report.report_digest}`",
        f"- Deployment: `{report.deployment_revision_id}`",
        f"- Benchmark runs: {', '.join(f'`{item}`' for item in report.benchmark_run_ids)}",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        "",
        "## Competition target checks",
        "",
        "| Target | Metric | Observed | Requirement | Status |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for check in report.target_checks:
        observed = "—" if check.observed_value is None else f"{check.observed_value:.6g}"
        lines.append(
            f"| {check.target_name} | `{check.metric_name}` | {observed} | "
            f"{check.comparator} {check.threshold:g} | **{check.status.value}** |"
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Metric | Value | Unit | Definition | Aggregation | Cases |",
            "| --- | ---: | --- | --- | --- | ---: |",
        ]
    )
    for metric in report.metrics:
        lines.append(
            f"| `{metric.metric_name}` | {metric.value:.6g} | {metric.unit or '—'} | "
            f"`@{metric.metric_definition_revision}` | {metric.aggregation.value} | "
            f"{metric.observation_count} |"
        )
    lines.extend(["", "## Metric definitions", ""])
    for metric in report.metrics:
        lines.extend(
            [
                f"### `{metric.metric_name}@{metric.metric_definition_revision}`",
                "",
                f"- denominator: {metric.denominator}",
                f"- missing-value policy: `{metric.missing_value_policy.value}`",
                f"- direction: `{metric.direction.value}`",
                "",
            ]
        )
    lines.extend(["## Not evaluated", ""])
    if report.unevaluated_competition_areas:
        lines.extend(f"- {item}" for item in report.unevaluated_competition_areas)
    else:
        lines.append("- None")
    lines.extend(["", "## Drill-down coordinates", ""])
    for metric in report.metrics:
        lines.append(
            f"- `{metric.metric_name}`: runs={metric.benchmark_run_ids}; "
            f"case_runs={metric.case_run_ids}"
        )
    if report.artifact_refs:
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- `{item}`" for item in report.artifact_refs)
    return "\n".join(lines) + "\n"
