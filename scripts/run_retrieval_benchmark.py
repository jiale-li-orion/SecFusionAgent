from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from apps.evaluation_runtime import ensure_benchmark_deployment_revision
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
)
from packages.evaluation.benchmark.metrics import metric_definition
from packages.intelligence.retrieval.operators import build_lexical_search_statement
from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory

INDEX_NAME = "ix_document_chunks_fts_simple"
SUITE_ID = "retrieval-lexical-plan-v1"
EVALUATOR_REVISION = "retrieval-explain-v1"
QUERIES = (
    ("cve-2026", "CVE 2026"),
    ("vulnerability", "vulnerability"),
    ("security", "security"),
    ("patch", "patch"),
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _walk_plan(node: dict[str, Any]) -> list[dict[str, Any]]:
    result = [node]
    for child in node.get("Plans", []):
        if isinstance(child, dict):
            result.extend(_walk_plan(child))
    return result


async def _run(
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
    limit: int,
) -> dict[str, Any]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    now = datetime.now(UTC)
    try:
        async with factory() as session, session.begin():
            resolved_deployment = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            knowledge_revision = await current_knowledge_revision(session)
            world_ref = f"knowledge-revision:{knowledge_revision}"
            case_refs: list[str] = []
            for query_id, query in QUERIES:
                case_id = f"retrieval-lexical-{query_id}"
                case_refs.append(f"{case_id}@{suite_revision}")
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=case_id,
                        case_revision=suite_revision,
                        input={"query": query, "limit": limit},
                        execution_profile="postgres_lexical_explain",
                        target_refs=[f"index:{INDEX_NAME}"],
                        world_snapshot_ref=world_ref,
                        fixture_refs=[],
                        expected_behavior={"index_name": INDEX_NAME},
                        gold_ref=f"retrieval-plan:{INDEX_NAME}",
                        tags=["m6", "retrieval", "fts", "diagnostic"],
                        latency_class="retrieval_operator",
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            suite_payload = {
                "queries": QUERIES,
                "limit": limit,
                "index_name": INDEX_NAME,
                "evaluator_revision": EVALUATOR_REVISION,
            }
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=SUITE_ID,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.PRODUCT_E2E,
                    purpose=(
                        "Diagnostic lexical-retrieval execution-plan regression for M6 QA latency"
                    ),
                    case_refs=case_refs,
                    gold_revision=f"retrieval-plan:{_digest(suite_payload)}",
                    evaluator_revision=EVALUATOR_REVISION,
                    default_world_snapshot_ref=world_ref,
                    scoring_profile={
                        "diagnostic_only": True,
                        "metrics": [
                            "retrieval.lexical_latency_ms",
                            "retrieval.lexical_index_used",
                        ],
                        "required_index": INDEX_NAME,
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{SUITE_ID}@{suite_revision}",
                deployment_revision_id=resolved_deployment,
                execution_mode=BenchmarkExecutionMode.LIVE_CONTROLLED,
                environment=settings.environment,
                model_config_ref=None,
                world_snapshot_ref=world_ref,
                warm_cold_condition="database_warm_unspecified",
                now=now,
            )

        results: dict[str, Any] = {}
        for query_id, query in QUERIES:
            case_id = f"retrieval-lexical-{query_id}"
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{case_id}@{suite_revision}",
                )
            try:
                async with factory() as session:
                    statement = build_lexical_search_statement(query=query, limit=limit)
                    compiled = statement.compile(
                        dialect=postgresql.dialect(),
                        compile_kwargs={"literal_binds": True},
                    )
                    raw = await session.scalar(
                        text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {compiled}")
                    )
                    await session.rollback()
                if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
                    raise RuntimeError("PostgreSQL EXPLAIN JSON has unexpected shape")
                explain = raw[0]
                plan = explain.get("Plan")
                if not isinstance(plan, dict):
                    raise RuntimeError("PostgreSQL EXPLAIN JSON is missing Plan")
                nodes = _walk_plan(plan)
                indexes = [
                    str(node.get("Index Name"))
                    for node in nodes
                    if node.get("Index Name") is not None
                ]
                index_used = INDEX_NAME in indexes
                execution_ms = float(explain.get("Execution Time", 0.0))
                async with factory() as session, session.begin():
                    for metric_name, value in (
                        ("retrieval.lexical_latency_ms", execution_ms),
                        ("retrieval.lexical_index_used", 1.0 if index_used else 0.0),
                    ):
                        definition = metric_definition(metric_name)
                        await store.observe_metric(
                            session,
                            case_run_id=case_run.case_run_id,
                            metric_name=metric_name,
                            value=value,
                            direction=definition.direction,
                            measurement_source=MeasurementSource.EXACT,
                            subject_ref=f"retrieval-query:{query_id}",
                            evidence_refs=[],
                            metadata={
                                "query": query,
                                "limit": limit,
                                "index_name": INDEX_NAME,
                                "observed_indexes": cast(JsonValue, indexes),
                                "top_plan_node": plan.get("Node Type"),
                                "planning_time_ms": explain.get("Planning Time"),
                            },
                        )
                    await store.finish_case_run(
                        session,
                        case_run.case_run_id,
                        status=BenchmarkCaseRunStatus.PASSED,
                        artifact_refs=[f"index:{INDEX_NAME}"],
                    )
                results[query_id] = {
                    "query": query,
                    "execution_time_ms": execution_ms,
                    "index_used": index_used,
                    "observed_indexes": indexes,
                }
            except Exception as exc:
                async with factory() as session, session.begin():
                    await store.finish_case_run(
                        session,
                        case_run.case_run_id,
                        status=BenchmarkCaseRunStatus.FAILED,
                        failure_class=type(exc).__name__,
                    )
                    await store.finish_run(
                        session,
                        run.benchmark_run_id,
                        status=BenchmarkRunStatus.FAILED,
                    )
                raise

        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
            )
        return {
            "schema_version": "retrieval-lexical-benchmark-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment,
            "suite_ref": f"{SUITE_ID}@{suite_revision}",
            "world_snapshot_ref": world_ref,
            "diagnostic_only": True,
            "required_index": INDEX_NAME,
            "query_results": results,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lexical retrieval execution-plan benchmark")
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = asyncio.run(
        _run(
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
            limit=args.limit,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
