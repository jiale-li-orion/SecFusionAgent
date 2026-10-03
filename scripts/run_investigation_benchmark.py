from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator
from sqlalchemy import select

from apps.evaluation_runtime import (
    InvestigationBenchmarkRecorder,
    InvestigationCompletionTrace,
    ensure_benchmark_deployment_revision,
    load_execution_measurement_trace,
    load_investigation_completion_trace,
    record_execution_measurements,
)
from apps.runtime_models import register_runtime_models
from packages.evaluation.agent_runtime import (
    AgentRuntimeGold,
    AgentRuntimeObservation,
    score_agent_runtime,
)
from packages.evaluation.benchmark import (
    BenchmarkCase,
    BenchmarkCaseRunStatus,
    BenchmarkDomain,
    BenchmarkExecutionMode,
    BenchmarkRunStatus,
    BenchmarkStore,
    BenchmarkSuite,
    MeasurementSource,
    metric_definition,
)
from packages.evaluation.investigation_readiness import MAX_PROSPECTIVE_FREEZE_LAG_SECONDS
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import CaseStateEventModel, EvidenceNeedModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.storage.models import TaskEventModel, TaskRunModel


class InvestigationBenchmarkManifestCase(BaseModel):
    case_id: str = Field(min_length=1)
    product_case_id: str = Field(min_length=1)
    expected_final_decision: bool = True
    measurement_deadline: datetime
    tags: list[str] = Field(default_factory=list)
    latency_class: str = "long_investigation"
    agent_runtime_gold: AgentRuntimeGold | None = None

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


def _version_reasoning_sources_match_gold(
    source_refs: list[str],
    *,
    allowed_relation_ids: set[str],
    allowed_claim_ids: set[str],
) -> bool:
    if not source_refs:
        return False
    relation_ids: set[str] = set()
    claim_ids: set[str] = set()
    for ref in source_refs:
        if ref.startswith("relation:"):
            relation_ids.add(ref.removeprefix("relation:"))
        elif ref.startswith("claim:"):
            claim_ids.add(ref.removeprefix("claim:"))
        else:
            return False
    return (
        bool(relation_ids & allowed_relation_ids)
        and relation_ids <= allowed_relation_ids
        and claim_ids <= allowed_claim_ids
    )


def _is_version_scoped_assertion(proposition: str) -> bool:
    normalized = proposition.lower()
    return any(
        token in normalized
        for token in ("fixed version", "fixed release", "patched version", "patched release")
    )


def _proposition_matches_expected_fixed_version(
    proposition: str,
    expected_fixed_version: str,
) -> bool:
    if not _is_version_scoped_assertion(proposition):
        return False
    escaped = re.escape(expected_fixed_version)
    return re.search(rf"(?<![0-9A-Za-z])v?{escaped}(?![0-9A-Za-z])", proposition) is not None


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
    evaluator_revision: str | None = None,
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
            "investigation measurement window is still open for frozen cases: " + ", ".join(pending)
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
                "agent_runtime_gold": (
                    item.agent_runtime_gold.model_dump(mode="json")
                    if item.agent_runtime_gold is not None
                    else None
                ),
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
                                "agent_runtime_gold": (
                                    item.agent_runtime_gold.model_dump(mode="json")
                                    if item.agent_runtime_gold is not None
                                    else None
                                ),
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
                    evaluator_revision=evaluator_revision or manifest.evaluator_revision,
                    scoring_profile={
                        "manifest_digest": manifest_digest,
                        "frozen_at": manifest.frozen_at.isoformat(),
                        "max_prospective_freeze_lag_seconds": (MAX_PROSPECTIVE_FREEZE_LAG_SECONDS),
                        "metrics": [
                            "agent.task_success",
                            "m6.investigation_final_decision_completion",
                            "m6.investigation_time_to_first_status_seconds",
                            "m6.investigation_time_to_final_decision_seconds",
                            "m6.investigation_role_episode_count",
                            "m6.investigation_open_need_count_at_measurement",
                            "agent.timeout_rate",
                            "agent.wall_latency_seconds",
                            "runtime.model_attempt_count",
                            "runtime.model_input_tokens",
                            "runtime.model_output_tokens",
                            "runtime.model_reasoning_tokens",
                            "runtime.model_cached_input_tokens",
                            "runtime.model_provider_cost",
                            "runtime.capability_call_count",
                            "runtime.retrieval_invocation_count",
                            "agent.trajectory_conformance",
                            "agent.wrong_entity_attachment_rate",
                            "agent.wrong_version_attachment_rate",
                            "agent.invalid_evidence_ref_rate",
                            "agent.stop_correctness",
                            "agent.unnecessary_continuation_rate",
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
                execution_trace = await load_execution_measurement_trace(
                    session,
                    [
                        *trace.investigation_task_run_refs,
                        *trace.decision_task_run_refs,
                        *trace.execution_refs,
                        *trace.model_request_refs,
                    ],
                )
                await record_execution_measurements(
                    store,
                    session,
                    case_run_id=case_run.case_run_id,
                    trace=execution_trace,
                    subject_ref=f"case:{item.product_case_id}",
                )
                semantic_metrics: dict[str, float] = {}
                if item.agent_runtime_gold is not None:
                    semantic_metrics = await _record_agent_semantic_metrics(
                        store,
                        session,
                        case_run_id=case_run.case_run_id,
                        product_case_id=item.product_case_id,
                        frozen_at=manifest.frozen_at,
                        deadline_met=(
                            trace.final_decision_at is not None
                            and trace.final_decision_at <= item.measurement_deadline
                        ),
                        gold=item.agent_runtime_gold,
                    )
                artifacts = [
                    f"case:{item.product_case_id}",
                    f"case-revision:{item.product_case_id}@{trace.case_revision}",
                    *trace.investigation_task_run_refs,
                    *trace.decision_task_run_refs,
                    *trace.execution_refs,
                    *trace.model_request_refs,
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
                "first_status_event_type": trace.first_status_event_type,
                "first_status_at": (
                    trace.first_status_at.isoformat() if trace.first_status_at is not None else None
                ),
                "time_to_first_status_seconds": trace.time_to_first_status_seconds,
                "time_to_final_decision_seconds": trace.time_to_final_decision_seconds,
                "measurement_deadline": item.measurement_deadline.isoformat(),
                "deadline_met": deadline_met,
                "investigation_episode_count": trace.investigation_episode_count,
                "failed_episode_count": trace.failed_episode_count,
                "timed_out_episode_count": trace.timed_out_episode_count,
                "completed_episode_count": trace.completed_episode_count,
                "agent_wall_latency_seconds": trace.agent_wall_latency_seconds,
                "investigation_episode_statuses": trace.investigation_episode_statuses,
                "open_evidence_need_count": trace.open_evidence_need_count,
                "investigation_task_run_refs": trace.investigation_task_run_refs,
                "decision_task_run_refs": trace.decision_task_run_refs,
                "execution_refs": trace.execution_refs,
                "model_request_refs": trace.model_request_refs,
                "agent_semantic_metrics": semantic_metrics,
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
    parser.add_argument("--evaluator-revision")
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
            evaluator_revision=args.evaluator_revision,
            preflight_only=args.preflight_only,
        )
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


async def _record_agent_semantic_metrics(
    store: BenchmarkStore,
    session,
    *,
    case_run_id: str,
    product_case_id: str,
    frozen_at: datetime,
    deadline_met: bool,
    gold: AgentRuntimeGold,
) -> dict[str, float]:
    state = await InvestigationStateService().get_state(session, product_case_id)
    role_runs = list(
        await session.scalars(
            select(TaskRunModel)
            .where(
                TaskRunModel.case_id == product_case_id,
                TaskRunModel.role_id == "InvestigationRole",
            )
            .order_by(TaskRunModel.created_at)
        )
    )
    task_events = (
        list(
            await session.scalars(
                select(TaskEventModel)
                .where(TaskEventModel.task_run_id.in_([item.run_id for item in role_runs]))
                .order_by(TaskEventModel.emitted_at, TaskEventModel.seq)
            )
        )
        if role_runs
        else []
    )
    case_events = list(
        await session.scalars(
            select(CaseStateEventModel)
            .where(CaseStateEventModel.case_id == product_case_id)
            .order_by(CaseStateEventModel.case_revision)
        )
    )
    needs = list(
        await session.scalars(
            select(EvidenceNeedModel).where(EvidenceNeedModel.case_id == product_case_id)
        )
    )

    state_items = [
        item
        for bucket in (state.confirmed, state.tentative, state.conflicts, state.unknowns)
        for item in bucket
        if item.writer.startswith("InvestigationRole")
    ]
    allowed_targets = set(gold.allowed_target_refs)
    normalized_allowed = allowed_targets | {
        ref.removeprefix("object:") for ref in allowed_targets if ref.startswith("object:")
    } | {
        f"object:{ref}" for ref in allowed_targets if not ref.startswith("object:")
    }
    wrong_entity_count = sum(
        item.target_ref is not None and item.target_ref not in normalized_allowed
        for item in state_items
    )
    evidence_items = [item for item in state_items if item.evidence_refs]
    evidence_refs = sorted({ref for item in evidence_items for ref in item.evidence_refs})
    resolved_evidence_ids = set()
    if evidence_refs:
        evidence_ids = [ref.removeprefix("evidence:") for ref in evidence_refs]
        resolved_evidence_ids = set(
            await session.scalars(
                select(EvidenceLinkModel.evidence_link_id).where(
                    EvidenceLinkModel.evidence_link_id.in_(evidence_ids)
                )
            )
        )
    invalid_evidence_assertions = sum(
        any(
            ref.removeprefix("evidence:") not in resolved_evidence_ids
            for ref in item.evidence_refs
        )
        for item in evidence_items
    )
    allowed_version_sources = set(gold.allowed_reasoning_relation_source_refs)
    allowed_version_claims = set(gold.allowed_reasoning_claim_source_refs)
    version_items = (
        [item for item in state_items if _is_version_scoped_assertion(item.proposition)]
        if gold.expected_fixed_version is not None
        else []
    )
    wrong_version_count = (
        sum(
            not _proposition_matches_expected_fixed_version(
                item.proposition,
                gold.expected_fixed_version,
            )
            for item in version_items
        )
        if gold.expected_fixed_version is not None
        else 0
    )
    reasoning_source_match_count = sum(
        item.reasoning_relation is not None
        and _version_reasoning_sources_match_gold(
            item.reasoning_relation.source_refs,
            allowed_relation_ids=allowed_version_sources,
            allowed_claim_ids=allowed_version_claims,
        )
        for item in version_items
        if item.reasoning_relation is not None
    )
    event_types = [
        *(f"case:{item.event_type}" for item in case_events),
        *(f"task:{item.event_type}" for item in task_events),
    ]
    final_role_run = role_runs[-1] if role_runs else None
    continuation_requested = any(
        item.opened_at > frozen_at for item in needs
    )
    observation = AgentRuntimeObservation(
        task_success=deadline_met,
        event_types=event_types,
        stop_reason=final_role_run.stop_reason if final_role_run is not None else None,
        timed_out=any(item.status == "timed_out" for item in role_runs),
        continuation_requested=continuation_requested,
        integrated_assertion_count=len(state_items),
        wrong_entity_attachment_count=wrong_entity_count,
        version_scoped_assertion_count=len(version_items),
        wrong_version_attachment_count=wrong_version_count,
        evidence_ref_assertion_count=len(evidence_items),
        invalid_evidence_ref_count=invalid_evidence_assertions,
    )
    score = score_agent_runtime(gold=gold, observation=observation)
    metric_values = {
        "agent.trajectory_conformance": score.trajectory_conformance,
        "agent.wrong_entity_attachment_rate": score.wrong_entity_attachment_rate,
        "agent.wrong_version_attachment_rate": score.wrong_version_attachment_rate,
        "agent.invalid_evidence_ref_rate": score.invalid_evidence_ref_rate,
        "agent.stop_correctness": score.stop_correctness,
        "agent.unnecessary_continuation_rate": score.unnecessary_continuation_rate,
    }
    observed: dict[str, float] = {}
    for metric_name, value in metric_values.items():
        if value is None:
            continue
        definition = metric_definition(metric_name)
        await store.observe_metric(
            session,
            case_run_id=case_run_id,
            metric_name=metric_name,
            value=value,
            direction=definition.direction,
            measurement_source=MeasurementSource.SCORER,
            subject_ref=f"case:{product_case_id}",
            evidence_refs=evidence_refs,
            metadata={
                "frozen_agent_runtime_gold": gold.model_dump(mode="json"),
                "event_types": cast(JsonValue, event_types),
                "investigation_role_run_ids": cast(
                    JsonValue, [item.run_id for item in role_runs]
                ),
                "state_item_count": len(state_items),
                "evidence_ref_assertion_count": len(evidence_items),
                "allowed_version_relation_ids": cast(
                    JsonValue, sorted(allowed_version_sources)
                ),
                "allowed_version_claim_ids": cast(
                    JsonValue, sorted(allowed_version_claims)
                ),
                "version_scoped_assertion_count": len(version_items),
                "reasoning_source_match_count": reasoning_source_match_count,
            },
        )
        observed[metric_name] = value
    return observed


if __name__ == "__main__":
    main()
