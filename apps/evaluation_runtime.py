from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.evaluation.benchmark import (
    BenchmarkStore,
    DeploymentRevision,
    MeasurementSource,
    MetricDirection,
)
from packages.evaluation.benchmark.metrics import metric_definition
from packages.evaluation.benchmark.storage import DeploymentRevisionModel
from packages.evaluation.m1_m3 import EnrichmentScore
from packages.evaluation.qa import QACitationCheck, QAPrediction, QAScore
from packages.intelligence.knowledge.vocabulary import VOCABULARY_REVISION
from packages.investigation.skills.seeds import seeded_skills
from packages.investigation.state.contracts import EvidenceNeedStatus, InvestigationState
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.decision import ConclusionType, DecisionResult
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import Settings


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
