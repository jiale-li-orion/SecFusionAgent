from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from apps.evaluation_runtime import (
    M3BenchmarkRecorder,
    ensure_benchmark_deployment_revision,
)
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
)
from packages.evaluation.m1_m3 import EnrichmentScore
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


async def _register(
    report: dict[str, object],
    *,
    suite_id: str,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, str]:
    cases = report.get("cases")
    case_scores = report.get("case_scores")
    gold_revision = report.get("gold_revision")
    profile = report.get("profile")
    formal_dimensions = report.get("formal_dimensions")
    if not isinstance(cases, list) or not all(isinstance(item, str) for item in cases):
        raise ValueError("benchmark report cases are invalid")
    if not isinstance(case_scores, dict):
        raise ValueError("benchmark report case_scores are missing")
    if not isinstance(gold_revision, str) or not gold_revision:
        raise ValueError("benchmark report gold_revision is missing")
    if not isinstance(profile, str) or not profile:
        raise ValueError("benchmark report profile is missing")
    if not isinstance(formal_dimensions, list) or not all(
        isinstance(item, str) for item in formal_dimensions
    ):
        raise ValueError("benchmark report formal_dimensions are invalid")

    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    recorder = M3BenchmarkRecorder(store)
    now = datetime.now(UTC)
    try:
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            case_refs: list[str] = []
            for cve_id in cases:
                case_ref = f"{cve_id}@{suite_revision}"
                case_refs.append(case_ref)
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=cve_id,
                        case_revision=suite_revision,
                        input={"cve_id": cve_id},
                        execution_profile="offline_scorer",
                        target_refs=[f"cve:{cve_id}"],
                        expected_behavior={
                            "formal_dimensions": list(formal_dimensions),
                            "profile": profile,
                        },
                        gold_ref=f"{gold_revision}#{cve_id}",
                        tags=["real-structured", "live-provider-gold"],
                        latency_class="offline",
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            suite = BenchmarkSuite(
                suite_id=suite_id,
                suite_revision=suite_revision,
                domain=BenchmarkDomain.M3_ENRICHMENT,
                purpose="Real structured provider enrichment regression",
                case_refs=case_refs,
                gold_revision=gold_revision,
                evaluator_revision=profile,
                scoring_profile={"formal_dimensions": list(formal_dimensions)},
                created_at=now,
            )
            await store.register_suite(session, suite)
            run = await store.start_run(
                session,
                suite_ref=f"{suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_EXTERNAL,
                environment=settings.environment,
                model_config_ref=(
                    f"model:{settings.model_name}" if settings.model_name else "model:unconfigured"
                ),
                now=now,
            )
            for cve_id in cases:
                raw_case = case_scores.get(cve_id)
                if not isinstance(raw_case, dict) or not isinstance(raw_case.get("score"), dict):
                    raise ValueError(f"missing case score for {cve_id}")
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{cve_id}@{suite_revision}",
                    now=now,
                )
                score = EnrichmentScore.model_validate(raw_case["score"])
                await recorder.record_case_score(
                    session,
                    case_run_id=case_run.case_run_id,
                    score=score,
                    subject_ref=f"cve:{cve_id}",
                )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    now=now,
                )
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )
        return {
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{suite_id}@{suite_revision}",
            "gold_revision": gold_revision,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persist a frozen real-enrichment report into the TD3 benchmark runtime"
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite-id", default="m3-real-structured")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("benchmark report must be a JSON object")
    result = asyncio.run(
        _register(
            report,
            suite_id=args.suite_id,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
