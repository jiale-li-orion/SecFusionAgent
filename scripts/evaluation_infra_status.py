from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark.metrics import CORE_METRICS
from packages.evaluation.benchmark.storage import (
    BenchmarkCaseRunModel,
    BenchmarkRunModel,
    MetricObservationModel,
)
from packages.evaluation.metric_contract import (
    EVALUATION_METRIC_GROUPS,
    validate_evaluation_metric_contract,
)
from packages.intelligence.storage.evidence_models import EvidenceArtifactModel, ObservationModel
from packages.intelligence.storage.knowledge_models import EvidenceLinkModel
from packages.investigation.storage.models import TrajectoryEventModel
from packages.reasoning.storage import DecisionResultModel
from packages.runtime.model.storage import (
    ModelAttemptModel,
    ModelRequestModel,
    PromptAssemblyRecordModel,
)
from packages.runtime.retrieval.storage import RetrievalInvocationModel
from packages.runtime.storage.models import CapabilityInvocationModel, ExecutionRunModel
from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
from packages.task_runtime.storage.models import TaskEventModel, TaskRunModel


async def _count(session, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


async def collect_status() -> dict[str, Any]:
    validate_evaluation_metric_contract()
    register_runtime_models()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            observed_rows = await session.execute(
                select(
                    MetricObservationModel.metric_name,
                    MetricObservationModel.metric_definition_revision,
                    func.count(MetricObservationModel.metric_observation_id),
                ).group_by(
                    MetricObservationModel.metric_name,
                    MetricObservationModel.metric_definition_revision,
                )
            )
            historical_counts: dict[str, int] = {}
            revision_counts: dict[tuple[str, str], int] = {}
            for name, revision, count in observed_rows.all():
                metric_name = str(name)
                metric_revision = str(revision)
                metric_count = int(count)
                historical_counts[metric_name] = (
                    historical_counts.get(metric_name, 0) + metric_count
                )
                revision_counts[(metric_name, metric_revision)] = metric_count
            observed_counts = {
                name: revision_counts.get((name, definition.revision), 0)
                for name, definition in CORE_METRICS.items()
            }

            group_status: list[dict[str, Any]] = []
            for group in EVALUATION_METRIC_GROUPS:
                observed = [name for name in group.metric_names if observed_counts.get(name, 0) > 0]
                missing = [name for name in group.metric_names if name not in observed]
                status = (
                    "observed" if not missing else ("partial" if observed else "contract_ready")
                )
                group_status.append(
                    {
                        "group_id": group.group_id,
                        "source": group.source,
                        "owner": group.owner,
                        "purpose": group.purpose,
                        "implementation": group.implementation,
                        "next_denominator": group.next_denominator,
                        "status": status,
                        "metric_count": len(group.metric_names),
                        "observed_metrics": observed,
                        "unobserved_metrics": missing,
                    }
                )

            trace_counts = {
                "benchmark_runs": await _count(session, BenchmarkRunModel),
                "benchmark_case_runs": await _count(session, BenchmarkCaseRunModel),
                "metric_observations": await _count(session, MetricObservationModel),
                "task_runs": await _count(session, TaskRunModel),
                "task_events": await _count(session, TaskEventModel),
                "execution_runs": await _count(session, ExecutionRunModel),
                "trajectory_events": await _count(session, TrajectoryEventModel),
                "capability_invocations": await _count(session, CapabilityInvocationModel),
                "retrieval_invocations": await _count(session, RetrievalInvocationModel),
                "model_requests": await _count(session, ModelRequestModel),
                "model_attempts": await _count(session, ModelAttemptModel),
                "prompt_assembly_records": await _count(session, PromptAssemblyRecordModel),
                "decision_results": await _count(session, DecisionResultModel),
                "evidence_links": await _count(session, EvidenceLinkModel),
                "observations": await _count(session, ObservationModel),
                "evidence_artifacts": await _count(session, EvidenceArtifactModel),
            }

            case_runs = list(await session.scalars(select(BenchmarkCaseRunModel)))
            case_with_artifacts = sum(bool(item.artifact_refs_json) for item in case_runs)
            case_with_task_ref = sum(
                item.task_run_id is not None
                or any(ref.startswith("task-run:") for ref in item.artifact_refs_json)
                for item in case_runs
            )
            case_with_execution_ref = sum(
                item.execution_id is not None
                or any(ref.startswith("execution:") for ref in item.artifact_refs_json)
                for item in case_runs
            )
            case_with_decision_ref = sum(
                item.decision_ref is not None
                or any(ref.startswith("decision:") for ref in item.artifact_refs_json)
                for item in case_runs
            )

            all_metrics = list(await session.scalars(select(MetricObservationModel)))
            metric_with_evidence = sum(bool(item.evidence_refs_json) for item in all_metrics)
            citation_metrics = [
                item
                for item in all_metrics
                if item.metric_name
                in {
                    "m6.groundedness",
                    "m6.citation_correctness",
                    "m6.citation_completeness",
                    "m6.multi_hop_correctness",
                }
            ]
            citation_metric_with_evidence = sum(
                bool(item.evidence_refs_json) for item in citation_metrics
            )

            model_request_total = trace_counts["model_requests"]
            model_request_artifacts = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ModelRequestModel)
                    .where(ModelRequestModel.request_artifact_ref.is_not(None))
                )
                or 0
            )
            model_attempt_total = trace_counts["model_attempts"]
            model_response_artifacts = int(
                await session.scalar(
                    select(func.count())
                    .select_from(ModelAttemptModel)
                    .where(ModelAttemptModel.response_artifact_ref.is_not(None))
                )
                or 0
            )
            assembly_total = trace_counts["prompt_assembly_records"]
            assembly_artifacts = int(
                await session.scalar(
                    select(func.count())
                    .select_from(PromptAssemblyRecordModel)
                    .where(PromptAssemblyRecordModel.request_artifact_ref.is_not(None))
                )
                or 0
            )

            latest_live_qa = await session.scalar(
                select(BenchmarkRunModel)
                .where(
                    BenchmarkRunModel.execution_mode == "live_external",
                    BenchmarkRunModel.status == "completed",
                    BenchmarkRunModel.suite_ref.like("m6-%"),
                )
                .order_by(BenchmarkRunModel.started_at.desc())
                .limit(1)
            )
            latest_live_qa_closure: dict[str, Any] | None = None
            if latest_live_qa is not None:
                latest_cases = list(
                    await session.scalars(
                        select(BenchmarkCaseRunModel).where(
                            BenchmarkCaseRunModel.benchmark_run_id
                            == latest_live_qa.benchmark_run_id
                        )
                    )
                )
                latest_case_ids = [item.case_run_id for item in latest_cases]
                latest_metrics = (
                    list(
                        await session.scalars(
                            select(MetricObservationModel).where(
                                MetricObservationModel.case_run_id.in_(latest_case_ids)
                            )
                        )
                    )
                    if latest_case_ids
                    else []
                )
                latest_citation_metrics = [
                    item
                    for item in latest_metrics
                    if item.metric_name
                    in {
                        "m6.groundedness",
                        "m6.citation_correctness",
                        "m6.citation_completeness",
                        "m6.multi_hop_correctness",
                    }
                ]
                latest_model_request_refs = {
                    ref
                    for case in latest_cases
                    for ref in case.artifact_refs_json
                    if isinstance(ref, str) and ref.startswith("model-request:")
                }
                latest_model_request_ids = [
                    ref.removeprefix("model-request:") for ref in latest_model_request_refs
                ]
                latest_model_requests = (
                    list(
                        await session.scalars(
                            select(ModelRequestModel).where(
                                ModelRequestModel.model_request_id.in_(latest_model_request_ids)
                            )
                        )
                    )
                    if latest_model_request_ids
                    else []
                )
                latest_model_attempts = (
                    list(
                        await session.scalars(
                            select(ModelAttemptModel).where(
                                ModelAttemptModel.model_request_id.in_(latest_model_request_ids)
                            )
                        )
                    )
                    if latest_model_request_ids
                    else []
                )
                latest_success_attempts = [
                    item for item in latest_model_attempts if item.status == "succeeded"
                ]
                latest_live_qa_closure = {
                    "benchmark_run_id": latest_live_qa.benchmark_run_id,
                    "suite_ref": latest_live_qa.suite_ref,
                    "case_runs": len(latest_cases),
                    "case_runs_with_artifact_refs": sum(
                        bool(item.artifact_refs_json) for item in latest_cases
                    ),
                    "citation_metric_observations": len(latest_citation_metrics),
                    "citation_metrics_with_evidence_refs": sum(
                        bool(item.evidence_refs_json) for item in latest_citation_metrics
                    ),
                    "citation_metric_evidence_rate": _ratio(
                        sum(bool(item.evidence_refs_json) for item in latest_citation_metrics),
                        len(latest_citation_metrics),
                    ),
                    "model_requests": len(latest_model_requests),
                    "model_requests_with_request_artifact": sum(
                        item.request_artifact_ref is not None for item in latest_model_requests
                    ),
                    "model_request_artifact_rate": _ratio(
                        sum(
                            item.request_artifact_ref is not None for item in latest_model_requests
                        ),
                        len(latest_model_requests),
                    ),
                    "successful_model_attempts": len(latest_success_attempts),
                    "successful_attempts_with_response_artifact": sum(
                        item.response_artifact_ref is not None for item in latest_success_attempts
                    ),
                    "model_response_artifact_rate": _ratio(
                        sum(
                            item.response_artifact_ref is not None
                            for item in latest_success_attempts
                        ),
                        len(latest_success_attempts),
                    ),
                    "runtime_metric_observations": sum(
                        item.metric_name.startswith("runtime.") for item in latest_metrics
                    ),
                }

            latest_live_investigation = await session.scalar(
                select(BenchmarkRunModel)
                .where(
                    BenchmarkRunModel.execution_mode == "live_controlled",
                    BenchmarkRunModel.status == "completed",
                    BenchmarkRunModel.suite_ref.like("m6-long-investigation-%"),
                )
                .order_by(BenchmarkRunModel.started_at.desc())
                .limit(1)
            )
            latest_live_investigation_closure: dict[str, Any] | None = None
            if latest_live_investigation is not None:
                investigation_cases = list(
                    await session.scalars(
                        select(BenchmarkCaseRunModel).where(
                            BenchmarkCaseRunModel.benchmark_run_id
                            == latest_live_investigation.benchmark_run_id
                        )
                    )
                )
                investigation_model_request_refs = {
                    ref
                    for case in investigation_cases
                    for ref in case.artifact_refs_json
                    if isinstance(ref, str) and ref.startswith("model-request:")
                }
                investigation_model_request_ids = [
                    ref.removeprefix("model-request:")
                    for ref in investigation_model_request_refs
                ]
                investigation_model_requests = (
                    list(
                        await session.scalars(
                            select(ModelRequestModel).where(
                                ModelRequestModel.model_request_id.in_(
                                    investigation_model_request_ids
                                )
                            )
                        )
                    )
                    if investigation_model_request_ids
                    else []
                )
                investigation_model_attempts = (
                    list(
                        await session.scalars(
                            select(ModelAttemptModel).where(
                                ModelAttemptModel.model_request_id.in_(
                                    investigation_model_request_ids
                                )
                            )
                        )
                    )
                    if investigation_model_request_ids
                    else []
                )
                investigation_success_attempts = [
                    item for item in investigation_model_attempts if item.status == "succeeded"
                ]
                m5_model_requests = [
                    item
                    for item in investigation_model_requests
                    if item.purpose == "m5.investigation_plan"
                ]
                m5_model_request_ids = {
                    item.model_request_id for item in m5_model_requests
                }
                m5_success_attempts = [
                    item
                    for item in investigation_success_attempts
                    if item.model_request_id in m5_model_request_ids
                ]
                m6_decision_requests = [
                    item
                    for item in investigation_model_requests
                    if item.purpose == "m6.decision"
                ]
                m6_decision_request_ids = {
                    item.model_request_id for item in m6_decision_requests
                }
                m6_decision_success_attempts = [
                    item
                    for item in investigation_success_attempts
                    if item.model_request_id in m6_decision_request_ids
                ]
                m6_decision_execution_owned = [
                    item for item in m6_decision_requests if item.execution_id is not None
                ]
                investigation_task_run_ids = list(
                    dict.fromkeys(
                        ref.removeprefix("task-run:")
                        for case in investigation_cases
                        for ref in case.artifact_refs_json
                        if isinstance(ref, str) and ref.startswith("task-run:")
                    )
                )
                investigation_assemblies = (
                    list(
                        await session.scalars(
                            select(PromptAssemblyRecordModel).where(
                                PromptAssemblyRecordModel.task_run_id.in_(
                                    investigation_task_run_ids
                                )
                            )
                        )
                    )
                    if investigation_task_run_ids
                    else []
                )
                investigation_decision_ids = [
                    case.decision_ref
                    for case in investigation_cases
                    if case.decision_ref is not None
                ]
                investigation_decisions = (
                    list(
                        await session.scalars(
                            select(DecisionResultModel).where(
                                DecisionResultModel.decision_id.in_(investigation_decision_ids)
                            )
                        )
                    )
                    if investigation_decision_ids
                    else []
                )
                decision_evidence_refs: set[str] = set()
                for decision in investigation_decisions:
                    raw_citations = decision.decision_json.get("citations")
                    if not isinstance(raw_citations, list):
                        continue
                    for citation in raw_citations:
                        if not isinstance(citation, dict):
                            continue
                        evidence_ref = citation.get("evidence_ref")
                        if isinstance(evidence_ref, str):
                            decision_evidence_refs.add(evidence_ref)
                decision_evidence_ids = [
                    ref.removeprefix("evidence:")
                    for ref in decision_evidence_refs
                    if ref.startswith("evidence:")
                ]
                decision_evidence_links = (
                    list(
                        await session.scalars(
                            select(EvidenceLinkModel).where(
                                EvidenceLinkModel.evidence_link_id.in_(decision_evidence_ids)
                            )
                        )
                    )
                    if decision_evidence_ids
                    else []
                )
                decision_observation_ids = [
                    item.observation_id for item in decision_evidence_links
                ]
                decision_artifact_ids = [
                    item.artifact_id
                    for item in decision_evidence_links
                    if item.artifact_id is not None
                ]
                resolved_observations = (
                    int(
                        await session.scalar(
                            select(func.count())
                            .select_from(ObservationModel)
                            .where(ObservationModel.observation_id.in_(decision_observation_ids))
                        )
                        or 0
                    )
                    if decision_observation_ids
                    else 0
                )
                resolved_artifacts = (
                    int(
                        await session.scalar(
                            select(func.count())
                            .select_from(EvidenceArtifactModel)
                            .where(EvidenceArtifactModel.artifact_id.in_(decision_artifact_ids))
                        )
                        or 0
                    )
                    if decision_artifact_ids
                    else 0
                )
                evidence_chain_resolved = sum(
                    item.artifact_id is not None for item in decision_evidence_links
                )
                if resolved_observations != len(decision_evidence_links):
                    evidence_chain_resolved = min(
                        evidence_chain_resolved,
                        resolved_observations,
                    )
                if resolved_artifacts != len(decision_artifact_ids):
                    evidence_chain_resolved = min(
                        evidence_chain_resolved,
                        resolved_artifacts,
                    )
                latest_live_investigation_closure = {
                    "benchmark_run_id": latest_live_investigation.benchmark_run_id,
                    "suite_ref": latest_live_investigation.suite_ref,
                    "case_runs": len(investigation_cases),
                    "model_requests": len(investigation_model_requests),
                    "m5_model_requests": len(m5_model_requests),
                    "m5_model_requests_with_request_artifact": sum(
                        item.request_artifact_ref is not None
                        for item in m5_model_requests
                    ),
                    "m5_model_request_artifact_rate": _ratio(
                        sum(
                            item.request_artifact_ref is not None
                            for item in m5_model_requests
                        ),
                        len(m5_model_requests),
                    ),
                    "m5_successful_model_attempts": len(m5_success_attempts),
                    "m5_successful_attempts_with_response_artifact": sum(
                        item.response_artifact_ref is not None
                        for item in m5_success_attempts
                    ),
                    "m5_model_response_artifact_rate": _ratio(
                        sum(
                            item.response_artifact_ref is not None
                            for item in m5_success_attempts
                        ),
                        len(m5_success_attempts),
                    ),
                    "m6_decision_model_requests": len(m6_decision_requests),
                    "m6_decision_execution_owned_requests": len(
                        m6_decision_execution_owned
                    ),
                    "m6_decision_execution_coordinate_rate": _ratio(
                        len(m6_decision_execution_owned),
                        len(m6_decision_requests),
                    ),
                    "m6_decision_request_artifact_rate": _ratio(
                        sum(
                            item.request_artifact_ref is not None
                            for item in m6_decision_execution_owned
                        ),
                        len(m6_decision_execution_owned),
                    ),
                    "m6_decision_response_artifact_rate": _ratio(
                        sum(
                            item.response_artifact_ref is not None
                            for item in m6_decision_success_attempts
                            if item.model_request_id
                            in {
                                request.model_request_id
                                for request in m6_decision_execution_owned
                            }
                        ),
                        sum(
                            item.model_request_id
                            in {
                                request.model_request_id
                                for request in m6_decision_execution_owned
                            }
                            for item in m6_decision_success_attempts
                        ),
                    ),
                    "prompt_assemblies": len(investigation_assemblies),
                    "prompt_assemblies_with_request_artifact": sum(
                        item.request_artifact_ref is not None
                        for item in investigation_assemblies
                    ),
                    "prompt_assembly_artifact_rate": _ratio(
                        sum(
                            item.request_artifact_ref is not None
                            for item in investigation_assemblies
                        ),
                        len(investigation_assemblies),
                    ),
                    "decision_evidence_refs": len(decision_evidence_refs),
                    "decision_evidence_chain_resolved": evidence_chain_resolved,
                    "decision_evidence_chain_rate": _ratio(
                        evidence_chain_resolved,
                        len(decision_evidence_refs),
                    ),
                }

            return {
                "schema_version": "evaluation-infra-status-v1",
                "generated_at": datetime.now(UTC).isoformat(),
                "registered_core_metric_count": len(CORE_METRICS),
                "contract_group_count": len(EVALUATION_METRIC_GROUPS),
                "observed_metric_name_count": sum(
                    count > 0 for count in observed_counts.values()
                ),
                "observed_metric_counts": dict(sorted(observed_counts.items())),
                "historical_observed_metric_name_count": len(historical_counts),
                "historical_observed_metric_counts": dict(sorted(historical_counts.items())),
                "metric_groups": group_status,
                "trace_substrate": trace_counts,
                "benchmark_case_trace_coverage": {
                    "case_runs": len(case_runs),
                    "with_artifact_refs": case_with_artifacts,
                    "with_artifact_refs_rate": _ratio(case_with_artifacts, len(case_runs)),
                    "with_task_ref": case_with_task_ref,
                    "with_task_ref_rate": _ratio(case_with_task_ref, len(case_runs)),
                    "with_execution_ref": case_with_execution_ref,
                    "with_execution_ref_rate": _ratio(case_with_execution_ref, len(case_runs)),
                    "with_decision_ref": case_with_decision_ref,
                    "with_decision_ref_rate": _ratio(case_with_decision_ref, len(case_runs)),
                },
                "metric_evidence_binding": {
                    "metric_observations": len(all_metrics),
                    "with_evidence_refs": metric_with_evidence,
                    "with_evidence_refs_rate": _ratio(metric_with_evidence, len(all_metrics)),
                    "citation_metric_observations": len(citation_metrics),
                    "citation_metrics_with_evidence_refs": citation_metric_with_evidence,
                    "citation_metrics_with_evidence_refs_rate": _ratio(
                        citation_metric_with_evidence,
                        len(citation_metrics),
                    ),
                },
                "replay_artifact_readiness": {
                    "model_requests": model_request_total,
                    "model_requests_with_request_artifact": model_request_artifacts,
                    "model_request_artifact_rate": _ratio(
                        model_request_artifacts, model_request_total
                    ),
                    "model_attempts": model_attempt_total,
                    "model_attempts_with_response_artifact": model_response_artifacts,
                    "model_response_artifact_rate": _ratio(
                        model_response_artifacts, model_attempt_total
                    ),
                    "prompt_assemblies": assembly_total,
                    "prompt_assemblies_with_request_artifact": assembly_artifacts,
                    "prompt_assembly_artifact_rate": _ratio(assembly_artifacts, assembly_total),
                },
                "latest_live_qa_closure": latest_live_qa_closure,
                "latest_live_investigation_closure": latest_live_investigation_closure,
                "interpretation": {
                    "observed": "all metrics in the contract group have durable observations",
                    "partial": "some metrics are observed; remaining denominators are still open",
                    "contract_ready": (
                        "metric definitions exist but no formal observations exist yet"
                    ),
                },
            }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect evaluation metric/trace infrastructure")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = asyncio.run(collect_status())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
