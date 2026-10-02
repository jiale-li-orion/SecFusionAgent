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
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.investigation.storage.models import InvestigationTrajectoryModel, TrajectoryEventModel
from packages.reasoning.storage import DecisionResultModel
from packages.runtime.model.storage import (
    ModelAttemptModel,
    ModelRequestModel,
    PromptAssemblyRecordModel,
)
from packages.runtime.retrieval.storage import RetrievalInvocationModel
from packages.runtime.storage.models import (
    CapabilityInvocationModel,
    ExecutionRunModel,
    RuntimeArtifactModel,
)
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskEventModel,
    TaskRunModel,
)


def _ref_ids(refs: list[str], prefix: str) -> list[str]:
    return list(dict.fromkeys(ref.removeprefix(prefix) for ref in refs if ref.startswith(prefix)))


def _decision_evidence_refs(payload: dict[str, object]) -> list[str]:
    result: list[str] = []
    conclusions = payload.get("conclusions")
    if not isinstance(conclusions, list):
        return result
    for conclusion in conclusions:
        if not isinstance(conclusion, dict):
            continue
        refs = conclusion.get("evidence_refs")
        if isinstance(refs, list):
            result.extend(ref for ref in refs if isinstance(ref, str))
    return list(dict.fromkeys(result))


async def _case_trace(session, case_run: BenchmarkCaseRunModel, metric_rows) -> dict[str, Any]:
    refs = list(case_run.artifact_refs_json)
    if case_run.task_run_id:
        refs.append(f"task-run:{case_run.task_run_id}")
    if case_run.execution_id:
        refs.append(case_run.execution_id)
    if case_run.decision_ref:
        refs.append(case_run.decision_ref)
    refs = list(dict.fromkeys(refs))

    task_run_ids = _ref_ids(refs, "task-run:")
    execution_ids = list(dict.fromkeys(ref for ref in refs if ref.startswith("execution:")))
    model_request_ids = _ref_ids(refs, "model-request:")
    retrieval_invocation_ids = _ref_ids(refs, "retrieval-invocation:")
    decision_ids = [ref for ref in refs if ref.startswith("decision:")]
    investigation_case_ids = _ref_ids(refs, "case:")

    task_runs = (
        list(
            await session.scalars(select(TaskRunModel).where(TaskRunModel.run_id.in_(task_run_ids)))
        )
        if task_run_ids
        else []
    )
    context_ids = [item.context_manifest_version_id for item in task_runs]
    contexts = (
        list(
            await session.scalars(
                select(ContextManifestVersionModel).where(
                    ContextManifestVersionModel.context_manifest_version_id.in_(context_ids)
                )
            )
        )
        if context_ids
        else []
    )
    task_events = (
        list(
            await session.scalars(
                select(TaskEventModel)
                .where(TaskEventModel.task_run_id.in_(task_run_ids))
                .order_by(TaskEventModel.task_run_id, TaskEventModel.seq)
            )
        )
        if task_run_ids
        else []
    )
    executions = (
        list(
            await session.scalars(
                select(ExecutionRunModel).where(ExecutionRunModel.execution_id.in_(execution_ids))
            )
        )
        if execution_ids
        else []
    )
    capabilities = (
        list(
            await session.scalars(
                select(CapabilityInvocationModel)
                .where(CapabilityInvocationModel.task_run_id.in_(task_run_ids))
                .order_by(CapabilityInvocationModel.started_at)
            )
        )
        if task_run_ids
        else []
    )
    model_requests = (
        list(
            await session.scalars(
                select(ModelRequestModel).where(
                    ModelRequestModel.model_request_id.in_(model_request_ids)
                )
            )
        )
        if model_request_ids
        else []
    )
    attempts = (
        list(
            await session.scalars(
                select(ModelAttemptModel)
                .where(ModelAttemptModel.model_request_id.in_(model_request_ids))
                .order_by(ModelAttemptModel.model_request_id, ModelAttemptModel.ordinal)
            )
        )
        if model_request_ids
        else []
    )
    prompt_assembly_ids = list(
        dict.fromkeys(item.prompt_assembly_id for item in model_requests if item.prompt_assembly_id)
    )
    prompt_assemblies = (
        list(
            await session.scalars(
                select(PromptAssemblyRecordModel).where(
                    PromptAssemblyRecordModel.assembly_id.in_(prompt_assembly_ids)
                )
            )
        )
        if prompt_assembly_ids
        else []
    )
    runtime_artifact_refs = list(
        dict.fromkeys(
            ref
            for ref in [
                *(item.request_artifact_ref for item in model_requests),
                *(item.response_artifact_ref for item in attempts),
                *(item.request_artifact_ref for item in prompt_assemblies),
            ]
            if isinstance(ref, str) and ref.startswith("artifact:")
        )
    )
    runtime_artifact_ids = _ref_ids(runtime_artifact_refs, "artifact:")
    runtime_artifacts = (
        list(
            await session.scalars(
                select(RuntimeArtifactModel).where(
                    RuntimeArtifactModel.artifact_id.in_(runtime_artifact_ids)
                )
            )
        )
        if runtime_artifact_ids
        else []
    )
    retrievals = (
        list(
            await session.scalars(
                select(RetrievalInvocationModel).where(
                    RetrievalInvocationModel.invocation_id.in_(retrieval_invocation_ids)
                )
            )
        )
        if retrieval_invocation_ids
        else []
    )
    decisions = (
        list(
            await session.scalars(
                select(DecisionResultModel).where(DecisionResultModel.decision_id.in_(decision_ids))
            )
        )
        if decision_ids
        else []
    )

    if not investigation_case_ids:
        investigation_case_ids = list(
            dict.fromkeys(item.case_id for item in task_runs if item.case_id)
        )
    trajectories = (
        list(
            await session.scalars(
                select(InvestigationTrajectoryModel).where(
                    InvestigationTrajectoryModel.case_id.in_(investigation_case_ids)
                )
            )
        )
        if investigation_case_ids
        else []
    )
    trajectory_ids = [item.trajectory_id for item in trajectories]
    trajectory_events = (
        list(
            await session.scalars(
                select(TrajectoryEventModel)
                .where(TrajectoryEventModel.trajectory_id.in_(trajectory_ids))
                .order_by(TrajectoryEventModel.trajectory_id, TrajectoryEventModel.ordinal)
            )
        )
        if trajectory_ids
        else []
    )

    evidence_refs = [
        ref for item in metric_rows for ref in item.evidence_refs_json if isinstance(ref, str)
    ]
    for decision in decisions:
        evidence_refs.extend(_decision_evidence_refs(decision.decision_json))
    for context in contexts:
        raw = context.manifest_json.get("evidence_refs")
        if isinstance(raw, list):
            evidence_refs.extend(ref for ref in raw if isinstance(ref, str))
    evidence_refs = list(dict.fromkeys(evidence_refs))
    evidence_link_ids = _ref_ids(evidence_refs, "evidence:")
    evidence_links = (
        list(
            await session.scalars(
                select(EvidenceLinkModel).where(
                    EvidenceLinkModel.evidence_link_id.in_(evidence_link_ids)
                )
            )
        )
        if evidence_link_ids
        else []
    )
    observation_ids = list(dict.fromkeys(item.observation_id for item in evidence_links))
    artifact_ids = list(
        dict.fromkeys(item.artifact_id for item in evidence_links if item.artifact_id)
    )
    observations = (
        list(
            await session.scalars(
                select(ObservationModel).where(ObservationModel.observation_id.in_(observation_ids))
            )
        )
        if observation_ids
        else []
    )
    artifacts = (
        list(
            await session.scalars(
                select(EvidenceArtifactModel).where(
                    EvidenceArtifactModel.artifact_id.in_(artifact_ids)
                )
            )
        )
        if artifact_ids
        else []
    )
    observation_map = {item.observation_id: item for item in observations}
    artifact_map = {item.artifact_id: item for item in artifacts}
    runtime_artifact_map = {f"artifact:{item.artifact_id}": item for item in runtime_artifacts}

    closure_issues: list[str] = []
    if model_requests:
        attempts_by_request = {
            request.model_request_id: [
                item for item in attempts if item.model_request_id == request.model_request_id
            ]
            for request in model_requests
        }
        for request in model_requests:
            if not attempts_by_request[request.model_request_id]:
                closure_issues.append(
                    f"model request has no persisted attempt: {request.model_request_id}"
                )
            if request.execution_id is None:
                closure_issues.append(
                    f"model request has no ExecutionRun owner: {request.model_request_id}"
                )
            elif request.request_artifact_ref is None:
                closure_issues.append(
                    f"model request has no request artifact: {request.model_request_id}"
                )
            elif request.request_artifact_ref not in runtime_artifact_map:
                closure_issues.append(
                    "model request artifact does not resolve: " + request.request_artifact_ref
                )
            if request.execution_id is not None and not any(
                item.execution_id == request.execution_id for item in executions
            ):
                closure_issues.append(
                    f"model request ExecutionRun does not resolve: {request.execution_id}"
                )
        for attempt in attempts:
            if attempt.status == "succeeded":
                request = next(
                    (
                        item
                        for item in model_requests
                        if item.model_request_id == attempt.model_request_id
                    ),
                    None,
                )
                if attempt.response_artifact_ref is None:
                    closure_issues.append(
                        "successful model attempt has no response artifact: "
                        f"{attempt.model_attempt_id}"
                    )
                elif attempt.response_artifact_ref not in runtime_artifact_map:
                    closure_issues.append(
                        "model response artifact does not resolve: " + attempt.response_artifact_ref
                    )
    if task_runs and len(contexts) != len({item.context_manifest_version_id for item in task_runs}):
        closure_issues.append("one or more TaskRun ContextManifest refs do not resolve")
    expected_retrieval_refs = {
        ref
        for context in contexts
        for ref in context.manifest_json.get("retrieval_invocation_refs", [])
        if isinstance(ref, str) and ref.startswith("retrieval-invocation:")
    }
    resolved_retrieval_refs = {f"retrieval-invocation:{item.invocation_id}" for item in retrievals}
    missing_retrieval_refs = sorted(expected_retrieval_refs - resolved_retrieval_refs)
    if missing_retrieval_refs:
        closure_issues.append(
            "retrieval invocation refs do not resolve: " + ", ".join(missing_retrieval_refs)
        )
    for link in evidence_links:
        if link.observation_id not in observation_map:
            closure_issues.append(
                f"EvidenceLink has no Observation: evidence:{link.evidence_link_id}"
            )
        if link.artifact_id is None or link.artifact_id not in artifact_map:
            closure_issues.append(
                f"EvidenceLink has no physical EvidenceArtifact: evidence:{link.evidence_link_id}"
            )
    decision_has_evidence = any(_decision_evidence_refs(item.decision_json) for item in decisions)
    citation_metric_names = {
        "m6.groundedness",
        "m6.citation_correctness",
        "m6.citation_completeness",
        "m6.multi_hop_correctness",
    }
    if decision_has_evidence:
        for metric in metric_rows:
            if metric.metric_name in citation_metric_names and not metric.evidence_refs_json:
                closure_issues.append(
                    f"citation metric is not bound to EvidenceRefs: {metric.metric_name}"
                )

    return {
        "closure": {
            "closed": not closure_issues,
            "issues": closure_issues,
        },
        "artifact_refs": refs,
        "task_runs": [
            {
                "run_id": item.run_id,
                "role_id": item.role_id,
                "status": item.status,
                "case_id": item.case_id,
                "context_id": item.context_id,
                "context_revision": item.context_revision,
                "result_ref": item.result_ref,
                "stop_reason": item.stop_reason,
                "created_at": item.created_at.isoformat(),
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            }
            for item in task_runs
        ],
        "contexts": [
            {
                "context_manifest_version_id": item.context_manifest_version_id,
                "context_id": item.context_id,
                "context_revision": item.context_revision,
                "parent_context_id": item.parent_context_id,
                "knowledge_revision": item.knowledge_revision,
                "case_ref": item.case_ref,
                "evidence_refs": item.manifest_json.get("evidence_refs", []),
                "relation_refs": item.manifest_json.get("relation_refs", []),
                "retrieval_refs": item.manifest_json.get("retrieval_refs", []),
                "retrieval_invocation_refs": item.manifest_json.get(
                    "retrieval_invocation_refs", []
                ),
                "content_hash": item.content_hash,
            }
            for item in contexts
        ],
        "task_events": [
            {
                "event_id": item.event_id,
                "task_run_id": item.task_run_id,
                "seq": item.seq,
                "event_type": item.event_type,
                "producer": item.producer,
                "base_context_revision": item.base_context_revision,
                "payload_ref": item.payload_ref,
                "emitted_at": item.emitted_at.isoformat(),
            }
            for item in task_events
        ],
        "executions": [
            {
                "execution_id": item.execution_id,
                "task_run_id": item.task_run_id,
                "parent_execution_id": item.parent_execution_id,
                "status": item.status,
                "stop_reason": item.stop_reason,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            }
            for item in executions
        ],
        "model_requests": [
            {
                "model_request_id": item.model_request_id,
                "purpose": item.purpose,
                "request_owner_ref": item.request_owner_ref,
                "task_run_id": item.task_run_id,
                "execution_id": item.execution_id,
                "prompt_revision": item.prompt_revision,
                "requested_model": item.requested_model,
                "request_digest": item.request_digest,
                "prompt_assembly_id": item.prompt_assembly_id,
                "request_artifact_ref": item.request_artifact_ref,
                "created_at": item.created_at.isoformat(),
            }
            for item in model_requests
        ],
        "model_attempts": [
            {
                "model_attempt_id": item.model_attempt_id,
                "model_request_id": item.model_request_id,
                "ordinal": item.ordinal,
                "provider": item.provider,
                "actual_model": item.actual_model,
                "status": item.status,
                "failure_class": item.failure_class,
                "latency_ms": item.latency_ms,
                "usage": item.usage_json,
                "cost": item.cost_json,
                "cache_usage": item.cache_usage_json,
                "response_metadata": item.response_metadata_json,
                "response_artifact_ref": item.response_artifact_ref,
            }
            for item in attempts
        ],
        "prompt_assemblies": [
            {
                "assembly_id": item.assembly_id,
                "assembly_hash": item.assembly_hash,
                "execution_id": item.execution_id,
                "task_run_id": item.task_run_id,
                "context_manifest_ref": item.context_manifest_ref,
                "context_manifest_revision": item.context_manifest_revision,
                "role_revision": item.role_revision,
                "ordered_fragment_ids": item.ordered_fragment_ids_json,
                "materialized_ref_set_digest": item.materialized_ref_set_digest,
                "request_artifact_ref": item.request_artifact_ref,
                "created_at": item.created_at.isoformat(),
            }
            for item in prompt_assemblies
        ],
        "runtime_artifacts": [
            {
                "artifact_ref": f"artifact:{item.artifact_id}",
                "execution_id": item.execution_id,
                "producer_kind": item.producer_kind,
                "producer_ref": item.producer_ref,
                "logical_name": item.logical_name,
                "media_type": item.media_type,
                "content_hash": item.content_hash,
                "storage_uri": item.storage_uri,
                "size_bytes": item.size_bytes,
                "trust_class": item.trust_class,
                "created_at": item.created_at.isoformat(),
            }
            for item in runtime_artifacts
        ],
        "capability_invocations": [
            {
                "invocation_id": item.invocation_id,
                "task_run_id": item.task_run_id,
                "capability_id": item.capability_id,
                "binding_id": item.binding_id,
                "tool_impl_id": item.tool_impl_id,
                "arguments_digest": item.arguments_digest,
                "status": item.status,
                "failure_code": item.failure_code,
                "policy_decision_ref": item.policy_decision_ref,
                "started_at": item.started_at.isoformat(),
                "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            }
            for item in capabilities
        ],
        "retrieval_invocations": [
            {
                "invocation_id": item.invocation_id,
                "request_owner_ref": item.request_owner_ref,
                "operator": item.operator,
                "operator_revision": item.operator_revision,
                "knowledge_revision": item.knowledge_revision,
                "result_count": item.result_count,
                "result_refs": item.result_refs,
                "disposition": item.disposition,
                "reuse_of_invocation_id": item.reuse_of_invocation_id,
                "started_at": item.started_at.isoformat(),
                "finished_at": item.finished_at.isoformat(),
            }
            for item in retrievals
        ],
        "decisions": [
            {
                "decision_id": item.decision_id,
                "case_id": item.case_id,
                "case_revision": item.case_revision,
                "content_hash": item.content_hash,
                "decision": item.decision_json,
                "created_at": item.created_at.isoformat(),
            }
            for item in decisions
        ],
        "trajectories": [
            {
                "trajectory_id": item.trajectory_id,
                "case_id": item.case_id,
                "status": item.status,
                "outcome": item.outcome,
                "latency_ms": item.latency_ms,
                "tool_calls": item.tool_calls,
                "cost": item.cost,
            }
            for item in trajectories
        ],
        "trajectory_events": [
            {
                "event_id": item.event_id,
                "trajectory_id": item.trajectory_id,
                "ordinal": item.ordinal,
                "event_type": item.event_type,
                "evidence_refs": item.evidence_refs,
                "artifact_uri": item.artifact_uri,
                "occurred_at": item.occurred_at.isoformat(),
            }
            for item in trajectory_events
        ],
        "evidence_chain": [
            {
                "evidence_ref": f"evidence:{link.evidence_link_id}",
                "target_kind": link.target_kind,
                "target_id": link.target_id,
                "locator": link.locator,
                "observation": (
                    {
                        "observation_id": observation_map[link.observation_id].observation_id,
                        "source_id": observation_map[link.observation_id].source_id,
                        "external_object_id": observation_map[
                            link.observation_id
                        ].external_object_id,
                        "external_revision": observation_map[link.observation_id].external_revision,
                        "observed_at": observation_map[link.observation_id].observed_at.isoformat(),
                        "content_hash": observation_map[link.observation_id].content_hash,
                    }
                    if link.observation_id in observation_map
                    else None
                ),
                "artifact": (
                    {
                        "artifact_id": artifact_map[link.artifact_id].artifact_id,
                        "storage_uri": artifact_map[link.artifact_id].storage_uri,
                        "content_hash": artifact_map[link.artifact_id].content_hash,
                        "media_type": artifact_map[link.artifact_id].media_type,
                        "trust_class": artifact_map[link.artifact_id].trust_class,
                    }
                    if link.artifact_id in artifact_map
                    else None
                ),
            }
            for link in evidence_links
        ],
    }


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
                    f"CompetitionReport references missing BenchmarkRun rows: {missing}"
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
            observations_by_case: dict[str, list[MetricObservationModel]] = {}
            for observation in observations:
                observations_by_case.setdefault(observation.case_run_id, []).append(observation)
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
                "case_runs": [
                    {
                        "case_run_id": item.case_run_id,
                        "benchmark_run_id": item.benchmark_run_id,
                        "case_ref": item.case_ref,
                        "task_run_id": item.task_run_id,
                        "execution_id": item.execution_id,
                        "decision_ref": item.decision_ref,
                        "status": item.status,
                        "failure_class": item.failure_class,
                        "started_at": item.started_at.isoformat(),
                        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                        "trace": await _case_trace(
                            session,
                            item,
                            observations_by_case.get(item.case_run_id, []),
                        ),
                    }
                    for item in case_runs
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


async def query_run_evidence(
    run_ids: list[str],
    *,
    metric_name: str | None = None,
    case_run_id: str | None = None,
) -> dict[str, Any]:
    if not run_ids:
        raise ValueError("run evidence query requires at least one BenchmarkRun id")
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
            observed_run_ids = {item.benchmark_run_id for item in runs}
            missing = sorted(set(run_ids) - observed_run_ids)
            if missing:
                raise LookupError(f"benchmark runs not found: {missing}")

            case_query = select(BenchmarkCaseRunModel).where(
                BenchmarkCaseRunModel.benchmark_run_id.in_(run_ids)
            )
            if case_run_id is not None:
                case_query = case_query.where(BenchmarkCaseRunModel.case_run_id == case_run_id)
            case_runs = list(await session.scalars(case_query))
            if case_run_id is not None and not case_runs:
                raise LookupError(f"case run not found in selected runs: {case_run_id}")
            case_run_ids = [item.case_run_id for item in case_runs]
            observations: list[MetricObservationModel] = []
            if case_run_ids:
                metric_query = select(MetricObservationModel).where(
                    MetricObservationModel.case_run_id.in_(case_run_ids)
                )
                if metric_name is not None:
                    metric_query = metric_query.where(
                        MetricObservationModel.metric_name == metric_name
                    )
                observations = list(
                    await session.scalars(
                        metric_query.order_by(
                            MetricObservationModel.metric_name,
                            MetricObservationModel.created_at,
                        )
                    )
                )
            observations_by_case: dict[str, list[MetricObservationModel]] = {}
            for observation in observations:
                observations_by_case.setdefault(observation.case_run_id, []).append(observation)
            traced_cases = []
            for item in case_runs:
                traced_cases.append(
                    {
                        "case_run_id": item.case_run_id,
                        "benchmark_run_id": item.benchmark_run_id,
                        "case_ref": item.case_ref,
                        "task_run_id": item.task_run_id,
                        "execution_id": item.execution_id,
                        "decision_ref": item.decision_ref,
                        "status": item.status,
                        "failure_class": item.failure_class,
                        "started_at": item.started_at.isoformat(),
                        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                        "trace": await _case_trace(
                            session,
                            item,
                            observations_by_case.get(item.case_run_id, []),
                        ),
                    }
                )
            return {
                "run_ids": run_ids,
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
                "case_runs": traced_cases,
                "metric_observations": [
                    {
                        "metric_observation_id": item.metric_observation_id,
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
        description="Query durable benchmark metrics, execution trace and Evidence chain"
    )
    parser.add_argument(
        "--report",
        type=Path,
    )
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--case-run-id")
    parser.add_argument("--metric")
    parser.add_argument("--require-closed", action="store_true")
    args = parser.parse_args()
    if args.report is not None and args.run_id:
        parser.error("--report and --run-id are mutually exclusive")
    if args.case_run_id is not None and not args.run_id:
        parser.error("--case-run-id requires --run-id")
    if args.run_id:
        result = asyncio.run(
            query_run_evidence(
                args.run_id,
                metric_name=args.metric,
                case_run_id=args.case_run_id,
            )
        )
    else:
        report = args.report or Path("benchmarks/competition/current.json")
        result = asyncio.run(query_report_evidence(report, metric_name=args.metric))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.require_closed:
        failures = [
            {
                "case_run_id": item["case_run_id"],
                "issues": item["trace"]["closure"]["issues"],
            }
            for item in result.get("case_runs", [])
            if not item["trace"]["closure"]["closed"]
        ]
        if failures:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
