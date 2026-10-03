from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import cast

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.question_facts import render_claim_fact, render_relation_fact
from apps.application.question_sessions import QuestionSessionTurnModel
from apps.decision_runtime import DecisionRuntime
from packages.evaluation.benchmark import (
    BenchmarkStore,
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
)
from packages.evaluation.benchmark.metrics import metric_definition
from packages.evaluation.benchmark.storage import DeploymentRevisionModel
from packages.evaluation.m1_m3 import EnrichmentScore
from packages.evaluation.qa import QACitationCheck, QAGold, QAPrediction, QAScore
from packages.intelligence.knowledge.vocabulary import VOCABULARY_REVISION
from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ObjectModel,
    RelationModel,
)
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.state.contracts import (
    CaseStateEventType,
    EvidenceNeedStatus,
    InvestigationState,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import (
    CaseStateEventModel,
    EvidenceNeedModel,
    InvestigationCaseModel,
)
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import ConclusionType, DecisionConclusion, DecisionResult
from packages.reasoning.model import ModelDecisionPlanner
from packages.reasoning.storage import DecisionResultStore
from packages.runtime.model.storage import ModelAttemptModel, ModelRequestModel
from packages.runtime.policy.loader import load_runtime_policy
from packages.runtime.retrieval.storage import RetrievalInvocationModel
from packages.runtime.storage.models import CapabilityInvocationModel, ExecutionRunModel
from packages.shared.config import Settings
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.contracts.models import TaskKind, TaskRunStatus
from packages.task_runtime.storage.models import ContextManifestVersionModel, TaskRunModel


class M3BenchmarkRecorder:
    """Project existing M3 scorer output into TD3 durable metric observations."""

    def __init__(self, store: BenchmarkStore | None = None) -> None:
        self._store = store or BenchmarkStore()

    async def record_case_score(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        score: EnrichmentScore,
        subject_ref: str,
    ) -> None:
        for metric_name, value, direction in (
            ("m3.micro_precision", score.micro_precision, MetricDirection.HIGHER_IS_BETTER),
            ("m3.micro_recall", score.micro_recall, MetricDirection.HIGHER_IS_BETTER),
            (
                "m3.dimension_macro_precision",
                score.dimension_macro_precision,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            (
                "m3.dimension_macro_recall",
                score.dimension_macro_recall,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            ("m3.true_positive", float(score.true_positive), MetricDirection.INFORMATIONAL),
            ("m3.false_positive", float(score.false_positive), MetricDirection.LOWER_IS_BETTER),
            ("m3.false_negative", float(score.false_negative), MetricDirection.LOWER_IS_BETTER),
        ):
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=direction,
                measurement_source=MeasurementSource.SCORER,
                subject_ref=subject_ref,
            )

        for dimension in score.dimensions:
            prefix = f"m3.dimension.{dimension.dimension.value}"
            for suffix, value, direction in (
                ("precision", dimension.precision, MetricDirection.HIGHER_IS_BETTER),
                ("recall", dimension.recall, MetricDirection.HIGHER_IS_BETTER),
                ("true_positive", float(dimension.true_positive), MetricDirection.INFORMATIONAL),
                (
                    "false_positive",
                    float(dimension.false_positive),
                    MetricDirection.LOWER_IS_BETTER,
                ),
                (
                    "false_negative",
                    float(dimension.false_negative),
                    MetricDirection.LOWER_IS_BETTER,
                ),
            ):
                await self._store.observe_metric(
                    session,
                    case_run_id=case_run_id,
                    metric_name=f"{prefix}.{suffix}",
                    value=value,
                    direction=direction,
                    measurement_source=MeasurementSource.SCORER,
                    subject_ref=subject_ref,
                )


class ProductQuestionQAExecution(BaseModel):
    prediction: QAPrediction
    session_id: str
    turn_index: int


class ExecutionMeasurementTrace(BaseModel):
    model_request_refs: list[str] = Field(default_factory=list)
    model_attempt_count: int = Field(ge=0)
    model_input_tokens: int | None = Field(default=None, ge=0)
    model_output_tokens: int | None = Field(default=None, ge=0)
    model_reasoning_tokens: int | None = Field(default=None, ge=0)
    model_cached_input_tokens: int | None = Field(default=None, ge=0)
    model_provider_cost: float | None = Field(default=None, ge=0)
    model_usage_source: MeasurementSource = MeasurementSource.UNAVAILABLE
    capability_invocation_count: int = Field(ge=0)
    retrieval_invocation_count: int = Field(ge=0)


async def load_execution_measurement_trace(
    session: AsyncSession,
    execution_refs: Iterable[str],
) -> ExecutionMeasurementTrace:
    refs = _stable_unique(execution_refs)
    model_request_ids = [
        ref.removeprefix("model-request:") for ref in refs if ref.startswith("model-request:")
    ]
    task_run_ids = [ref.removeprefix("task-run:") for ref in refs if ref.startswith("task-run:")]
    retrieval_invocation_ids = [
        ref.removeprefix("retrieval-invocation:")
        for ref in refs
        if ref.startswith("retrieval-invocation:")
    ]

    attempts: list[ModelAttemptModel] = []
    if model_request_ids:
        attempts = list(
            await session.scalars(
                select(ModelAttemptModel).where(
                    ModelAttemptModel.model_request_id.in_(model_request_ids)
                )
            )
        )
    capabilities: list[CapabilityInvocationModel] = []
    if task_run_ids:
        capabilities = list(
            await session.scalars(
                select(CapabilityInvocationModel).where(
                    CapabilityInvocationModel.task_run_id.in_(task_run_ids)
                )
            )
        )
    retrievals: list[RetrievalInvocationModel] = []
    if retrieval_invocation_ids:
        retrievals = list(
            await session.scalars(
                select(RetrievalInvocationModel).where(
                    RetrievalInvocationModel.invocation_id.in_(retrieval_invocation_ids)
                )
            )
        )

    usage_sources = {
        str(attempt.usage_json.get("measurement_source"))
        for attempt in attempts
        if attempt.usage_json.get("measurement_source")
    }
    usage_source = (
        MeasurementSource.PROVIDER_EXACT
        if usage_sources == {MeasurementSource.PROVIDER_EXACT.value}
        else MeasurementSource.UNAVAILABLE
    )

    def _sum_usage(key: str) -> int | None:
        values = [attempt.usage_json.get(key) for attempt in attempts]
        numeric = [int(value) for value in values if isinstance(value, int)]
        return sum(numeric) if numeric else None

    provider_costs = [attempt.usage_json.get("provider_cost") for attempt in attempts]
    numeric_costs = [float(value) for value in provider_costs if isinstance(value, (int, float))]
    provider_cost = (
        sum(numeric_costs) if numeric_costs and len(numeric_costs) == len(provider_costs) else None
    )
    return ExecutionMeasurementTrace(
        model_request_refs=[f"model-request:{item}" for item in model_request_ids],
        model_attempt_count=len(attempts),
        model_input_tokens=_sum_usage("input_tokens"),
        model_output_tokens=_sum_usage("output_tokens"),
        model_reasoning_tokens=_sum_usage("reasoning_tokens"),
        model_cached_input_tokens=_sum_usage("cached_input_tokens"),
        model_provider_cost=provider_cost,
        model_usage_source=usage_source,
        capability_invocation_count=len(capabilities),
        retrieval_invocation_count=len(retrievals),
    )


async def record_execution_measurements(
    store: BenchmarkStore,
    session: AsyncSession,
    *,
    case_run_id: str,
    trace: ExecutionMeasurementTrace,
    subject_ref: str,
) -> None:
    exact_values: list[tuple[str, float, MeasurementSource]] = [
        (
            "runtime.model_attempt_count",
            float(trace.model_attempt_count),
            MeasurementSource.EXACT,
        ),
        (
            "runtime.capability_call_count",
            float(trace.capability_invocation_count),
            MeasurementSource.EXACT,
        ),
        (
            "runtime.retrieval_invocation_count",
            float(trace.retrieval_invocation_count),
            MeasurementSource.EXACT,
        ),
    ]
    token_values = (
        ("runtime.model_input_tokens", trace.model_input_tokens),
        ("runtime.model_output_tokens", trace.model_output_tokens),
        ("runtime.model_reasoning_tokens", trace.model_reasoning_tokens),
        ("runtime.model_cached_input_tokens", trace.model_cached_input_tokens),
    )
    for metric_name, token_value in token_values:
        if token_value is not None:
            exact_values.append((metric_name, float(token_value), trace.model_usage_source))
    if trace.model_provider_cost is not None:
        exact_values.append(
            (
                "runtime.model_provider_cost",
                trace.model_provider_cost,
                MeasurementSource.PROVIDER_EXACT,
            )
        )
    for metric_name, metric_value, source in exact_values:
        definition = metric_definition(metric_name)
        await store.observe_metric(
            session,
            case_run_id=case_run_id,
            metric_name=metric_name,
            value=metric_value,
            direction=definition.direction,
            measurement_source=source,
            subject_ref=subject_ref,
            evidence_refs=[],
            metadata={"model_request_refs": cast(JsonValue, trace.model_request_refs)},
        )


class ProductQuestionSessionTurnTrace(BaseModel):
    turn_index: int
    request_id: str
    target_keys: list[str]
    retrieval_refs: list[str] = Field(default_factory=list)
    retrieval_invocation_refs: list[str] = Field(default_factory=list)
    retrieval_dispositions: list[str] = Field(default_factory=list)
    knowledge_revision: int | None = None
    context_id: str | None = None
    parent_context_id: str | None = None
    decision_ref: str | None = None
    investigation_ref: str | None = None


class ProductQuestionSessionTrace(BaseModel):
    session_id: str
    turns: list[ProductQuestionSessionTurnTrace]


class InvestigationCompletionTrace(BaseModel):
    case_id: str
    case_status: str
    case_revision: int = Field(ge=0)
    case_created_at: datetime
    final_decision_ref: str | None = None
    final_decision_case_revision: int | None = Field(default=None, ge=0)
    final_decision_event_revision: int | None = Field(default=None, ge=1)
    final_decision_at: datetime | None = None
    first_status_event_type: str | None = None
    first_status_at: datetime | None = None
    time_to_first_status_seconds: float | None = Field(default=None, ge=0)
    time_to_final_decision_seconds: float | None = Field(default=None, ge=0)
    investigation_episode_count: int = Field(ge=0)
    terminal_episode_count: int = Field(ge=0)
    active_episode_count: int = Field(ge=0)
    failed_episode_count: int = Field(default=0, ge=0)
    timed_out_episode_count: int = Field(default=0, ge=0)
    completed_episode_count: int = Field(default=0, ge=0)
    agent_wall_latency_seconds: float | None = Field(default=None, ge=0)
    investigation_episode_statuses: list[str] = Field(default_factory=list)
    open_evidence_need_count: int = Field(ge=0)
    investigation_task_run_refs: list[str] = Field(default_factory=list)
    decision_task_run_refs: list[str] = Field(default_factory=list)
    execution_refs: list[str] = Field(default_factory=list)
    model_request_refs: list[str] = Field(default_factory=list)

    @property
    def final_decision_present(self) -> bool:
        return self.final_decision_ref is not None


class InvestigationBenchmarkRecorder:
    """Record long-Investigation outcome/latency without changing the online Case."""

    def __init__(self, store: BenchmarkStore | None = None) -> None:
        self._store = store or BenchmarkStore()

    async def record_completion_trace(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        trace: InvestigationCompletionTrace,
        subject_ref: str,
        expected_final_decision: bool = True,
        decision_deadline: datetime | None = None,
    ) -> None:
        normalized_deadline = _as_utc(decision_deadline) if decision_deadline is not None else None
        deadline_met: bool | None = None
        if trace.final_decision_at is not None and normalized_deadline is not None:
            deadline_met = trace.final_decision_at <= normalized_deadline
        success = trace.final_decision_present is expected_final_decision
        if expected_final_decision and success and deadline_met is False:
            success = False
        values: list[tuple[str, float, MeasurementSource]] = [
            (
                "agent.task_success",
                1.0 if success else 0.0,
                MeasurementSource.DERIVED,
            ),
            (
                "m6.investigation_final_decision_completion",
                1.0 if trace.final_decision_present else 0.0,
                MeasurementSource.DERIVED,
            ),
            (
                "m6.investigation_role_episode_count",
                float(trace.investigation_episode_count),
                MeasurementSource.EXACT,
            ),
            (
                "m6.investigation_open_need_count_at_measurement",
                float(trace.open_evidence_need_count),
                MeasurementSource.EXACT,
            ),
        ]
        if trace.time_to_first_status_seconds is not None:
            values.append(
                (
                    "m6.investigation_time_to_first_status_seconds",
                    trace.time_to_first_status_seconds,
                    MeasurementSource.EXACT,
                )
            )
        if trace.time_to_final_decision_seconds is not None:
            values.append(
                (
                    "m6.investigation_time_to_final_decision_seconds",
                    trace.time_to_final_decision_seconds,
                    MeasurementSource.EXACT,
                )
            )
        if trace.agent_wall_latency_seconds is not None:
            values.append(
                (
                    "agent.wall_latency_seconds",
                    trace.agent_wall_latency_seconds,
                    MeasurementSource.EXACT,
                )
            )
        for metric_name, value, source in values:
            definition = metric_definition(metric_name)
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=definition.direction,
                measurement_source=source,
                subject_ref=subject_ref,
                evidence_refs=(
                    [trace.final_decision_ref] if trace.final_decision_ref is not None else []
                ),
                metadata={
                    "case_status": trace.case_status,
                    "case_revision": trace.case_revision,
                    "first_status_event_type": trace.first_status_event_type,
                    "first_status_at": (
                        trace.first_status_at.isoformat()
                        if trace.first_status_at is not None
                        else None
                    ),
                    "final_decision_event_revision": trace.final_decision_event_revision,
                    "terminal_episode_count": trace.terminal_episode_count,
                    "active_episode_count": trace.active_episode_count,
                    "failed_episode_count": trace.failed_episode_count,
                    "timed_out_episode_count": trace.timed_out_episode_count,
                    "completed_episode_count": trace.completed_episode_count,
                    "investigation_episode_statuses": cast(
                        JsonValue,
                        trace.investigation_episode_statuses,
                    ),
                    "expected_final_decision": expected_final_decision,
                    "decision_deadline": (
                        normalized_deadline.isoformat() if normalized_deadline is not None else None
                    ),
                    "deadline_met": deadline_met,
                },
            )
        timeout_definition = metric_definition("agent.timeout_rate")
        for task_ref, status in zip(
            trace.investigation_task_run_refs,
            trace.investigation_episode_statuses,
            strict=True,
        ):
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name="agent.timeout_rate",
                value=1.0 if status == TaskRunStatus.TIMED_OUT.value else 0.0,
                direction=timeout_definition.direction,
                measurement_source=MeasurementSource.EXACT,
                subject_ref=task_ref,
                evidence_refs=(
                    [trace.final_decision_ref] if trace.final_decision_ref is not None else []
                ),
                metadata={
                    "case_id": trace.case_id,
                    "episode_status": status,
                },
            )


async def load_investigation_completion_trace(
    session: AsyncSession,
    case_id: str,
) -> InvestigationCompletionTrace:
    case = await session.get(InvestigationCaseModel, case_id)
    if case is None:
        raise LookupError(f"investigation case not found: {case_id}")
    case_created_at = _as_utc(case.created_at)

    first_status_event = await session.scalar(
        select(CaseStateEventModel)
        .where(CaseStateEventModel.case_id == case_id)
        .order_by(CaseStateEventModel.created_at, CaseStateEventModel.case_revision)
        .limit(1)
    )
    first_status_event_type: str | None = None
    first_status_at: datetime | None = None
    first_status_latency_seconds: float | None = None
    if first_status_event is not None:
        first_status_event_type = first_status_event.event_type
        first_status_at = _as_utc(first_status_event.created_at)
        first_status_latency_seconds = (first_status_at - case_created_at).total_seconds()
        if first_status_latency_seconds < 0:
            raise ValueError("first status timestamp predates investigation creation")

    decision_event = await session.scalar(
        select(CaseStateEventModel)
        .where(
            CaseStateEventModel.case_id == case_id,
            CaseStateEventModel.event_type == CaseStateEventType.DECISION_CHANGED.value,
        )
        .order_by(CaseStateEventModel.case_revision.desc())
        .limit(1)
    )
    decision_ref: str | None = None
    decision_case_revision: int | None = None
    decision_event_revision: int | None = None
    decision_at: datetime | None = None
    latency_seconds: float | None = None
    if decision_event is not None:
        payload = decision_event.payload.get("decision")
        if not isinstance(payload, dict):
            raise ValueError("M4 decision event has no typed decision payload")
        decision = DecisionResult.model_validate(payload)
        if decision.case_id != case_id:
            raise ValueError("M4 decision event references another investigation case")
        if decision.case_revision != decision_event.base_case_revision:
            raise ValueError("M4 decision event revision does not match DecisionResult")
        decision_ref = decision.decision_id
        decision_case_revision = decision.case_revision
        decision_event_revision = decision_event.case_revision
        decision_at = _as_utc(decision_event.created_at)
        latency_seconds = (decision_at - case_created_at).total_seconds()
        if latency_seconds < 0:
            raise ValueError("final decision timestamp predates investigation creation")

    episodes = list(
        await session.scalars(
            select(TaskRunModel)
            .where(
                TaskRunModel.case_id == case_id,
                TaskRunModel.role_id == "InvestigationRole",
            )
            .order_by(TaskRunModel.created_at, TaskRunModel.run_id)
        )
    )
    terminal_episode_count = sum(item.finished_at is not None for item in episodes)
    active_episode_count = len(episodes) - terminal_episode_count
    failed_episode_count = sum(item.status == TaskRunStatus.FAILED.value for item in episodes)
    timed_out_episode_count = sum(item.status == TaskRunStatus.TIMED_OUT.value for item in episodes)
    completed_episode_count = sum(
        item.status == TaskRunStatus.COMPLETED.value for item in episodes
    )
    episode_statuses = [item.status for item in episodes]
    agent_wall_latency_seconds: float | None = None
    if episodes and terminal_episode_count == len(episodes):
        first_episode_at = _as_utc(episodes[0].created_at)
        terminal_times = [
            _as_utc(item.finished_at) for item in episodes if item.finished_at is not None
        ]
        final_episode_at = max(terminal_times)
        agent_wall_latency_seconds = (final_episode_at - first_episode_at).total_seconds()
        if agent_wall_latency_seconds < 0:
            raise ValueError("InvestigationRole terminal time predates first episode creation")
    episode_run_ids = [item.run_id for item in episodes]
    decision_runs = list(
        await session.scalars(
            select(TaskRunModel)
            .where(
                TaskRunModel.case_id == case_id,
                TaskRunModel.role_id == "DecisionRole",
            )
            .order_by(TaskRunModel.created_at, TaskRunModel.run_id)
        )
    )
    decision_run_ids = [item.run_id for item in decision_runs]
    all_role_run_ids = [*episode_run_ids, *decision_run_ids]
    execution_rows = (
        list(
            await session.scalars(
                select(ExecutionRunModel).where(
                    ExecutionRunModel.task_run_id.in_(all_role_run_ids)
                )
            )
        )
        if all_role_run_ids
        else []
    )
    model_request_rows = list(
        await session.scalars(
            select(ModelRequestModel)
            .where(ModelRequestModel.case_id == case_id)
            .order_by(ModelRequestModel.created_at, ModelRequestModel.model_request_id)
        )
    )
    open_need_count = int(
        await session.scalar(
            select(func.count())
            .select_from(EvidenceNeedModel)
            .where(
                EvidenceNeedModel.case_id == case_id,
                EvidenceNeedModel.status.in_(
                    [EvidenceNeedStatus.OPEN.value, EvidenceNeedStatus.BLOCKED.value]
                ),
            )
        )
        or 0
    )
    return InvestigationCompletionTrace(
        case_id=case_id,
        case_status=case.status,
        case_revision=case.current_revision,
        case_created_at=case_created_at,
        final_decision_ref=decision_ref,
        final_decision_case_revision=decision_case_revision,
        final_decision_event_revision=decision_event_revision,
        final_decision_at=decision_at,
        first_status_event_type=first_status_event_type,
        first_status_at=first_status_at,
        time_to_first_status_seconds=first_status_latency_seconds,
        time_to_final_decision_seconds=latency_seconds,
        investigation_episode_count=len(episodes),
        terminal_episode_count=terminal_episode_count,
        active_episode_count=active_episode_count,
        failed_episode_count=failed_episode_count,
        timed_out_episode_count=timed_out_episode_count,
        completed_episode_count=completed_episode_count,
        agent_wall_latency_seconds=agent_wall_latency_seconds,
        investigation_episode_statuses=episode_statuses,
        open_evidence_need_count=open_need_count,
        investigation_task_run_refs=[f"task-run:{item}" for item in episode_run_ids],
        decision_task_run_refs=[f"task-run:{item}" for item in decision_run_ids],
        execution_refs=[item.execution_id for item in execution_rows],
        model_request_refs=[
            f"model-request:{item.model_request_id}" for item in model_request_rows
        ],
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def validate_structured_qa_gold_provenance(
    session: AsyncSession,
    *,
    gold: QAGold,
    evidence_refs: Iterable[str],
    source_ids: Iterable[str],
    knowledge_revision: int,
    absence_checks: Iterable[tuple[str, str]] = (),
) -> None:
    """Fail closed unless structured-authority evidence supports the frozen QA gold facts."""

    refs = _stable_unique(evidence_refs)
    declared_sources = set(source_ids)
    if not refs or not declared_sources:
        raise ValueError("structured QA gold provenance requires evidence refs and source ids")

    supported_facts: set[str] = set()
    observed_sources: set[str] = set()
    relation_refs: list[str] = []
    for ref in refs:
        if not ref.startswith("evidence:"):
            raise ValueError(f"structured QA gold has invalid EvidenceRef: {ref}")
        link = await session.get(EvidenceLinkModel, ref.removeprefix("evidence:"))
        if link is None:
            raise ValueError(f"structured QA gold EvidenceRef does not resolve: {ref}")
        observation = await session.get(ObservationModel, link.observation_id)
        if observation is None:
            raise ValueError(f"structured QA gold EvidenceRef has no Observation: {ref}")
        observed_sources.add(observation.source_id)
        if observation.source_id not in declared_sources:
            raise ValueError(
                "structured QA gold EvidenceRef source is outside declared authorities: "
                f"{observation.source_id}"
            )
        if link.target_kind == "claim":
            claim = await session.get(ClaimModel, link.target_id)
            if claim is None:
                raise ValueError(f"structured QA gold claim does not resolve: {link.target_id}")
            _require_visible_revision(
                created_revision=claim.created_revision,
                superseded_revision=claim.superseded_revision,
                knowledge_revision=knowledge_revision,
                target_ref=f"claim:{link.target_id}",
            )
            subject = await session.get(ObjectModel, claim.subject_id)
            if subject is None:
                raise ValueError(f"structured QA gold claim subject is missing: {claim.subject_id}")
            supported_facts.add(
                render_claim_fact(
                    subject.canonical_key,
                    claim.predicate,
                    claim.value,
                    qualifier=claim.qualifier,
                )
            )
        elif link.target_kind == "relation":
            relation_refs.append(f"relation:{link.target_id}")
            relation = await session.get(RelationModel, link.target_id)
            if relation is None:
                raise ValueError(f"structured QA gold relation does not resolve: {link.target_id}")
            _require_visible_revision(
                created_revision=relation.created_revision,
                superseded_revision=relation.superseded_revision,
                knowledge_revision=knowledge_revision,
                target_ref=f"relation:{link.target_id}",
            )
            source = await session.get(ObjectModel, relation.source_object_id)
            target = await session.get(ObjectModel, relation.target_object_id)
            if source is None or target is None:
                raise ValueError(
                    f"structured QA gold relation endpoint is missing: {link.target_id}"
                )
            supported_facts.add(
                render_relation_fact(
                    source.canonical_key,
                    relation.relation_type,
                    target.canonical_key,
                    qualifier=relation.qualifier,
                    target_properties=target.properties,
                )
            )
        else:
            raise ValueError(
                "structured QA gold preflight accepts claim/relation Evidence only; "
                f"got {link.target_kind}:{link.target_id}"
            )

    if observed_sources != declared_sources:
        raise ValueError(
            "structured QA gold declared source set does not match evidence: "
            f"declared={sorted(declared_sources)}, observed={sorted(observed_sources)}"
        )
    expected_facts = set(gold.required_facts) | set(gold.acceptable_answer_facts)
    missing = expected_facts - supported_facts
    if missing:
        raise ValueError(
            "structured QA gold facts are not supported by declared EvidenceRefs: "
            + ", ".join(sorted(missing))
        )

    if gold.required_relation_paths:
        observed_paths = {
            tuple(path) for path in await _relation_paths_for_refs(session, relation_refs)
        }
        missing_paths = {tuple(path) for path in gold.required_relation_paths} - observed_paths
        if missing_paths:
            rendered = "; ".join(" -> ".join(path) for path in sorted(missing_paths))
            raise ValueError(
                "structured QA gold relation paths are not supported by declared EvidenceRefs: "
                + rendered
            )

    for subject_key, predicate in absence_checks:
        subject = await session.scalar(
            select(ObjectModel).where(ObjectModel.canonical_key == subject_key)
        )
        if subject is None or subject.created_revision > knowledge_revision:
            raise ValueError(
                "structured QA gold absence subject is not visible at pinned Knowledge revision: "
                f"{subject_key}@{knowledge_revision}"
            )
        present = await session.scalar(
            select(ClaimModel.claim_id).where(
                ClaimModel.subject_id == subject.object_id,
                ClaimModel.predicate == predicate,
                ClaimModel.lifecycle == "accepted",
                ClaimModel.created_revision <= knowledge_revision,
                (
                    ClaimModel.superseded_revision.is_(None)
                    | (ClaimModel.superseded_revision > knowledge_revision)
                ),
            )
        )
        if present is not None:
            raise ValueError(
                "structured QA gold absence check is false at pinned Knowledge revision: "
                f"{subject_key} {predicate}@{knowledge_revision}"
            )


class QABenchmarkRecorder:
    def __init__(self, store: BenchmarkStore | None = None) -> None:
        self._store = store or BenchmarkStore()

    async def record_case_score(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        score: QAScore,
        subject_ref: str,
        prediction: QAPrediction | None = None,
        gold: QAGold | None = None,
    ) -> None:
        evidence_refs = (
            _stable_unique(citation.evidence_ref for citation in prediction.citations)
            if prediction is not None
            else []
        )
        execution_refs = list(prediction.execution_refs) if prediction is not None else []
        values: list[tuple[str, float]] = [
            ("m6.answer_accuracy", score.answer_accuracy),
            ("m6.groundedness", score.groundedness),
            ("m6.citation_correctness", score.citation_correctness),
            ("m6.citation_completeness", score.citation_completeness),
            ("m6.unknown_correctness", score.unknown_correctness),
            ("m6.conflict_handling", score.conflict_handling),
            ("m6.completion_correctness", score.completion_correctness),
        ]
        if score.multi_hop_correctness is not None:
            values.append(("m6.multi_hop_correctness", score.multi_hop_correctness))
        if score.interactive_latency_seconds is not None:
            values.append(("m6.interactive_latency_seconds", score.interactive_latency_seconds))
        for metric_name, value in values:
            definition = metric_definition(metric_name)
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=definition.direction,
                measurement_source=MeasurementSource.SCORER,
                subject_ref=subject_ref,
                evidence_refs=evidence_refs,
                metadata={"execution_refs": cast(JsonValue, execution_refs)},
            )

        if prediction is not None and gold is not None:
            expects_gap = gold.completion_expectation == "continuation_requested"
            opened_gap = prediction.completion_status == "continuation_requested"
            if expects_gap:
                definition = metric_definition("agent.critical_evidence_need_recall")
                await self._store.observe_metric(
                    session,
                    case_run_id=case_run_id,
                    metric_name="agent.critical_evidence_need_recall",
                    value=1.0 if opened_gap else 0.0,
                    direction=definition.direction,
                    measurement_source=MeasurementSource.SCORER,
                    subject_ref=subject_ref,
                    metadata={
                        "owner": "M6 Continuation -> M4 EvidenceNeed",
                        "expected_completion": gold.completion_expectation,
                        "observed_completion": prediction.completion_status,
                        "execution_refs": cast(JsonValue, execution_refs),
                    },
                )
            if opened_gap:
                definition = metric_definition("agent.false_gap_rate")
                await self._store.observe_metric(
                    session,
                    case_run_id=case_run_id,
                    metric_name="agent.false_gap_rate",
                    value=0.0 if expects_gap else 1.0,
                    direction=definition.direction,
                    measurement_source=MeasurementSource.SCORER,
                    subject_ref=subject_ref,
                    metadata={
                        "owner": "M6 Continuation -> M4 EvidenceNeed",
                        "expected_completion": gold.completion_expectation,
                        "observed_completion": prediction.completion_status,
                        "execution_refs": cast(JsonValue, execution_refs),
                    },
                )

    async def record_session_trace_score(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        context_chain_correctness: float,
        target_carry_correctness: float,
        retrieval_overlap_rate: float | None = None,
        retrieval_invocation_coverage: float | None = None,
        retrieval_reuse_rate: float | None = None,
        subject_ref: str,
    ) -> None:
        values: list[tuple[str, float]] = [
            ("m6.session_context_chain_correctness", context_chain_correctness),
            ("m6.session_target_carry_correctness", target_carry_correctness),
        ]
        if retrieval_overlap_rate is not None:
            values.append(("m6.session_retrieval_overlap_rate", retrieval_overlap_rate))
        if retrieval_invocation_coverage is not None:
            values.append(
                (
                    "m6.session_retrieval_invocation_coverage",
                    retrieval_invocation_coverage,
                )
            )
        if retrieval_reuse_rate is not None:
            values.append(("m6.session_retrieval_reuse_rate", retrieval_reuse_rate))
        for metric_name, value in values:
            definition = metric_definition(metric_name)
            await self._store.observe_metric(
                session,
                case_run_id=case_run_id,
                metric_name=metric_name,
                value=value,
                direction=definition.direction,
                measurement_source=MeasurementSource.DERIVED,
                subject_ref=subject_ref,
            )

    async def record_execution_measurements(
        self,
        session: AsyncSession,
        *,
        case_run_id: str,
        trace: ExecutionMeasurementTrace,
        subject_ref: str,
    ) -> None:
        await record_execution_measurements(
            self._store,
            session,
            case_run_id=case_run_id,
            trace=trace,
            subject_ref=subject_ref,
        )


def project_decision_to_qa_prediction(
    *,
    benchmark_case_id: str,
    decision: DecisionResult,
    state: InvestigationState,
    relation_paths: Iterable[Iterable[str]] = (),
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    interactive_latency_seconds: float | None = None,
    execution_refs: Iterable[str] = (),
) -> QAPrediction:
    """Project a persisted M6 decision into the evaluation-neutral QA contract."""

    if not benchmark_case_id.strip():
        raise ValueError("benchmark_case_id cannot be empty")
    if decision.case_id != state.case_id:
        raise ValueError("decision case_id does not match M4 state")
    current = state.current_decision
    if current is not None and current.get("decision_id") != decision.decision_id:
        raise ValueError("M4 current_decision does not match projected decision")

    support_verdicts = dict(citation_support or {})
    eligible_indexes = {
        index
        for index, conclusion in enumerate(decision.conclusions)
        if conclusion.type is not ConclusionType.RECOMMENDATION
    }
    citations: list[QACitationCheck] = []
    consumed_verdicts: set[tuple[int, str]] = set()
    for citation in decision.citations:
        if citation.conclusion_index not in eligible_indexes:
            continue
        if citation.conclusion_index >= len(decision.conclusions):
            raise ValueError("decision citation conclusion_index is out of range")
        conclusion = decision.conclusions[citation.conclusion_index]
        verdict_key = (citation.conclusion_index, citation.evidence_ref)
        explicit = support_verdicts.get(verdict_key)
        if explicit is None:
            supports = _confirmed_state_supports(
                state,
                statement=conclusion.statement,
                evidence_ref=citation.evidence_ref,
            )
        else:
            supports = explicit
            consumed_verdicts.add(verdict_key)
        citations.append(
            QACitationCheck(
                conclusion_fact=conclusion.statement,
                evidence_ref=citation.evidence_ref,
                supports=supports,
            )
        )
    stale_verdicts = set(support_verdicts) - consumed_verdicts
    if stale_verdicts:
        rendered = ", ".join(
            f"{index}:{evidence_ref}" for index, evidence_ref in sorted(stale_verdicts)
        )
        raise ValueError(f"citation support verdict does not match decision citation: {rendered}")

    reasoning_refs = [
        ref
        for index, conclusion in enumerate(decision.conclusions)
        if index in eligible_indexes
        for ref in conclusion.reasoning_relation_refs
    ]
    merged_execution_refs = _stable_unique(
        [
            f"case:{decision.case_id}",
            decision.decision_id,
            f"case-revision:{decision.case_id}@{decision.case_revision}",
            *reasoning_refs,
            *execution_refs,
        ]
    )
    return QAPrediction(
        case_id=benchmark_case_id,
        conclusion_facts=[
            conclusion.statement
            for conclusion in decision.conclusions
            if conclusion.type is not ConclusionType.RECOMMENDATION
        ],
        relation_paths=[list(path) for path in relation_paths],
        citations=citations,
        unknowns=list(decision.unknowns),
        conflicts=list(decision.conflicts),
        assumptions=list(decision.assumptions),
        completion_status="answered",
        interactive_latency_seconds=interactive_latency_seconds,
        execution_refs=merged_execution_refs,
    )


def project_continuation_state_to_qa_prediction(
    *,
    benchmark_case_id: str,
    state: InvestigationState,
    evidence_need_refs: Iterable[str],
    interactive_latency_seconds: float | None = None,
    execution_refs: Iterable[str] = (),
) -> QAPrediction:
    """Project a product state that intentionally requested more evidence."""

    needs = list(evidence_need_refs)
    if not needs:
        raise ValueError("continuation projection requires at least one EvidenceNeed ref")
    return QAPrediction(
        case_id=benchmark_case_id,
        conclusion_facts=[],
        citations=[],
        unknowns=[item.proposition for item in state.unknowns],
        conflicts=[item.proposition for item in state.conflicts],
        completion_status="continuation_requested",
        interactive_latency_seconds=interactive_latency_seconds,
        execution_refs=_stable_unique(
            [
                f"case:{state.case_id}",
                f"case-revision:{state.case_id}@{state.case_revision}",
                *needs,
                *execution_refs,
            ]
        ),
    )


async def load_product_qa_prediction(
    session: AsyncSession,
    *,
    benchmark_case_id: str,
    product_case_id: str,
    relation_paths: Iterable[Iterable[str]] = (),
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    interactive_latency_seconds: float | None = None,
    execution_refs: Iterable[str] = (),
    state_service: InvestigationStateService | None = None,
) -> QAPrediction:
    """Project either a final Decision or a durable M6 continuation outcome."""

    service = state_service or InvestigationStateService()
    state = await service.get_state(session, product_case_id)
    if state.current_decision is not None:
        try:
            decision = DecisionResult.model_validate(state.current_decision)
        except ValueError as exc:
            raise ValueError(f"persisted decision is invalid for case: {product_case_id}") from exc
        return project_decision_to_qa_prediction(
            benchmark_case_id=benchmark_case_id,
            decision=decision,
            state=state,
            relation_paths=relation_paths,
            citation_support=citation_support,
            interactive_latency_seconds=interactive_latency_seconds,
            execution_refs=execution_refs,
        )

    needs = await service.list_evidence_needs(
        session,
        product_case_id,
        statuses={EvidenceNeedStatus.OPEN, EvidenceNeedStatus.BLOCKED},
    )
    if not needs:
        raise LookupError(f"case has no persisted decision or continuation: {product_case_id}")
    return project_continuation_state_to_qa_prediction(
        benchmark_case_id=benchmark_case_id,
        state=state,
        evidence_need_refs=[f"evidence-need:{item.need_id}" for item in needs],
        interactive_latency_seconds=interactive_latency_seconds,
        execution_refs=execution_refs,
    )


async def execute_product_case_qa_prediction(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    benchmark_case_id: str,
    product_case_id: str,
    provider: ModelProvider,
    relation_paths: Iterable[Iterable[str]] = (),
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    execution_refs: Iterable[str] = (),
    state_service: InvestigationStateService | None = None,
) -> QAPrediction:
    """Execute live M6 reasoning over a durable Product Case without mutating that Case.

    The source M4 state is read in a short transaction, the remote model call happens with no
    database transaction held open, and the normal DecisionRuntime/M4 write gate is exercised in
    a disposable transaction that is rolled back after the evaluation-neutral prediction is
    materialized. Model execution recording remains durable when ``provider`` is a
    RecordedModelProvider because that recorder owns its own short transactions.
    """

    service = state_service or InvestigationStateService()
    async with session_factory() as session:
        state = await service.get_state(session, product_case_id)
        citation_sources = await _load_citation_sources(session, state)
        await session.rollback()

    if state.current_decision is not None:
        raise ValueError("live Product QA source case must not already contain a current decision")

    started = monotonic()
    proposal = await ModelDecisionPlanner(provider).plan(
        state,
        citation_sources=citation_sources,
    )

    async with session_factory() as session:
        transaction = await session.begin()
        try:
            outcome = await DecisionRuntime(state_service=service).commit_proposal(
                session,
                state=state,
                proposal=proposal,
                citation_sources=citation_sources,
            )
            projected_state = await service.get_state(session, product_case_id)
            latency = monotonic() - started
            merged_execution_refs = _stable_unique([f"case:{product_case_id}", *execution_refs])
            if outcome.decision is not None:
                prediction = project_decision_to_qa_prediction(
                    benchmark_case_id=benchmark_case_id,
                    decision=outcome.decision,
                    state=projected_state,
                    relation_paths=relation_paths,
                    citation_support=citation_support,
                    interactive_latency_seconds=latency,
                    execution_refs=merged_execution_refs,
                )
            else:
                assert outcome.continuation is not None
                prediction = project_continuation_state_to_qa_prediction(
                    benchmark_case_id=benchmark_case_id,
                    state=projected_state,
                    evidence_need_refs=[f"evidence-need:{outcome.continuation.need.need_id}"],
                    interactive_latency_seconds=latency,
                    execution_refs=merged_execution_refs,
                )
        finally:
            await transaction.rollback()
    return prediction


async def execute_product_question_qa_execution(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    benchmark_case_id: str,
    request_id: str,
    provider: ModelProvider,
    question: str,
    cve_id: str | None = None,
    object_id: str | None = None,
    task_kind: TaskKind = TaskKind.LOOKUP,
    required_source_roles: Iterable[str] = (),
    priority: int = 50,
    interactive_timeout_seconds: int = 5,
    retrieval_limit: int = 8,
    principal: str = "system:benchmark-m6",
    session_id: str | None = None,
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    execution_refs: Iterable[str] = (),
    expected_knowledge_revision: int | None = None,
) -> ProductQuestionQAExecution:
    """Run the real Product AskQuestion path and project its durable outcome into QA metrics.

    Unlike the durable-Case evaluator above, this function intentionally keeps Product runtime
    records: TaskRun, ExecutionRun, ModelRequest/Attempt and validated DecisionResult are the
    benchmark evidence for interactive latency and execution provenance.
    """

    started = monotonic()
    async with session_factory() as session:
        if expected_knowledge_revision is not None:
            current_revision = await current_knowledge_revision(session)
            if current_revision != expected_knowledge_revision:
                raise ValueError(
                    "live Product QA knowledge revision drifted before execution: "
                    f"expected={expected_knowledge_revision}, current={current_revision}"
                )
        result = await AskQuestionUseCase(
            policy_path=settings.runtime_policy_path,
            task_event_stream_name=settings.task_event_stream_name,
            model_provider=provider,
            model_payload_persistence="redacted_runtime_artifact",
        ).execute(
            session,
            AskQuestionCommand(
                principal=principal,
                request_id=request_id,
                session_id=session_id,
                question=question,
                cve_id=cve_id,
                object_id=object_id,
                task_kind=task_kind,
                required_source_roles=list(required_source_roles),
                priority=priority,
                interactive_timeout_seconds=interactive_timeout_seconds,
                retrieval_limit=retrieval_limit,
            ),
        )
    latency = monotonic() - started

    async with session_factory() as session:
        (
            runtime_refs,
            context_revisions,
            runtime_relation_paths,
        ) = await _product_question_execution_refs(
            session,
            request_id,
        )
        if expected_knowledge_revision is not None:
            if context_revisions != {expected_knowledge_revision}:
                raise ValueError(
                    "live Product QA ContextManifest knowledge revision does not match pin: "
                    f"expected={expected_knowledge_revision}, observed={sorted(context_revisions)}"
                )
            current_revision = await current_knowledge_revision(session)
            if current_revision != expected_knowledge_revision:
                raise ValueError(
                    "live Product QA knowledge revision drifted during execution: "
                    f"expected={expected_knowledge_revision}, current={current_revision}"
                )
        merged_execution_refs = _stable_unique(
            [f"product-request:{request_id}", *runtime_refs, *execution_refs]
        )
        if result.mode == "completed":
            assert result.decision is not None
            stored = await DecisionResultStore().get(session, result.decision.decision_id)
            decision = DecisionResult.model_validate(
                stored.model_dump(mode="json", exclude={"created_at"})
            )
            return ProductQuestionQAExecution(
                prediction=project_validated_decision_to_qa_prediction(
                    benchmark_case_id=benchmark_case_id,
                    decision=decision,
                    relation_paths=runtime_relation_paths,
                    citation_support=citation_support,
                    interactive_latency_seconds=latency,
                    execution_refs=merged_execution_refs,
                ),
                session_id=result.session_id,
                turn_index=result.turn_index,
            )

        assert result.investigation is not None
        investigation = result.investigation
        state = await InvestigationStateService().get_state(session, investigation.case_id)
        need_refs = [f"evidence-need:{item.need_id}" for item in investigation.open_evidence_needs]
        if not need_refs:
            raise ValueError("accepted Product question has no durable EvidenceNeed")
        return ProductQuestionQAExecution(
            prediction=project_continuation_state_to_qa_prediction(
                benchmark_case_id=benchmark_case_id,
                state=state,
                evidence_need_refs=need_refs,
                interactive_latency_seconds=latency,
                execution_refs=merged_execution_refs,
            ),
            session_id=result.session_id,
            turn_index=result.turn_index,
        )


async def execute_product_question_qa_prediction(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    settings: Settings,
    benchmark_case_id: str,
    request_id: str,
    provider: ModelProvider,
    question: str,
    cve_id: str | None = None,
    object_id: str | None = None,
    task_kind: TaskKind = TaskKind.LOOKUP,
    required_source_roles: Iterable[str] = (),
    priority: int = 50,
    interactive_timeout_seconds: int = 5,
    retrieval_limit: int = 8,
    principal: str = "system:benchmark-m6",
    session_id: str | None = None,
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    execution_refs: Iterable[str] = (),
    expected_knowledge_revision: int | None = None,
) -> QAPrediction:
    execution = await execute_product_question_qa_execution(
        session_factory,
        settings=settings,
        benchmark_case_id=benchmark_case_id,
        request_id=request_id,
        provider=provider,
        question=question,
        cve_id=cve_id,
        object_id=object_id,
        task_kind=task_kind,
        required_source_roles=required_source_roles,
        priority=priority,
        interactive_timeout_seconds=interactive_timeout_seconds,
        retrieval_limit=retrieval_limit,
        principal=principal,
        session_id=session_id,
        citation_support=citation_support,
        execution_refs=execution_refs,
        expected_knowledge_revision=expected_knowledge_revision,
    )
    return execution.prediction


def project_validated_decision_to_qa_prediction(
    *,
    benchmark_case_id: str,
    decision: DecisionResult,
    relation_paths: Iterable[Iterable[str]] = (),
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    interactive_latency_seconds: float | None = None,
    execution_refs: Iterable[str] = (),
) -> QAPrediction:
    """Project an already M6-validated DecisionResult when its ephemeral state is unavailable.

    A FACT citation defaults to supported because DecisionService accepts a fact only when the
    exact proposition and cited EvidenceRef coexist in confirmed state. INFERENCE support is not
    implied by that invariant and therefore requires an explicit adjudication verdict.
    """

    if not benchmark_case_id.strip():
        raise ValueError("benchmark_case_id cannot be empty")
    support_verdicts = dict(citation_support or {})
    eligible_indexes = {
        index
        for index, conclusion in enumerate(decision.conclusions)
        if conclusion.type is not ConclusionType.RECOMMENDATION
    }
    citations: list[QACitationCheck] = []
    consumed_verdicts: set[tuple[int, str]] = set()
    for citation in decision.citations:
        if citation.conclusion_index not in eligible_indexes:
            continue
        if citation.conclusion_index >= len(decision.conclusions):
            raise ValueError("decision citation conclusion_index is out of range")
        conclusion = decision.conclusions[citation.conclusion_index]
        verdict_key = (citation.conclusion_index, citation.evidence_ref)
        explicit = support_verdicts.get(verdict_key)
        if explicit is not None:
            supports = explicit
            consumed_verdicts.add(verdict_key)
        else:
            supports = conclusion.type is ConclusionType.FACT
        citations.append(
            QACitationCheck(
                conclusion_fact=conclusion.statement,
                evidence_ref=citation.evidence_ref,
                supports=supports,
            )
        )
    _reject_stale_citation_verdicts(support_verdicts, consumed_verdicts)
    reasoning_refs = _decision_reasoning_refs(decision.conclusions, eligible_indexes)
    return QAPrediction(
        case_id=benchmark_case_id,
        conclusion_facts=[
            conclusion.statement
            for conclusion in decision.conclusions
            if conclusion.type is not ConclusionType.RECOMMENDATION
        ],
        relation_paths=[list(path) for path in relation_paths],
        citations=citations,
        unknowns=list(decision.unknowns),
        conflicts=list(decision.conflicts),
        assumptions=list(decision.assumptions),
        completion_status="answered",
        interactive_latency_seconds=interactive_latency_seconds,
        execution_refs=_stable_unique([decision.decision_id, *reasoning_refs, *execution_refs]),
    )


async def _product_question_execution_refs(
    session: AsyncSession,
    request_id: str,
) -> tuple[list[str], set[int], list[list[str]]]:
    requests = list(
        await session.scalars(
            select(ModelRequestModel)
            .where(ModelRequestModel.purpose == "m6.decision")
            .order_by(ModelRequestModel.created_at.desc())
            .limit(100)
        )
    )
    matching = [
        item for item in requests if item.metadata_json.get("product_request_id") == request_id
    ]
    refs: list[str] = []
    context_revisions: set[int] = set()
    relation_refs: list[str] = []
    for item in matching:
        refs.append(f"model-request:{item.model_request_id}")
        if item.task_run_id:
            refs.append(f"task-run:{item.task_run_id}")
            run = await session.get(TaskRunModel, item.task_run_id)
            if run is not None:
                context = await session.get(
                    ContextManifestVersionModel,
                    run.context_manifest_version_id,
                )
                if context is not None and context.knowledge_revision is not None:
                    context_revisions.add(context.knowledge_revision)
                if context is not None:
                    raw_relation_refs = context.manifest_json.get("relation_refs")
                    if isinstance(raw_relation_refs, list):
                        relation_refs.extend(
                            item for item in raw_relation_refs if isinstance(item, str)
                        )
                    raw_retrieval_refs = context.manifest_json.get("retrieval_invocation_refs")
                    if isinstance(raw_retrieval_refs, list):
                        refs.extend(
                            item
                            for item in raw_retrieval_refs
                            if isinstance(item, str) and item.startswith("retrieval-invocation:")
                        )
        if item.execution_id:
            refs.append(item.execution_id)
        if item.budget_ref:
            refs.append(item.budget_ref)
    relation_paths = await _relation_paths_for_refs(session, _stable_unique(relation_refs))
    return _stable_unique(refs), context_revisions, relation_paths


async def load_product_question_session_trace(
    session: AsyncSession,
    session_id: str,
) -> ProductQuestionSessionTrace:
    turns = list(
        await session.scalars(
            select(QuestionSessionTurnModel)
            .where(QuestionSessionTurnModel.session_id == session_id)
            .order_by(QuestionSessionTurnModel.turn_index)
        )
    )
    if not turns:
        raise LookupError(f"question session has no turns: {session_id}")

    object_ids = {
        object_id
        for turn in turns
        for object_id in turn.target_object_ids
        if isinstance(object_id, str) and object_id
    }
    objects = {
        item.object_id: item.canonical_key
        for item in await session.scalars(
            select(ObjectModel).where(ObjectModel.object_id.in_(object_ids))
        )
    }
    trace_turns: list[ProductQuestionSessionTurnTrace] = []
    for turn in turns:
        parent_context_id: str | None = None
        retrieval_refs: list[str] = []
        retrieval_invocation_refs: list[str] = []
        retrieval_dispositions: list[str] = []
        if turn.context_id is not None:
            context = await session.scalar(
                select(ContextManifestVersionModel)
                .where(ContextManifestVersionModel.context_id == turn.context_id)
                .order_by(ContextManifestVersionModel.context_revision.desc())
                .limit(1)
            )
            if context is None:
                raise LookupError(
                    f"question session turn references missing ContextManifest: {turn.context_id}"
                )
            parent_context_id = context.parent_context_id
            raw_evidence_refs = context.manifest_json.get("evidence_refs")
            if isinstance(raw_evidence_refs, list):
                retrieval_refs = [
                    ref
                    for ref in raw_evidence_refs
                    if isinstance(ref, str) and ref.startswith("document-chunk:")
                ]
            raw_invocation_refs = context.manifest_json.get("retrieval_invocation_refs")
            if isinstance(raw_invocation_refs, list):
                retrieval_invocation_refs = [
                    ref for ref in raw_invocation_refs if isinstance(ref, str)
                ]
            for ref in retrieval_invocation_refs:
                prefix = "retrieval-invocation:"
                if not ref.startswith(prefix):
                    raise ValueError(f"invalid retrieval invocation ref in ContextManifest: {ref}")
                invocation = await session.get(
                    RetrievalInvocationModel,
                    ref.removeprefix(prefix),
                )
                if invocation is None:
                    raise LookupError(f"retrieval invocation does not resolve: {ref}")
                if invocation.product_session_id != session_id:
                    raise ValueError("retrieval invocation belongs to another Product session")
                if invocation.product_turn_index != turn.turn_index:
                    raise ValueError("retrieval invocation Product turn index does not match")
                retrieval_refs.extend(
                    ref
                    for ref in invocation.result_refs
                    if isinstance(ref, str) and ref.startswith("document-chunk:")
                )
                retrieval_dispositions.append(invocation.disposition)
        target_keys: list[str] = []
        for object_id in turn.target_object_ids:
            canonical_key = objects.get(object_id)
            if canonical_key is None:
                raise LookupError(
                    f"question session turn references missing Knowledge object: {object_id}"
                )
            target_keys.append(canonical_key)
        trace_turns.append(
            ProductQuestionSessionTurnTrace(
                turn_index=turn.turn_index,
                request_id=turn.request_id,
                target_keys=_stable_unique(target_keys),
                retrieval_refs=_stable_unique(retrieval_refs),
                retrieval_invocation_refs=_stable_unique(retrieval_invocation_refs),
                retrieval_dispositions=retrieval_dispositions,
                knowledge_revision=turn.knowledge_revision,
                context_id=turn.context_id,
                parent_context_id=parent_context_id,
                decision_ref=turn.decision_ref,
                investigation_ref=turn.investigation_ref,
            )
        )
    return ProductQuestionSessionTrace(session_id=session_id, turns=trace_turns)


async def _relation_paths_for_refs(
    session: AsyncSession,
    relation_refs: Iterable[str],
) -> list[list[str]]:
    relation_ids = [
        ref.removeprefix("relation:") for ref in relation_refs if ref.startswith("relation:")
    ]
    if not relation_ids:
        return []
    relations = list(
        await session.scalars(
            select(RelationModel).where(RelationModel.relation_id.in_(relation_ids))
        )
    )
    object_ids = {
        object_id
        for relation in relations
        for object_id in (relation.source_object_id, relation.target_object_id)
    }
    objects = {
        item.object_id: item
        for item in await session.scalars(
            select(ObjectModel).where(ObjectModel.object_id.in_(object_ids))
        )
    }
    paths: list[list[str]] = []
    for first in relations:
        source = objects.get(first.source_object_id)
        middle = objects.get(first.target_object_id)
        if source is None or middle is None:
            continue
        for second in relations:
            if second.source_object_id != first.target_object_id:
                continue
            target = objects.get(second.target_object_id)
            if target is None:
                continue
            paths.append(
                [
                    source.canonical_key,
                    first.relation_type,
                    middle.canonical_key,
                    second.relation_type,
                    target.canonical_key,
                ]
            )
    return [list(path) for path in dict.fromkeys(tuple(path) for path in paths)]


def _decision_reasoning_refs(
    conclusions: Iterable[DecisionConclusion],
    eligible_indexes: set[int],
) -> list[str]:
    return [
        ref
        for index, conclusion in enumerate(conclusions)
        if index in eligible_indexes
        for ref in conclusion.reasoning_relation_refs
    ]


def _reject_stale_citation_verdicts(
    support_verdicts: Mapping[tuple[int, str], bool],
    consumed_verdicts: set[tuple[int, str]],
) -> None:
    stale_verdicts = set(support_verdicts) - consumed_verdicts
    if stale_verdicts:
        rendered = ", ".join(
            f"{index}:{evidence_ref}" for index, evidence_ref in sorted(stale_verdicts)
        )
        raise ValueError(f"citation support verdict does not match decision citation: {rendered}")


async def _load_citation_sources(
    session: AsyncSession,
    state: InvestigationState,
) -> list[CitationSource]:
    refs = {
        ref
        for group in (
            state.confirmed,
            state.tentative,
            state.conflicts,
            state.unknowns,
            state.hypotheses,
        )
        for item in group
        for ref in item.evidence_refs
        if ref.startswith("evidence:")
    }
    result: list[CitationSource] = []
    for ref in sorted(refs):
        link = await session.get(EvidenceLinkModel, ref.removeprefix("evidence:"))
        if link is None:
            continue
        observation = await session.get(ObservationModel, link.observation_id)
        if observation is None:
            continue
        source_ref = f"source:{observation.source_id}:{observation.external_object_id}"
        if observation.external_revision:
            source_ref += f"@{observation.external_revision}"
        result.append(
            CitationSource(
                evidence_ref=ref,
                source_ref=source_ref,
                locator=cast(dict[str, JsonValue], dict(link.locator)),
            )
        )
    return result


def _require_visible_revision(
    *,
    created_revision: int,
    superseded_revision: int | None,
    knowledge_revision: int,
    target_ref: str,
) -> None:
    if created_revision > knowledge_revision or (
        superseded_revision is not None and superseded_revision <= knowledge_revision
    ):
        raise ValueError(
            "structured QA gold target is not visible at pinned Knowledge revision: "
            f"{target_ref}@{knowledge_revision}"
        )


def _confirmed_state_supports(
    state: InvestigationState,
    *,
    statement: str,
    evidence_ref: str,
) -> bool:
    return any(
        item.proposition == statement and evidence_ref in item.evidence_refs
        for item in state.confirmed
    )


def _stable_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


async def capture_current_deployment_revision(
    session: AsyncSession,
    settings: Settings,
    *,
    repo_root: Path = Path("."),
) -> DeploymentRevision:
    schema_revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    if not isinstance(schema_revision, str) or not schema_revision:
        raise RuntimeError("cannot resolve current Alembic schema revision")
    git_revision = _git_working_revision(repo_root)
    source_inventory_hash = _file_hash(repo_root / "config/source-inventory.json")
    policy = load_runtime_policy(repo_root / settings.runtime_policy_path)
    skill_registry_revision = _skill_registry_digest()
    model_endpoint_digest = (
        sha256(settings.model_base_url.rstrip("/").encode()).hexdigest()[:16]
        if settings.model_base_url
        else None
    )
    model_provider_revision = (
        f"openai-compatible-v1:{settings.model_name}:endpoint-{model_endpoint_digest}"
        if settings.model_name and model_endpoint_digest
        else "unconfigured"
    )
    semantic_config = {
        "environment": settings.environment,
        "schema_revision": schema_revision,
        "source_inventory_hash": source_inventory_hash,
        "vocabulary_revision": VOCABULARY_REVISION,
        "policy_revision": policy.policy_revision,
        "capability_registry_revision": "unbound",
        "skill_registry_revision": skill_registry_revision,
        "model_provider_revision": model_provider_revision,
        "model_timeout_seconds": settings.model_timeout_seconds,
        "model_max_tokens": settings.model_max_tokens,
        "model_temperature": settings.model_temperature,
        "model_reasoning_effort": settings.model_reasoning_effort,
        "model_max_attempts": settings.model_max_attempts,
        "model_retry_base_seconds": settings.model_retry_base_seconds,
        "model_retry_max_seconds": settings.model_retry_max_seconds,
        "embedding_model_name": settings.embedding_model_name,
        "embedding_dimensions": settings.embedding_dimensions,
        "hot_cache_ttl_seconds": settings.hot_cache_ttl_seconds,
        "task_event_stream_name": settings.task_event_stream_name,
    }
    configuration_digest = _digest_json(semantic_config)
    identity_payload = {
        "git_revision": git_revision,
        **semantic_config,
        "configuration_digest": configuration_digest,
    }
    deployment_id = f"deployment:{_digest_json(identity_payload)[:32]}"
    return DeploymentRevision(
        deployment_revision_id=deployment_id,
        git_commit=git_revision,
        schema_revision=schema_revision,
        source_inventory_hash=source_inventory_hash,
        vocabulary_revision=VOCABULARY_REVISION,
        policy_revision=policy.policy_revision,
        capability_registry_revision="unbound",
        skill_registry_revision=skill_registry_revision,
        model_provider_revision=model_provider_revision,
        configuration_digest=configuration_digest,
        created_at=datetime.now(UTC),
    )


async def ensure_benchmark_deployment_revision(
    session: AsyncSession,
    settings: Settings,
    *,
    deployment_revision_id: str | None = None,
    repo_root: Path = Path("."),
) -> str:
    """Resolve a pinned benchmark deployment or freeze the current repo state once."""

    if deployment_revision_id is not None:
        existing = await session.get(DeploymentRevisionModel, deployment_revision_id)
        if existing is None:
            raise LookupError(f"deployment revision not found: {deployment_revision_id}")
        current = await capture_current_deployment_revision(
            session,
            settings,
            repo_root=repo_root,
        )
        if current.deployment_revision_id != deployment_revision_id:
            raise RuntimeError(
                "current repository/runtime coordinate no longer matches the pinned "
                f"deployment revision: expected={deployment_revision_id} "
                f"current={current.deployment_revision_id}"
            )
        return deployment_revision_id
    deployment = await capture_current_deployment_revision(
        session,
        settings,
        repo_root=repo_root,
    )
    await BenchmarkStore().register_deployment(session, deployment)
    return deployment.deployment_revision_id


def _git_working_revision(repo_root: Path) -> str:
    head = _git(repo_root, "rev-parse", "HEAD").decode().strip()
    diff = _git(repo_root, "diff", "HEAD", "--binary")
    untracked_raw = _git(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    untracked_paths = [item.decode() for item in untracked_raw.split(b"\0") if item]
    hasher = sha256()
    hasher.update(diff)
    for relative in sorted(untracked_paths):
        path = repo_root / relative
        if not path.is_file():
            continue
        hasher.update(relative.encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    dirty_digest = hasher.hexdigest()
    if not diff and not untracked_paths:
        return head
    return f"{head}+dirty.{dirty_digest[:16]}"


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", *args],
        cwd=repo_root,
        stderr=subprocess.DEVNULL,
    )


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _skill_registry_digest() -> str:
    payload = [skill.model_dump(mode="json") for skill in seeded_skills()]
    return f"seed-skills:{_digest_json(payload)[:24]}"


def _digest_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
