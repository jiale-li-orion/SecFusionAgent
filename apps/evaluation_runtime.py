from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import cast

from pydantic import JsonValue
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.question_facts import render_claim_fact, render_relation_fact
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
from packages.investigation.state.contracts import EvidenceNeedStatus, InvestigationState
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import ConclusionType, DecisionConclusion, DecisionResult
from packages.reasoning.model import ModelDecisionPlanner
from packages.reasoning.storage import DecisionResultStore
from packages.runtime.model.storage import ModelRequestModel
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import Settings
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.contracts.models import TaskKind
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
            (
                "m3.micro_precision",
                score.micro_precision,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            (
                "m3.micro_recall",
                score.micro_recall,
                MetricDirection.HIGHER_IS_BETTER,
            ),
            (
                "m3.true_positive",
                float(score.true_positive),
                MetricDirection.INFORMATIONAL,
            ),
            (
                "m3.false_positive",
                float(score.false_positive),
                MetricDirection.LOWER_IS_BETTER,
            ),
            (
                "m3.false_negative",
                float(score.false_negative),
                MetricDirection.LOWER_IS_BETTER,
            ),
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
                (
                    "precision",
                    dimension.precision,
                    MetricDirection.HIGHER_IS_BETTER,
                ),
                (
                    "recall",
                    dimension.recall,
                    MetricDirection.HIGHER_IS_BETTER,
                ),
                (
                    "true_positive",
                    float(dimension.true_positive),
                    MetricDirection.INFORMATIONAL,
                ),
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
                raise ValueError(
                    f"structured QA gold relation does not resolve: {link.target_id}"
                )
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
            tuple(path)
            for path in await _relation_paths_for_refs(session, relation_refs)
        }
        missing_paths = {
            tuple(path) for path in gold.required_relation_paths
        } - observed_paths
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
    ) -> None:
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
        raise ValueError(
            "live Product QA source case must not already contain a current decision"
        )

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
            merged_execution_refs = _stable_unique(
                [f"case:{product_case_id}", *execution_refs]
            )
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
                    evidence_need_refs=[
                        f"evidence-need:{outcome.continuation.need.need_id}"
                    ],
                    interactive_latency_seconds=latency,
                    execution_refs=merged_execution_refs,
                )
        finally:
            await transaction.rollback()
    return prediction


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
    citation_support: Mapping[tuple[int, str], bool] | None = None,
    execution_refs: Iterable[str] = (),
    expected_knowledge_revision: int | None = None,
) -> QAPrediction:
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
        ).execute(
            session,
            AskQuestionCommand(
                principal=principal,
                request_id=request_id,
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
        runtime_refs, context_revisions, runtime_relation_paths = (
            await _product_question_execution_refs(
            session,
            request_id,
            )
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
            return project_validated_decision_to_qa_prediction(
                benchmark_case_id=benchmark_case_id,
                decision=decision,
                relation_paths=runtime_relation_paths,
                citation_support=citation_support,
                interactive_latency_seconds=latency,
                execution_refs=merged_execution_refs,
            )

        assert result.investigation is not None
        investigation = result.investigation
        state = await InvestigationStateService().get_state(session, investigation.case_id)
        need_refs = [
            f"evidence-need:{item.need_id}" for item in investigation.open_evidence_needs
        ]
        if not need_refs:
            raise ValueError("accepted Product question has no durable EvidenceNeed")
        return project_continuation_state_to_qa_prediction(
            benchmark_case_id=benchmark_case_id,
            state=state,
            evidence_need_refs=need_refs,
            interactive_latency_seconds=latency,
            execution_refs=merged_execution_refs,
        )


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
        execution_refs=_stable_unique(
            [decision.decision_id, *reasoning_refs, *execution_refs]
        ),
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
        item
        for item in requests
        if item.metadata_json.get("product_request_id") == request_id
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
        if item.execution_id:
            refs.append(item.execution_id)
        if item.budget_ref:
            refs.append(item.budget_ref)
    relation_paths = await _relation_paths_for_refs(session, _stable_unique(relation_refs))
    return _stable_unique(refs), context_revisions, relation_paths


async def _relation_paths_for_refs(
    session: AsyncSession,
    relation_refs: Iterable[str],
) -> list[list[str]]:
    relation_ids = [
        ref.removeprefix("relation:")
        for ref in relation_refs
        if ref.startswith("relation:")
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
    model_provider_revision = (
        f"openai-compatible:{settings.model_name}" if settings.model_name else "unconfigured"
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
