from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    MetricObservationModel,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def query_report_evidence(
    report_path: Path,
    *,
    metric_name: str | None = None,
) -> dict[str, Any]:
    report_text = await asyncio.to_thread(report_path.read_text, encoding="utf-8")
    payload = json.loads(report_text)
    run_ids = payload.get("benchmark_run_ids")
    if not isinstance(run_ids, list) or not all(isinstance(item, str) for item in run_ids):
        raise ValueError("competition report JSON must contain benchmark_run_ids[]")

    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            runs = list(
                await session.scalars(
                    select(BenchmarkRunModel)
                    .where(BenchmarkRunModel.benchmark_run_id.in_(run_ids))
                    .order_by(BenchmarkRunModel.started_at)
                )
            )
            if {item.benchmark_run_id for item in runs} != set(run_ids):
                missing = sorted(set(run_ids) - {item.benchmark_run_id for item in runs})
                raise RuntimeError(
                    "CompetitionReport references missing BenchmarkRun rows: "
                    f"{missing}"
                )

            case_runs = list(
                await session.scalars(
                    select(BenchmarkCaseRunModel).where(
                        BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids)
                    )
                )
            )
            case_run_ids = [item.case_run_id for item in case_runs]
            metric_query = select(MetricObservationModel).where(
                MetricObservationModel.case_run_id.in_(case_run_ids)
            )
            if metric_name is not None:
                metric_query = metric_query.where(MetricObservationModel.metric_name == metric_name)
            observations = list(
                await session.scalars(
                    metric_query.order_by(
                        MetricObservationModel.metric_name,
                        MetricObservationModel.created_at,
                    )
                )
            )

            case_to_run = {item.case_run_id: item.benchmark_run_id for item in case_runs}
            return {
                "report_id": payload.get("report_id"),
                "report_digest": payload.get("report_digest"),
                "declared_deployment_revision_id": payload.get("deployment_revision_id"),
                "runs": [
                    {
                        "benchmark_run_id": item.benchmark_run_id,
                        "suite_ref": item.suite_ref,
                        "deployment_revision_id": item.deployment_revision_id,
                        "world_snapshot_ref": item.world_snapshot_ref,
                        "model_config_ref": item.model_config_ref,
                        "execution_mode": item.execution_mode,
                        "status": item.status,
                        "started_at": item.started_at.isoformat(),
                        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                    }
                    for item in runs
                ],
                "metric_observations": [
                    {
                        "metric_observation_id": item.metric_observation_id,
                        "benchmark_run_id": case_to_run[item.case_run_id],
                        "case_run_id": item.case_run_id,
                        "metric_name": item.metric_name,
                        "metric_definition_revision": item.metric_definition_revision,
                        "value": item.value,
                        "unit": item.unit,
                        "measurement_source": item.measurement_source,
                        "subject_ref": item.subject_ref,
                        "evidence_refs": item.evidence_refs_json,
                        "metadata": item.metadata_json,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in observations
                ],
            }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query durable BenchmarkRun/MetricObservation rows referenced by a report JSON"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmarks/competition/current.json"),
    )
    parser.add_argument("--metric")
    args = parser.parse_args()
    result = asyncio.run(query_report_evidence(args.report, metric_name=args.metric))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
