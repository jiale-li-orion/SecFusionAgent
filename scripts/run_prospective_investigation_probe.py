from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select

from apps.application.commands.start_investigation import (
    StartInvestigationCommand,
    StartInvestigationUseCase,
)
from apps.decision_runtime import (
    DecisionRuntime,
    finish_case_decision_execution,
    open_case_decision_execution,
)
from apps.evaluation_runtime import _load_citation_sources
from apps.model_runtime import create_recorded_model_provider
from apps.runtime_artifacts import create_runtime_artifact_service
from apps.runtime_models import register_runtime_models
from apps.worker.tasks import _run_investigation
from packages.evaluation.agent_runtime import AgentRuntimeGold
from packages.intelligence.storage.knowledge_models import ClaimModel, ObjectModel, RelationModel
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.model import ModelDecisionPlanner
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.contracts.models import TaskKind, TaskRunStatus
from packages.task_runtime.storage.models import TaskRunModel
from scripts.query_benchmark_evidence import query_run_evidence
from scripts.run_investigation_benchmark import (
    InvestigationBenchmarkManifest,
    InvestigationBenchmarkManifestCase,
)
from scripts.run_investigation_benchmark import (
    _run as run_investigation_benchmark,
)


def _relation_supports_expected_fixed_version(
    *,
    relation_type: str,
    target_canonical_key: str,
    qualifier: dict[str, object],
    expected_fixed_version: str,
) -> bool:
    if (
        relation_type == "fixed-version"
        and target_canonical_key.rsplit(":", 1)[-1] == expected_fixed_version
    ):
        return True
    if qualifier.get("first_patched_version") == expected_fixed_version:
        return True
    for key in ("version_range", "vulnerable_version_range"):
        value = qualifier.get(key)
        if not isinstance(value, str):
            continue
        upper_bounds = re.findall(r"(?<!<)<\s*([^,\s]+)", value)
        if expected_fixed_version in upper_bounds:
            return True
    return False


def _claim_supports_expected_fixed_version(
    *,
    predicate: str,
    value: object,
    expected_fixed_version: str,
) -> bool:
    serialized = json.dumps(value, ensure_ascii=False).strip('"')
    escaped = re.escape(expected_fixed_version)
    if re.search(
        rf"\b(?:fixed|patched)\s+(?:in|at|to)\s+{escaped}\b",
        serialized,
        flags=re.IGNORECASE,
    ):
        return True
    normalized_predicate = predicate.lower().replace("-", "_")
    return (
        any(token in normalized_predicate for token in ("fixed", "patched"))
        and serialized == expected_fixed_version
    )


async def _run(args: argparse.Namespace) -> dict[str, object]:
    register_runtime_models()
    settings = get_settings()
    if not settings.model_base_url or not settings.model_name:
        raise RuntimeError("prospective investigation probe requires configured model provider")

    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        use_case = StartInvestigationUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
        )
        async with factory() as session:
            started = await use_case.execute(
                session,
                StartInvestigationCommand(
                    principal="system:benchmark-prospective",
                    request_id=f"prospective:{uuid4()}",
                    cve_id=args.cve_id,
                    goal=args.goal,
                    evidence_question=args.evidence_question,
                    purpose="prospective_benchmark_probe",
                    task_kind=TaskKind.VERIFY_VERSION_FIX,
                    timeout_seconds=args.deadline_seconds,
                    agent_turns=args.agent_turns,
                    tool_calls=args.tool_calls,
                ),
            )
            case_id = started.investigation.case_id
            run = await session.scalar(
                select(TaskRunModel)
                .where(
                    TaskRunModel.case_id == case_id,
                    TaskRunModel.role_id == "InvestigationRole",
                )
                .order_by(TaskRunModel.created_at.desc())
                .limit(1)
            )
            if run is None:
                raise RuntimeError("StartInvestigation did not create InvestigationRole TaskRun")
            investigation_run_id = run.run_id
            initial_state = await InvestigationStateService().get_state(session, case_id)
            allowed_version_sources: list[str] = []
            allowed_version_claims: list[str] = []
            if args.expected_fixed_version is not None:
                relation_rows = list(
                    await session.execute(
                        select(
                            RelationModel.relation_id,
                            RelationModel.relation_type,
                            RelationModel.qualifier,
                            ObjectModel.canonical_key,
                        )
                        .join(
                            ObjectModel,
                            ObjectModel.object_id == RelationModel.target_object_id,
                        )
                        .where(
                            RelationModel.source_object_id.in_(initial_state.targets),
                            RelationModel.superseded_revision.is_(None),
                        )
                    )
                )
                allowed_version_sources = sorted(
                    relation_id
                    for relation_id, relation_type, qualifier, target_key in relation_rows
                    if _relation_supports_expected_fixed_version(
                        relation_type=relation_type,
                        target_canonical_key=target_key,
                        qualifier=qualifier,
                        expected_fixed_version=args.expected_fixed_version,
                    )
                )
                if not allowed_version_sources:
                    raise RuntimeError(
                        "expected fixed version is not present in the frozen Knowledge world: "
                        f"{args.expected_fixed_version}"
                    )
                claim_rows = list(
                    await session.execute(
                        select(
                            ClaimModel.claim_id,
                            ClaimModel.predicate,
                            ClaimModel.value,
                        ).where(
                            ClaimModel.subject_id.in_(initial_state.targets),
                            ClaimModel.lifecycle == "accepted",
                            ClaimModel.superseded_revision.is_(None),
                        )
                    )
                )
                allowed_version_claims = sorted(
                    claim_id
                    for claim_id, predicate, value in claim_rows
                    if _claim_supports_expected_fixed_version(
                        predicate=predicate,
                        value=value,
                        expected_fixed_version=args.expected_fixed_version,
                    )
                )

            agent_runtime_gold = AgentRuntimeGold(
                expected_task_success=True,
                allowed_target_refs=list(initial_state.targets),
                expected_fixed_version=args.expected_fixed_version,
                allowed_reasoning_relation_source_refs=allowed_version_sources,
                allowed_reasoning_claim_source_refs=allowed_version_claims,
                required_event_types=[
                    "case:fact_confirmed",
                    "case:evidence_need_resolved",
                    "task:InvestigationStateChanged",
                    "task:TaskCompleted",
                ],
                forbidden_event_types=["task:TaskFailed"],
                acceptable_stop_reasons=["evidence_sufficient"],
                expected_continuation=False,
            )

        frozen_at = datetime.now(UTC)
        manifest = InvestigationBenchmarkManifest(
            suite_id=args.suite_id,
            purpose=(
                "Prospective end-to-end validation of current Long Investigation evaluation and "
                "provenance infrastructure"
            ),
            evaluator_revision=args.evaluator_revision,
            frozen_at=frozen_at,
            cases=[
                InvestigationBenchmarkManifestCase(
                    case_id=f"long-investigation-probe-{case_id[:8]}",
                    product_case_id=case_id,
                    expected_final_decision=True,
                    measurement_deadline=frozen_at
                    + timedelta(seconds=args.deadline_seconds),
                    tags=[
                        "infra-prospective-probe",
                        "current-runner-closure",
                        "real-product",
                        "not-competition-score",
                    ],
                    latency_class="long_investigation_prospective_probe",
                    agent_runtime_gold=agent_runtime_gold,
                )
            ],
        )
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        preflight = await run_investigation_benchmark(
            manifest,
            suite_revision=args.suite_revision,
            deployment_revision_id=None,
            evaluator_revision=args.evaluator_revision,
            preflight_only=True,
            measured_at=frozen_at,
        )
        statuses = preflight["statuses"]
        if not statuses or statuses[0]["status"] != "pending":
            raise RuntimeError("prospective case was not frozen before outcome")

        investigation_status = await _run_investigation(investigation_run_id)
        if investigation_status != TaskRunStatus.COMPLETED.value:
            raise RuntimeError(
                f"InvestigationRole did not complete successfully: {investigation_status}"
            )

        state_service = InvestigationStateService()
        async with factory() as session:
            state = await state_service.get_state(session, case_id)
            citation_sources = await _load_citation_sources(session, state)
            await session.rollback()
        if state.current_decision is not None:
            raise RuntimeError("prospective Case already has decision before DecisionRole probe")

        decision_request_id = f"prospective-decision:{uuid4()}"
        async with factory() as session, session.begin():
            coordinate = await open_case_decision_execution(
                session,
                settings=settings,
                state=state,
                principal="system:benchmark-prospective",
                request_id=decision_request_id,
                surface="prospective-decision",
                timeout_seconds=settings.model_timeout_seconds,
            )

        artifacts = await create_runtime_artifact_service(settings)
        async with httpx.AsyncClient(timeout=settings.model_timeout_seconds) as client:
            provider = create_recorded_model_provider(
                settings,
                factory,
                client,
                artifact_service=artifacts,
            )
            if provider is None:
                raise RuntimeError("model provider is unavailable")
            try:
                proposal = await ModelDecisionPlanner(provider).plan(
                    state,
                    citation_sources=citation_sources,
                    runtime_metadata={
                        "request_owner_ref": f"task-run:{coordinate.task_run_id}",
                        "task_run_id": coordinate.task_run_id,
                        "execution_id": coordinate.execution_id,
                        "budget_ref": coordinate.budget_ref,
                        "case_id": case_id,
                        "model_wall_seconds": settings.model_timeout_seconds,
                        "model_payload_persistence": "redacted_runtime_artifact",
                    },
                )
            except Exception:
                async with factory() as session, session.begin():
                    await finish_case_decision_execution(
                        session,
                        settings=settings,
                        coordinate=coordinate,
                        result_ref=f"task-run:{coordinate.task_run_id}",
                        stop_reason="decision_reasoning_failed",
                        status=TaskRunStatus.FAILED,
                        surface="prospective-decision",
                    )
                raise

        async with factory() as session, session.begin():
            outcome = await DecisionRuntime(state_service=state_service).commit_proposal(
                session,
                state=state,
                proposal=proposal,
                citation_sources=citation_sources,
            )
            if outcome.decision is not None:
                result_ref = outcome.decision.decision_id
                stop_reason = outcome.decision.stop_reason
            else:
                assert outcome.continuation is not None
                result_ref = f"evidence-need:{outcome.continuation.need.need_id}"
                stop_reason = "continuation_requested"
            await finish_case_decision_execution(
                session,
                settings=settings,
                coordinate=coordinate,
                result_ref=result_ref,
                stop_reason=stop_reason,
                surface="prospective-decision",
            )

        benchmark = await run_investigation_benchmark(
            manifest,
            suite_revision=args.suite_revision,
            deployment_revision_id=None,
            evaluator_revision=args.evaluator_revision,
        )
        audit = await query_run_evidence([str(benchmark["benchmark_run_id"])])
        open_cases = [
            item
            for item in audit["case_runs"]
            if not item["trace"]["closure"]["closed"]
        ]
        if open_cases:
            raise RuntimeError(
                "prospective benchmark provenance is not closed: "
                + json.dumps(
                    [
                        {
                            "case_run_id": item["case_run_id"],
                            "issues": item["trace"]["closure"]["issues"],
                        }
                        for item in open_cases
                    ],
                    ensure_ascii=False,
                )
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(benchmark, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return {
            "case_id": case_id,
            "investigation_task_run_id": investigation_run_id,
            "decision_task_run_id": coordinate.task_run_id,
            "decision_execution_id": coordinate.execution_id,
            "manifest": str(args.manifest_output),
            "benchmark": benchmark,
            "provenance_closed": True,
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create, prospectively freeze and synchronously execute one real Long Investigation "
            "through the production M5/M6 owners, then persist and audit its benchmark trace."
        )
    )
    parser.add_argument("--cve-id", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--evidence-question", required=True)
    parser.add_argument("--expected-fixed-version")
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--suite-revision", type=int, default=1)
    parser.add_argument("--evaluator-revision", default="investigation-completion-v4")
    parser.add_argument("--deadline-seconds", type=int, default=300)
    parser.add_argument("--agent-turns", type=int, default=8)
    parser.add_argument("--tool-calls", type=int, default=12)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
