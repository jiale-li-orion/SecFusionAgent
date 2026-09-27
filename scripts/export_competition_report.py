from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import CompetitionReport, CompetitionReportService
from packages.evaluation.benchmark.storage import BenchmarkRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def _export(
    run_ids: list[str],
    *,
    deployment_revision_id: str | None,
    artifact_refs: list[str],
) -> CompetitionReport:
    if not run_ids:
        raise ValueError("at least one benchmark run id is required")
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("benchmark run ids must be unique")
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            runs = list(
                await session.scalars(
                    select(BenchmarkRunModel).where(BenchmarkRunModel.benchmark_run_id.in_(run_ids))
                )
            )
            by_id = {item.benchmark_run_id: item for item in runs}
            missing = [item for item in run_ids if item not in by_id]
            if missing:
                raise LookupError(f"benchmark runs not found: {missing}")
            deployment_ids = {item.deployment_revision_id for item in runs}
            if len(deployment_ids) != 1:
                raise ValueError(
                    "competition report cannot mix benchmark runs from different deployments"
                )
            resolved_deployment_id = next(iter(deployment_ids))
            if (
                deployment_revision_id is not None
                and resolved_deployment_id != deployment_revision_id
            ):
                raise ValueError(
                    "selected benchmark runs do not belong to the requested deployment revision"
                )
            return await CompetitionReportService().generate_and_persist(
                session,
                deployment_revision_id=resolved_deployment_id,
                benchmark_run_ids=run_ids,
                artifact_refs=artifact_refs,
            )
    finally:
        await engine.dispose()


def _markdown(report: CompetitionReport) -> str:
    lines = [
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and persist a competition report from completed benchmark runs"
    )
    parser.add_argument("run_ids", nargs="*", help="legacy positional benchmark run ids")
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--artifact-ref", action="append", default=[])
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--output", type=Path, help="legacy alias for --json-output")
    args = parser.parse_args()
    run_ids = [*args.run_ids, *args.run_id]
    report = asyncio.run(
        _export(
            run_ids,
            deployment_revision_id=args.deployment_revision_id,
            artifact_refs=args.artifact_ref,
        )
    )
    payload = report.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json_output = args.json_output or args.output
    if json_output is not None:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(rendered, encoding="utf-8")
    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_markdown(report), encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
