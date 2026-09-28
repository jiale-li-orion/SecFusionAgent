from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, JsonValue, model_validator

from apps.evaluation_runtime import (
    QABenchmarkRecorder,
    ensure_benchmark_deployment_revision,
    load_product_qa_prediction,
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
from packages.evaluation.qa import (
    QAAdjudicationRecord,
    QAGold,
    QAPrediction,
    score_qa,
    validate_qa_adjudication_history,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


class QABenchmarkManifestCase(BaseModel):
    case_id: str
    input: dict[str, JsonValue] = Field(default_factory=dict)
    gold: QAGold
    prediction: QAPrediction | None = None
    product_case_id: str | None = None
    citation_support: dict[str, bool] = Field(default_factory=dict)
    relation_paths: list[list[str]] = Field(default_factory=list)
    interactive_latency_seconds: float | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    latency_class: str = "interactive"
    execution_refs: list[str] = Field(default_factory=list)
    adjudications: list[QAAdjudicationRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_prediction_source(self) -> QABenchmarkManifestCase:
        if (self.prediction is None) == (self.product_case_id is None):
            raise ValueError("QA case requires exactly one of prediction or product_case_id")
        if self.prediction is not None and self.prediction.case_id != self.case_id:
            raise ValueError("QA inline prediction case_id does not match manifest case")
        for key in self.citation_support:
            index, separator, evidence_ref = key.partition(":")
            if not separator or not index.isdigit() or not evidence_ref:
                raise ValueError(
                    "citation_support keys must use '<conclusion_index>:<evidence_ref>'"
                )
        validate_qa_adjudication_history(self.adjudications)
        return self


class QABenchmarkManifest(BaseModel):
    suite_id: str = "m6-qa"
    purpose: str = "Frozen QA accuracy, grounding, citation and multi-hop benchmark"
    evaluator_revision: str = "qa-v1"
    cases: list[QABenchmarkManifestCase]


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


async def _run(
    manifest: QABenchmarkManifest,
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, Any]:
    if not manifest.cases:
        raise ValueError("QA benchmark manifest must contain at least one case")
    case_ids = [item.case_id for item in manifest.cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("QA benchmark case ids must be unique")
    for item in manifest.cases:
        if item.gold.case_id != item.case_id:
            raise ValueError(f"QA case identity mismatch: {item.case_id}")

    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    recorder = QABenchmarkRecorder(store)
    now = datetime.now(UTC)
    manifest_payload = manifest.model_dump(mode="json")
    manifest_digest = _digest(manifest_payload)
    gold_digest = _digest(
        [
            {
                "gold": item.gold.model_dump(mode="json"),
                "adjudications": [
                    record.model_dump(mode="json") for record in item.adjudications
                ],
            }
            for item in manifest.cases
        ]
    )

    try:
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            predictions: dict[str, QAPrediction] = {}
            for item in manifest.cases:
                if item.prediction is not None:
                    predictions[item.case_id] = item.prediction
                    continue
                assert item.product_case_id is not None
                predictions[item.case_id] = await load_product_qa_prediction(
                    session,
                    benchmark_case_id=item.case_id,
                    product_case_id=item.product_case_id,
                    relation_paths=item.relation_paths,
                    citation_support=_citation_support(item.citation_support),
                    interactive_latency_seconds=item.interactive_latency_seconds,
                    execution_refs=item.execution_refs,
                )
            case_refs: list[str] = []
            for item in manifest.cases:
                prediction = predictions[item.case_id]
                case_ref = f"{item.case_id}@{suite_revision}"
                case_refs.append(case_ref)
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=item.case_id,
                        case_revision=suite_revision,
                        input=item.input,
                        execution_profile=(
                            "product_decision_projection"
                            if item.product_case_id is not None
                            else "offline_scorer"
                        ),
                        target_refs=list(prediction.execution_refs or item.execution_refs),
                        expected_behavior=item.gold.model_dump(mode="json"),
                        gold_ref=f"qa-gold:{gold_digest}#{item.case_id}",
                        tags=["m6", "qa", *item.tags],
                        latency_class=item.latency_class,
                        replay_tier="R0",
                        created_at=now,
                    ),
                )
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=manifest.suite_id,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.M6_QA,
                    purpose=manifest.purpose,
                    case_refs=case_refs,
                    gold_revision=f"qa-gold:{gold_digest}",
                    evaluator_revision=manifest.evaluator_revision,
                    scoring_profile={
                        "manifest_digest": manifest_digest,
                        "metrics": [
                            "answer_accuracy",
                            "groundedness",
                            "citation_correctness",
                            "citation_completeness",
                            "multi_hop_correctness",
                            "unknown_correctness",
                            "conflict_handling",
                            "completion_correctness",
                            "interactive_latency_seconds",
                        ],
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{manifest.suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.OFFLINE_SCORER,
                environment=settings.environment,
                model_config_ref=(
                    f"model:{settings.model_name}" if settings.model_name else "model:unconfigured"
                ),
                now=now,
            )
            per_case: dict[str, object] = {}
            for item in manifest.cases:
                prediction = predictions[item.case_id]
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{item.case_id}@{suite_revision}",
                    now=now,
                )
                score = score_qa(gold=item.gold, prediction=prediction)
                await recorder.record_case_score(
                    session,
                    case_run_id=case_run.case_run_id,
                    score=score,
                    subject_ref=f"qa-case:{item.case_id}",
                )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    artifact_refs=list(prediction.execution_refs or item.execution_refs),
                    now=now,
                )
                per_case[item.case_id] = score.model_dump(mode="json")
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
                now=now,
            )
        return {
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{manifest.suite_id}@{suite_revision}",
            "manifest_digest": manifest_digest,
            "gold_revision": f"qa-gold:{gold_digest}",
            "case_count": len(manifest.cases),
            "case_scores": per_case,
        }
    finally:
        await engine.dispose()


def _citation_support(values: dict[str, bool]) -> dict[tuple[int, str], bool]:
    result: dict[tuple[int, str], bool] = {}
    for key, supports in values.items():
        index, _, evidence_ref = key.partition(":")
        result[(int(index), evidence_ref)] = supports
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score a frozen QA manifest and persist it in the TD3 benchmark runtime"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = QABenchmarkManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    result = asyncio.run(
        _run(
            manifest,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
