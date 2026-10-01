from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator

from apps.evaluation_runtime import (
    InvestigationBenchmarkRecorder,
    InvestigationCompletionTrace,
    ensure_benchmark_deployment_revision,
    load_investigation_completion_trace,
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
from packages.evaluation.investigation_readiness import MAX_PROSPECTIVE_FREEZE_LAG_SECONDS
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory


class InvestigationBenchmarkManifestCase(BaseModel):
    case_id: str = Field(min_length=1)
    product_case_id: str = Field(min_length=1)
    expected_final_decision: bool = True
    measurement_deadline: datetime
    tags: list[str] = Field(default_factory=list)
    latency_class: str = "long_investigation"

    @field_validator("measurement_deadline")
    @classmethod
    def deadline_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("measurement_deadline must include timezone")
        return value.astimezone(UTC)


class InvestigationBenchmarkManifest(BaseModel):
    suite_id: str = "m6-long-investigation"
    purpose: str = "Prospectively frozen long-Investigation completion measurement"
    evaluator_revision: str = "investigation-completion-v1"
    frozen_at: datetime
    cases: list[InvestigationBenchmarkManifestCase] = Field(min_length=1)

    @field_validator("frozen_at")
    @classmethod
    def frozen_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("frozen_at must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_manifest(self) -> InvestigationBenchmarkManifest:
        case_ids = [item.case_id for item in self.cases]
        product_case_ids = [item.product_case_id for item in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("investigation benchmark case_id values must be unique")
        if len(set(product_case_ids)) != len(product_case_ids):
            raise ValueError("one Product Case cannot appear twice in one frozen denominator")
        for item in self.cases:
            if item.measurement_deadline <= self.frozen_at:
                raise ValueError("measurement_deadline must be after manifest frozen_at")
        return self


class InvestigationMeasurementStatus(BaseModel):
    case_id: str
    product_case_id: str
    status: Literal["ready", "pending"]
    final_decision_present: bool
    final_decision_at: datetime | None = None
    measurement_deadline: datetime


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


def _measurement_status(
    item: InvestigationBenchmarkManifestCase,
    trace: InvestigationCompletionTrace,
    *,
    frozen_at: datetime,
    measured_at: datetime,
) -> InvestigationMeasurementStatus:
    if measured_at.tzinfo is None:
        raise ValueError("measured_at must include timezone")
    measured_at = measured_at.astimezone(UTC)
    frozen_at = frozen_at.astimezone(UTC)
    if frozen_at > measured_at:
        raise ValueError("manifest frozen_at is in the future relative to measurement time")
    if trace.case_created_at > frozen_at:
        raise ValueError(
            "Product Case was created after manifest frozen_at; prospective freeze is invalid"
        )
    freeze_lag_seconds = (frozen_at - trace.case_created_at).total_seconds()
    if freeze_lag_seconds > MAX_PROSPECTIVE_FREEZE_LAG_SECONDS:
        raise ValueError(
            "Product Case was not frozen promptly after creation; prospective denominator "
            f"requires freeze lag <= {MAX_PROSPECTIVE_FREEZE_LAG_SECONDS:.0f}s, "
            f"observed={freeze_lag_seconds:.3f}s"
        )
    if trace.final_decision_at is not None and trace.final_decision_at <= frozen_at:
        raise ValueError(
            "Product Case already had a final decision before manifest frozen_at; "
            "retrospective case selection is not formal competition evidence"
        )
    status: Literal["ready", "pending"] = "ready"
    if trace.final_decision_at is None and measured_at < item.measurement_deadline:
        status = "pending"
    return InvestigationMeasurementStatus(
        case_id=item.case_id,
        product_case_id=item.product_case_id,
        status=status,
        final_decision_present=trace.final_decision_present,
        final_decision_at=trace.final_decision_at,
        measurement_deadline=item.measurement_deadline,
    )


async def _load_and_validate(
    manifest: InvestigationBenchmarkManifest,
    *,
    measured_at: datetime,
) -> tuple[dict[str, InvestigationCompletionTrace], list[InvestigationMeasurementStatus]]:
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    traces: dict[str, InvestigationCompletionTrace] = {}
    statuses: list[InvestigationMeasurementStatus] = []
    try:
        async with factory() as session:
            for item in manifest.cases:
                trace = await load_investigation_completion_trace(
                    session,
                    item.product_case_id,
                )
                traces[item.case_id] = trace
                statuses.append(
                    _measurement_status(
                        item,
                        trace,
                        frozen_at=manifest.frozen_at,
                        measured_at=measured_at,
                    )
                )
        return traces, statuses
    finally:
        await engine.dispose()


async def _run(
    manifest: InvestigationBenchmarkManifest,
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
    preflight_only: bool = False,
    measured_at: datetime | None = None,
) -> dict[str, Any]:
    now = (measured_at or datetime.now(UTC)).astimezone(UTC)
    traces, statuses = await _load_and_validate(manifest, measured_at=now)
    if preflight_only:
        return {
            "suite_id": manifest.suite_id,
            "manifest_digest": _digest(manifest.model_dump(mode="json")),
            "frozen_at": manifest.frozen_at.isoformat(),
            "measured_at": now.isoformat(),
            "case_count": len(manifest.cases),
            "statuses": [item.model_dump(mode="json") for item in statuses],
        }
    pending = [item.case_id for item in statuses if item.status == "pending"]
    if pending:
        raise RuntimeError(
            "investigation measurement window is still open for frozen cases: "
            + ", ".join(pending)
        )

    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    recorder = InvestigationBenchmarkRecorder(store)
    manifest_digest = _digest(manifest.model_dump(mode="json"))
    expectation_digest = _digest(
        [
            {
                "case_id": item.case_id,
                "product_case_id": item.product_case_id,
                "expected_final_decision": item.expected_final_decision,
                "measurement_deadline": item.measurement_deadline.isoformat(),
            }
            for item in manifest.cases
        ]
    )
    gold_revision = f"investigation-expectation:{expectation_digest}"
    case_refs = [f"{item.case_id}@{suite_revision}" for item in manifest.cases]

    try:
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            for item in manifest.cases:
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=item.case_id,
                        case_revision=suite_revision,
                        input=cast(
                            dict[str, JsonValue],
                            {
                                "product_case_id": item.product_case_id,
                                "manifest_frozen_at": manifest.frozen_at.isoformat(),
                                "measurement_deadline": item.measurement_deadline.isoformat(),
                            },
                        ),
                        execution_profile="persisted_long_investigation_measurement",
                        target_refs=[f"case:{item.product_case_id}"],
                        expected_behavior=cast(
                            dict[str, JsonValue],
                            {
                                "expected_final_decision": item.expected_final_decision,
                                "measurement_deadline": item.measurement_deadline.isoformat(),
                            },
                        ),
                        gold_ref=f"{gold_revision}#{item.case_id}",
                        tags=["m5", "m6", "long-investigation", *item.tags],
                        latency_class=item.latency_class,
                        replay_tier="R0",
                        created_at=manifest.frozen_at,
                    ),
                )
            await store.register_suite(
                session,
                BenchmarkSuite(
                    suite_id=manifest.suite_id,
                    suite_revision=suite_revision,
                    domain=BenchmarkDomain.PRODUCT_E2E,
                    purpose=manifest.purpose,
                    case_refs=case_refs,
                    gold_revision=gold_revision,
                    evaluator_revision=manifest.evaluator_revision,
                    scoring_profile={
                        "manifest_digest": manifest_digest,
                        "frozen_at": manifest.frozen_at.isoformat(),
                        "max_prospective_freeze_lag_seconds": (
                            MAX_PROSPECTIVE_FREEZE_LAG_SECONDS
                        ),
                        "metrics": [
                            "agent.task_success",
                            "m6.investigation_final_decision_completion",
                            "m6.investigation_time_to_final_decision_seconds",
                            "m6.investigation_role_episode_count",
                            "m6.investigation_open_need_count_at_measurement",
                        ],
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{manifest.suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_CONTROLLED,
                environment=settings.environment,
                model_config_ref=(
                    f"model:{settings.model_name}" if settings.model_name else "model:unconfigured"
                ),
                now=now,
            )

        per_case: dict[str, object] = {}
        for item in manifest.cases:
            trace = traces[item.case_id]
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{item.case_id}@{suite_revision}",
                    now=now,
                )
                await recorder.record_completion_trace(
                    session,
                    case_run_id=case_run.case_run_id,
                    trace=trace,
                    subject_ref=f"case:{item.product_case_id}",
                    expected_final_decision=item.expected_final_decision,
                    decision_deadline=item.measurement_deadline,
                )
                artifacts = [
                    f"case:{item.product_case_id}",
                    f"case-revision:{item.product_case_id}@{trace.case_revision}",
                ]
                if trace.final_decision_ref is not None:
                    artifacts.append(trace.final_decision_ref)
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    decision_ref=trace.final_decision_ref,
                    artifact_refs=artifacts,
                    now=now,
                )
            deadline_met = (
                trace.final_decision_at <= item.measurement_deadline
                if trace.final_decision_at is not None
                else False
            )
            per_case[item.case_id] = {
                "product_case_id": item.product_case_id,
                "expected_final_decision": item.expected_final_decision,
                "final_decision_present": trace.final_decision_present,
                "final_decision_ref": trace.final_decision_ref,
                "time_to_final_decision_seconds": trace.time_to_final_decision_seconds,
                "measurement_deadline": item.measurement_deadline.isoformat(),
                "deadline_met": deadline_met,
                "investigation_episode_count": trace.investigation_episode_count,
                "open_evidence_need_count": trace.open_evidence_need_count,
            }

        async with factory() as session, session.begin():
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
            "gold_revision": gold_revision,
            "frozen_at": manifest.frozen_at.isoformat(),
            "measured_at": now.isoformat(),
            "case_count": len(manifest.cases),
            "execution_mode": BenchmarkExecutionMode.LIVE_CONTROLLED.value,
            "cases": per_case,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure prospectively frozen Product Investigation cases and persist "
            "long-Investigation metrics in the TD3 benchmark runtime"
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--suite-revision", type=int, required=True)
    parser.add_argument("--deployment-revision-id")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = InvestigationBenchmarkManifest.model_validate_json(
        args.manifest.read_text(encoding="utf-8")
    )
    result = asyncio.run(
        _run(
            manifest,
            suite_revision=args.suite_revision,
            deployment_revision_id=args.deployment_revision_id,
            preflight_only=args.preflight_only,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
