from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from apps.evaluation_runtime import M3BenchmarkRecorder, ensure_benchmark_deployment_revision
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

VERSION_RE = re.compile(r"^(?P<base>.+?)(?P<version>v\d+)?$")


def _base_id(arxiv_id: str) -> str:
    match = VERSION_RE.match(arxiv_id)
    return match.group("base") if match is not None else arxiv_id


async def _register(
    report: dict[str, object],
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, str]:
    cases = report.get("cases")
    case_scores = report.get("case_scores")
    gold_revision = report.get("gold_revision")
    profile = report.get("profile")
    formal_dimensions = report.get("formal_dimensions")
    paper_revisions = report.get("paper_revisions")
    if not isinstance(cases, list) or not all(isinstance(item, str) for item in cases):
        raise ValueError("research benchmark cases are invalid")
    if not isinstance(case_scores, dict):
        raise ValueError("research benchmark case_scores are missing")
    if not isinstance(gold_revision, str) or not gold_revision:
        raise ValueError("research benchmark gold_revision is missing")
    if not isinstance(profile, str) or not profile:
        raise ValueError("research benchmark profile is missing")
    if not isinstance(formal_dimensions, list) or not all(
        isinstance(item, str) for item in formal_dimensions
    ):
        raise ValueError("research benchmark formal_dimensions are invalid")
    if not isinstance(paper_revisions, dict):
        raise ValueError("research benchmark paper_revisions are missing")

    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    recorder = M3BenchmarkRecorder(store)
    now = datetime.now(UTC)
    suite_id = "m3-research-exact-cve"
    try:
        async with factory() as session, session.begin():
            deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            case_refs: list[str] = []
            for arxiv_id in cases:
                base_id = _base_id(arxiv_id)
                case_id = f"research:arxiv:{arxiv_id}"
                case_ref = f"{case_id}@{suite_revision}"
                case_refs.append(case_ref)
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=case_id,
                        case_revision=suite_revision,
                        input={"arxiv_id": arxiv_id},
                        execution_profile="offline_scorer",
                        target_refs=[f"arxiv:{base_id}"],
                        expected_behavior={
                            "formal_dimensions": list(formal_dimensions),
                            "profile": profile,
                            "paper_revision": paper_revisions.get(arxiv_id),
                        },
                        gold_ref=f"{gold_revision}#{arxiv_id}",
                        tags=["real-research", "arxiv", "exact-cve-anchor"],
                        latency_class="offline",
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=suite_id,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.M3_ENRICHMENT,
                    purpose="Exact paper-to-vulnerability association regression",
                    case_refs=case_refs,
                    gold_revision=gold_revision,
                    evaluator_revision=profile,
                    scoring_profile={"formal_dimensions": list(formal_dimensions)},
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{suite_id}@{suite_revision}",
                deployment_revision_id=deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_EXTERNAL,
                environment=settings.environment,
                model_config_ref="model:unconfigured",
                now=now,
            )
            for arxiv_id in cases:
                base_id = _base_id(arxiv_id)
                raw_case = case_scores.get(arxiv_id)
                if not isinstance(raw_case, dict) or not isinstance(raw_case.get("score"), dict):
                    raise ValueError(f"missing research case score for {arxiv_id}")
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"research:arxiv:{arxiv_id}@{suite_revision}",
                    now=now,
                )
                score = EnrichmentScore.model_validate(raw_case["score"])
                await recorder.record_case_score(
                    session,
                    case_run_id=case_run.case_run_id,
                    score=score,
                    subject_ref=f"arxiv:{base_id}",
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
            "deployment_revision_id": deployment_id,
            "suite_ref": f"{suite_id}@{suite_revision}",
            "gold_revision": gold_revision,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist exact paper-CVE M3 benchmark results")
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("research benchmark report must be a JSON object")
    result = asyncio.run(
        _register(
            report,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
