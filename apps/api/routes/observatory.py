from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from apps.api.dependencies import SessionDep
from apps.application.views.observatory import CompetitionProofView, ProofMetricView, ProofTargetView
from packages.evaluation.benchmark.storage import BenchmarkCaseRunModel, BenchmarkRunModel

router = APIRouter(prefix="/api/v1/observatory", tags=["observatory"])

_COMPETITION_REPORT = Path("benchmarks/competition/current.json")
_EVAL_INFRA = Path("benchmarks/evaluation-infra/current.json")
_HEADLINE_METRICS = {
    "m1.monitoring.within_6h_rate",
    "m1.source_delivery_coverage",
    "m3.true_positive",
    "m3.false_positive",
    "m3.false_negative",
    "m3.micro_precision",
    "m3.micro_recall",
    "m6.answer_accuracy",
    "m6.groundedness",
    "m6.citation_correctness",
    "m6.citation_completeness",
    "m6.interactive_latency_seconds",
    "m6.session_context_chain_correctness",
    "m6.session_target_carry_correctness",
    "m6.session_retrieval_invocation_coverage",
    "m6.session_retrieval_reuse_rate",
    "engineering.fault_recovery_success",
}


@router.get("/proof", response_model=CompetitionProofView)
async def competition_proof(session: SessionDep) -> CompetitionProofView:
    report = _load_json(_COMPETITION_REPORT)
    infra = _load_json(_EVAL_INFRA)
    run_ids = list(report.get("benchmark_run_ids", []))

    completed_runs = int(
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkRunModel)
            .where(
                BenchmarkRunModel.benchmark_run_id.in_(run_ids),
                BenchmarkRunModel.status == "completed",
            )
        )
        or 0
    )
    passed_cases = int(
        await session.scalar(
            select(func.count())
            .select_from(BenchmarkCaseRunModel)
            .where(
                BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids),
                BenchmarkCaseRunModel.status == "passed",
            )
        )
        or 0
    )

    groups = list(infra.get("metric_groups", []))
    return CompetitionProofView(
        report_id=str(report["report_id"]),
        report_digest=str(report["report_digest"]),
        deployment_revision_id=str(report["deployment_revision_id"]),
        generated_at=report["generated_at"],
        benchmark_runs_completed=completed_runs,
        case_runs_passed=passed_cases,
        registered_core_metrics=int(infra.get("registered_core_metric_count", 0)),
        observed_core_metrics=int(infra.get("observed_metric_name_count", 0)),
        metric_groups=int(infra.get("contract_group_count", len(groups))),
        observed_metric_groups=sum(1 for group in groups if group.get("status") == "observed"),
        partial_metric_groups=sum(1 for group in groups if group.get("status") == "partial"),
        unevaluated_core_metrics=[
            name
            for name, count in infra.get("observed_metric_counts", {}).items()
            if int(count) == 0
        ],
        headline_metrics=[
            ProofMetricView(
                metric_name=str(metric["metric_name"]),
                value=float(metric["value"]),
                unit=metric.get("unit"),
                direction=str(metric.get("direction", "informational")),
            )
            for metric in report.get("metrics", [])
            if metric.get("metric_name") in _HEADLINE_METRICS
        ],
        target_checks=[
            ProofTargetView(
                target_name=str(item["target_name"]),
                requirement=str(item["requirement"]),
                metric_name=str(item["metric_name"]),
                observed_value=float(item["observed_value"]),
                threshold=float(item["threshold"]),
                comparator=str(item["comparator"]),
                status=str(item["status"]),
            )
            for item in report.get("target_checks", [])
        ],
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"observatory artifact unavailable: {path.name}",
        ) from exc
