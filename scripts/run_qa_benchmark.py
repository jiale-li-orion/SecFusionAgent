from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, Field, JsonValue, model_validator

from apps.evaluation_runtime import (
    QABenchmarkRecorder,
    ensure_benchmark_deployment_revision,
    execute_product_case_qa_prediction,
    execute_product_question_qa_execution,
    execute_product_question_qa_prediction,
    load_product_qa_prediction,
    load_product_question_session_trace,
    validate_structured_qa_gold_provenance,
)
from apps.model_runtime import create_recorded_model_provider
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
from packages.task_runtime.contracts.models import TaskKind


class LiveProductQuestion(BaseModel):
    question: str = Field(min_length=1)
    principal: str = "system:benchmark-m6"
    cve_id: str | None = None
    object_id: str | None = None
    task_kind: TaskKind = TaskKind.LOOKUP
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    interactive_timeout_seconds: int = Field(default=5, ge=1, le=30)
    retrieval_limit: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def validate_product_question(self) -> LiveProductQuestion:
        if self.cve_id and self.object_id:
            raise ValueError("live Product question cve_id and object_id are mutually exclusive")
        if self.task_kind is TaskKind.LOOKUP and not (self.cve_id or self.object_id):
            raise ValueError("live Product LOOKUP requires cve_id or object_id")
        if self.task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE} and not (
            self.cve_id or self.object_id
        ):
            raise ValueError("live Product investigation question requires a bound target")
        if self.task_kind is TaskKind.ENRICHMENT:
            raise ValueError("enrichment is not a Product QA route")
        return self


class QASessionManifestTurn(BaseModel):
    turn_id: str = Field(min_length=1)
    question: LiveProductSessionQuestion
    gold: QAGold
    citation_support: dict[str, bool] = Field(default_factory=dict)
    expected_target_keys: list[str] = Field(default_factory=list)
    adjudications: list[QAAdjudicationRecord] = Field(default_factory=list)
    gold_provenance: QAGoldProvenance | None = None

    @model_validator(mode="after")
    def validate_turn(self) -> QASessionManifestTurn:
        for key in self.citation_support:
            index, separator, evidence_ref = key.partition(":")
            if not separator or not index.isdigit() or not evidence_ref:
                raise ValueError(
                    "citation_support keys must use '<conclusion_index>:<evidence_ref>'"
                )
        validate_qa_adjudication_history(self.adjudications)
        if (
            self.gold_provenance is not None
            and self.gold_provenance.mode == "human_adjudicated"
            and not self.adjudications
        ):
            raise ValueError("human-adjudicated QA gold requires adjudication history")
        return self


class QASessionManifestCase(BaseModel):
    case_id: str = Field(min_length=1)
    principal: str = "system:benchmark-m6"
    state_carry_policy: Literal["targets_and_outcomes_v1"] = "targets_and_outcomes_v1"
    turns: list[QASessionManifestTurn] = Field(min_length=2)
    tags: list[str] = Field(default_factory=list)
    latency_class: str = "interactive_session"

    @model_validator(mode="after")
    def validate_session_case(self) -> QASessionManifestCase:
        turn_ids = [turn.turn_id for turn in self.turns]
        if len(set(turn_ids)) != len(turn_ids):
            raise ValueError("QASessionCase turn ids must be unique")
        first = self.turns[0]
        if first.question.task_kind is TaskKind.LOOKUP and not (
            first.question.cve_id or first.question.object_id
        ):
            raise ValueError("QASessionCase first LOOKUP turn requires an explicit target")
        for index, turn in enumerate(self.turns, start=1):
            expected_case_id = f"{self.case_id}#turn:{turn.turn_id}"
            if turn.gold.case_id != expected_case_id:
                raise ValueError(
                    "QASessionCase turn gold case_id must equal " + expected_case_id
                )
            if index > 1:
                if turn.question.cve_id is not None or turn.question.object_id is not None:
                    raise ValueError(
                        "QASessionCase follow-up turns must rely on Product session target carry"
                    )
                if not turn.expected_target_keys:
                    raise ValueError(
                        "QASessionCase follow-up turns require expected_target_keys"
                    )
            if index < len(self.turns) and turn.gold.completion_expectation != "answered":
                raise ValueError(
                    "non-final QASessionCase turns must complete synchronously as answered"
                )
        return self


class LiveProductSessionQuestion(BaseModel):
    question: str = Field(min_length=1)
    cve_id: str | None = None
    object_id: str | None = None
    task_kind: TaskKind = TaskKind.LOOKUP
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    interactive_timeout_seconds: int = Field(default=5, ge=1, le=30)
    retrieval_limit: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def validate_session_question(self) -> LiveProductSessionQuestion:
        if self.cve_id and self.object_id:
            raise ValueError("session turn cve_id and object_id are mutually exclusive")
        if self.task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            raise ValueError("first QASessionCase slice supports LOOKUP/RETRIEVE turns only")
        return self


class QAGoldAbsenceCheck(BaseModel):
    subject_key: str = Field(min_length=1)
    predicate: str = Field(min_length=1)


class QAGoldProvenance(BaseModel):
    mode: Literal["synthetic", "structured_authority", "human_adjudicated"]
    evidence_refs: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    absence_checks: list[QAGoldAbsenceCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_provenance(self) -> QAGoldProvenance:
        if self.mode == "structured_authority":
            if not self.evidence_refs:
                raise ValueError("structured-authority QA gold requires evidence_refs")
            if not self.source_ids:
                raise ValueError("structured-authority QA gold requires source_ids")
        return self


class QABenchmarkManifestCase(BaseModel):
    case_id: str
    input: dict[str, JsonValue] = Field(default_factory=dict)
    gold: QAGold
    prediction: QAPrediction | None = None
    product_case_id: str | None = None
    live_product_case_id: str | None = None
    live_product_question: LiveProductQuestion | None = None
    citation_support: dict[str, bool] = Field(default_factory=dict)
    relation_paths: list[list[str]] = Field(default_factory=list)
    interactive_latency_seconds: float | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    latency_class: str = "interactive"
    execution_refs: list[str] = Field(default_factory=list)
    adjudications: list[QAAdjudicationRecord] = Field(default_factory=list)
    gold_provenance: QAGoldProvenance | None = None

    @model_validator(mode="after")
    def validate_prediction_source(self) -> QABenchmarkManifestCase:
        source_count = sum(
            source is not None
            for source in (
                self.prediction,
                self.product_case_id,
                self.live_product_case_id,
                self.live_product_question,
            )
        )
        if source_count != 1:
            raise ValueError(
                "QA case requires exactly one of prediction, product_case_id, "
                "live_product_case_id, or live_product_question"
            )
        if self.prediction is not None and self.prediction.case_id != self.case_id:
            raise ValueError("QA inline prediction case_id does not match manifest case")
        if _is_live_case(self) and self.interactive_latency_seconds is not None:
            raise ValueError(
                "live Product QA measures latency; it cannot accept a supplied latency"
            )
        if self.live_product_question is not None and self.relation_paths:
            raise ValueError(
                "live Product Question relation_paths are derived from runtime ContextManifest"
            )
        for key in self.citation_support:
            index, separator, evidence_ref = key.partition(":")
            if not separator or not index.isdigit() or not evidence_ref:
                raise ValueError(
                    "citation_support keys must use '<conclusion_index>:<evidence_ref>'"
                )
        validate_qa_adjudication_history(self.adjudications)
        if (
            self.gold_provenance is not None
            and self.gold_provenance.mode == "human_adjudicated"
            and not self.adjudications
        ):
            raise ValueError("human-adjudicated QA gold requires adjudication history")
        return self


class QABenchmarkManifest(BaseModel):
    suite_id: str = "m6-qa"
    purpose: str = "Frozen QA accuracy, grounding, citation and multi-hop benchmark"
    evaluator_revision: str = "qa-v1"
    knowledge_revision: int | None = Field(default=None, ge=0)
    cases: list[QABenchmarkManifestCase] = Field(default_factory=list)
    sessions: list[QASessionManifestCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_execution_mode(self) -> QABenchmarkManifest:
        if bool(self.cases) == bool(self.sessions):
            raise ValueError("QA manifest requires exactly one of cases or sessions")
        if self.sessions:
            if self.knowledge_revision is None:
                raise ValueError("QASessionCase benchmark requires a pinned knowledge_revision")
            session_ids = [item.case_id for item in self.sessions]
            if len(set(session_ids)) != len(session_ids):
                raise ValueError("QASessionCase ids must be unique")
            return self
        live_count = sum(_is_live_case(item) for item in self.cases)
        if live_count not in {0, len(self.cases)}:
            raise ValueError("one BenchmarkRun cannot mix live Product QA with offline QA cases")
        live_profiles = {
            _execution_profile(item)
            for item in self.cases
            if _is_live_case(item)
        }
        if len(live_profiles) > 1:
            raise ValueError(
                "one BenchmarkRun cannot mix durable-Case live QA with Product Question live QA"
            )
        if any(item.live_product_question is not None for item in self.cases):
            if self.knowledge_revision is None:
                raise ValueError("live Product Question QA requires a pinned knowledge_revision")
        if any(
            item.gold_provenance is not None
            and item.gold_provenance.mode == "structured_authority"
            for item in self.cases
        ) and self.knowledge_revision is None:
            raise ValueError("structured-authority QA gold requires a pinned knowledge_revision")
        return self


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
    if manifest.sessions:
        return await _run_sessions(
            manifest,
            suite_revision=suite_revision,
            deployment_revision_id=deployment_revision_id,
        )
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
    execution_mode = (
        BenchmarkExecutionMode.LIVE_EXTERNAL
        if any(_is_live_case(item) for item in manifest.cases)
        else BenchmarkExecutionMode.OFFLINE_SCORER
    )
    if execution_mode is BenchmarkExecutionMode.LIVE_EXTERNAL and (
        not settings.model_base_url or not settings.model_name
    ):
        raise RuntimeError("live Product QA requires a configured model provider")
    world_snapshot_ref = (
        f"knowledge-revision:{manifest.knowledge_revision}"
        if manifest.knowledge_revision is not None
        else None
    )
    manifest_payload = manifest.model_dump(mode="json")
    manifest_digest = _digest(manifest_payload)
    gold_digest = _digest(
        [
            {
                "gold": item.gold.model_dump(mode="json"),
                "gold_provenance": (
                    item.gold_provenance.model_dump(mode="json")
                    if item.gold_provenance is not None
                    else None
                ),
                "adjudications": [
                    record.model_dump(mode="json") for record in item.adjudications
                ],
            }
            for item in manifest.cases
        ]
    )

    client: httpx.AsyncClient | None = None
    try:
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            for item in manifest.cases:
                if (
                    item.gold_provenance is not None
                    and item.gold_provenance.mode == "structured_authority"
                ):
                    assert manifest.knowledge_revision is not None
                    await validate_structured_qa_gold_provenance(
                        session,
                        gold=item.gold,
                        evidence_refs=item.gold_provenance.evidence_refs,
                        source_ids=item.gold_provenance.source_ids,
                        knowledge_revision=manifest.knowledge_revision,
                        absence_checks=[
                            (check.subject_key, check.predicate)
                            for check in item.gold_provenance.absence_checks
                        ],
                    )
            case_refs: list[str] = []
            for item in manifest.cases:
                case_ref = f"{item.case_id}@{suite_revision}"
                case_refs.append(case_ref)
                target_refs = list(item.execution_refs)
                if item.prediction is not None:
                    target_refs = list(item.prediction.execution_refs or item.execution_refs)
                elif item.product_case_id is not None:
                    target_refs = [f"case:{item.product_case_id}", *target_refs]
                elif item.live_product_case_id is not None:
                    target_refs = [f"case:{item.live_product_case_id}", *target_refs]
                elif item.live_product_question is not None:
                    target_refs = [
                        *_live_question_target_refs(item.live_product_question),
                        *target_refs,
                    ]
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=item.case_id,
                        case_revision=suite_revision,
                        input=item.input,
                        execution_profile=_execution_profile(item),
                        target_refs=list(dict.fromkeys(target_refs)),
                        world_snapshot_ref=world_snapshot_ref,
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
                    default_world_snapshot_ref=world_snapshot_ref,
                    scoring_profile={
                        "manifest_digest": manifest_digest,
                        "knowledge_revision": manifest.knowledge_revision,
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
                execution_mode=execution_mode,
                environment=settings.environment,
                model_config_ref=(
                    f"model:{settings.model_name}" if settings.model_name else "model:unconfigured"
                ),
                world_snapshot_ref=world_snapshot_ref,
                now=now,
            )
        provider = None
        if execution_mode is BenchmarkExecutionMode.LIVE_EXTERNAL:
            client = httpx.AsyncClient(timeout=settings.model_timeout_seconds)
            provider = create_recorded_model_provider(settings, factory, client)
            if provider is None:
                async with factory() as session, session.begin():
                    await store.finish_run(
                        session,
                        run.benchmark_run_id,
                        status=BenchmarkRunStatus.FAILED,
                    )
                raise RuntimeError("live Product QA model provider is unavailable")

        per_case: dict[str, object] = {}
        for item in manifest.cases:
            async with factory() as session, session.begin():
                case_run = await store.start_case_run(
                    session,
                    benchmark_run_id=run.benchmark_run_id,
                    case_ref=f"{item.case_id}@{suite_revision}",
                )
            try:
                if item.prediction is not None:
                    prediction = item.prediction
                elif item.product_case_id is not None:
                    async with factory() as session:
                        prediction = await load_product_qa_prediction(
                            session,
                            benchmark_case_id=item.case_id,
                            product_case_id=item.product_case_id,
                            relation_paths=item.relation_paths,
                            citation_support=_citation_support(item.citation_support),
                            interactive_latency_seconds=item.interactive_latency_seconds,
                            execution_refs=item.execution_refs,
                        )
                        await session.rollback()
                elif item.live_product_case_id is not None:
                    assert provider is not None
                    prediction = await execute_product_case_qa_prediction(
                        factory,
                        benchmark_case_id=item.case_id,
                        product_case_id=item.live_product_case_id,
                        provider=provider,
                        relation_paths=item.relation_paths,
                        citation_support=_citation_support(item.citation_support),
                        execution_refs=item.execution_refs,
                    )
                else:
                    assert item.live_product_question is not None
                    assert provider is not None
                    question = item.live_product_question
                    prediction = await execute_product_question_qa_prediction(
                        factory,
                        settings=settings,
                        benchmark_case_id=item.case_id,
                        request_id=f"benchmark:{run.benchmark_run_id}:{item.case_id}",
                        provider=provider,
                        question=question.question,
                        cve_id=question.cve_id,
                        object_id=question.object_id,
                        task_kind=question.task_kind,
                        required_source_roles=question.required_source_roles,
                        priority=question.priority,
                        interactive_timeout_seconds=question.interactive_timeout_seconds,
                        retrieval_limit=question.retrieval_limit,
                        principal=question.principal,
                        citation_support=_citation_support(item.citation_support),
                        execution_refs=item.execution_refs,
                        expected_knowledge_revision=manifest.knowledge_revision,
                    )
                score = score_qa(gold=item.gold, prediction=prediction)
                async with factory() as session, session.begin():
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
                    )
                per_case[item.case_id] = score.model_dump(mode="json")
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
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{manifest.suite_id}@{suite_revision}",
            "manifest_digest": manifest_digest,
            "gold_revision": f"qa-gold:{gold_digest}",
            "case_count": len(manifest.cases),
            "execution_mode": execution_mode.value,
            "world_snapshot_ref": world_snapshot_ref,
            "case_scores": per_case,
        }
    finally:
        if client is not None:
            await client.aclose()
        await engine.dispose()


async def _run_sessions(
    manifest: QABenchmarkManifest,
    *,
    suite_revision: int,
    deployment_revision_id: str | None,
) -> dict[str, Any]:
    if not manifest.sessions:
        raise ValueError("QASessionCase benchmark requires at least one session")
    assert manifest.knowledge_revision is not None

    register_runtime_models()
    settings = get_settings()
    if not settings.model_base_url or not settings.model_name:
        raise RuntimeError("live Product QA session benchmark requires a configured model provider")
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    store = BenchmarkStore()
    recorder = QABenchmarkRecorder(store)
    now = datetime.now(UTC)
    world_snapshot_ref = f"knowledge-revision:{manifest.knowledge_revision}"
    manifest_digest = _digest(manifest.model_dump(mode="json"))
    gold_digest = _digest(
        [
            {
                "case_id": session_case.case_id,
                "state_carry_policy": session_case.state_carry_policy,
                "turns": [
                    {
                        "turn_id": turn.turn_id,
                        "gold": turn.gold.model_dump(mode="json"),
                        "gold_provenance": (
                            turn.gold_provenance.model_dump(mode="json")
                            if turn.gold_provenance is not None
                            else None
                        ),
                        "adjudications": [
                            record.model_dump(mode="json") for record in turn.adjudications
                        ],
                        "expected_target_keys": list(turn.expected_target_keys),
                    }
                    for turn in session_case.turns
                ],
            }
            for session_case in manifest.sessions
        ]
    )

    client: httpx.AsyncClient | None = None
    try:
        async with factory() as session, session.begin():
            resolved_deployment_id = await ensure_benchmark_deployment_revision(
                session,
                settings,
                deployment_revision_id=deployment_revision_id,
            )
            for session_case in manifest.sessions:
                for turn in session_case.turns:
                    provenance = turn.gold_provenance
                    if provenance is None or provenance.mode != "structured_authority":
                        continue
                    await validate_structured_qa_gold_provenance(
                        session,
                        gold=turn.gold,
                        evidence_refs=provenance.evidence_refs,
                        source_ids=provenance.source_ids,
                        knowledge_revision=manifest.knowledge_revision,
                        absence_checks=[
                            (check.subject_key, check.predicate)
                            for check in provenance.absence_checks
                        ],
                    )

            case_refs: list[str] = []
            for session_case in manifest.sessions:
                case_ref = f"{session_case.case_id}@{suite_revision}"
                case_refs.append(case_ref)
                target_refs: list[str] = []
                for turn in session_case.turns:
                    if turn.question.cve_id:
                        target_refs.append(f"cve:{turn.question.cve_id.upper()}")
                    if turn.question.object_id:
                        target_refs.append(f"object:{turn.question.object_id}")
                    target_refs.extend(
                        f"knowledge-key:{key}" for key in turn.expected_target_keys
                    )
                await store.register_case(
                    session,
                    BenchmarkCase(
                        case_id=session_case.case_id,
                        case_revision=suite_revision,
                        input=cast(
                            dict[str, JsonValue],
                            {
                                "state_carry_policy": session_case.state_carry_policy,
                                "turns": [
                                    {
                                        "turn_id": turn.turn_id,
                                        "question": turn.question.model_dump(mode="json"),
                                    }
                                    for turn in session_case.turns
                                ],
                            },
                        ),
                        execution_profile="product_question_session_live",
                        target_refs=list(dict.fromkeys(target_refs)),
                        world_snapshot_ref=world_snapshot_ref,
                        expected_behavior=cast(
                            dict[str, JsonValue],
                            {
                                "turns": [
                                    {
                                        "turn_id": turn.turn_id,
                                        "gold": turn.gold.model_dump(mode="json"),
                                        "expected_target_keys": turn.expected_target_keys,
                                    }
                                    for turn in session_case.turns
                                ]
                            },
                        ),
                        gold_ref=f"qa-session-gold:{gold_digest}#{session_case.case_id}",
                        tags=["m6", "qa", "session", *session_case.tags],
                        latency_class=session_case.latency_class,
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
                    gold_revision=f"qa-session-gold:{gold_digest}",
                    evaluator_revision=manifest.evaluator_revision,
                    default_world_snapshot_ref=world_snapshot_ref,
                    scoring_profile={
                        "manifest_digest": manifest_digest,
                        "knowledge_revision": manifest.knowledge_revision,
                        "state_carry_policy": "targets_and_outcomes_v1",
                        "metrics": [
                            "m6.answer_accuracy",
                            "m6.groundedness",
                            "m6.citation_correctness",
                            "m6.citation_completeness",
                            "m6.multi_hop_correctness",
                            "m6.unknown_correctness",
                            "m6.conflict_handling",
                            "m6.completion_correctness",
                            "m6.interactive_latency_seconds",
                            "m6.session_context_chain_correctness",
                            "m6.session_target_carry_correctness",
                            "m6.session_retrieval_overlap_rate",
                        ],
                    },
                    created_at=now,
                ),
            )
            run = await store.start_run(
                session,
                suite_ref=f"{manifest.suite_id}@{suite_revision}",
                deployment_revision_id=resolved_deployment_id,
                execution_mode=BenchmarkExecutionMode.LIVE_EXTERNAL,
                environment=settings.environment,
                model_config_ref=f"model:{settings.model_name}",
                world_snapshot_ref=world_snapshot_ref,
                now=now,
            )

        client = httpx.AsyncClient(timeout=settings.model_timeout_seconds)
        provider = create_recorded_model_provider(settings, factory, client)
        if provider is None:
            async with factory() as session, session.begin():
                await store.finish_run(
                    session,
                    run.benchmark_run_id,
                    status=BenchmarkRunStatus.FAILED,
                )
            raise RuntimeError("live Product QA session model provider is unavailable")

        session_scores = await _execute_session_cases(
            manifest,
            factory=factory,
            store=store,
            recorder=recorder,
            provider=provider,
            benchmark_run_id=run.benchmark_run_id,
            suite_revision=suite_revision,
        )
        async with factory() as session, session.begin():
            await store.finish_run(
                session,
                run.benchmark_run_id,
                status=BenchmarkRunStatus.COMPLETED,
            )
        return {
            "benchmark_run_id": run.benchmark_run_id,
            "deployment_revision_id": resolved_deployment_id,
            "suite_ref": f"{manifest.suite_id}@{suite_revision}",
            "manifest_digest": manifest_digest,
            "gold_revision": f"qa-session-gold:{gold_digest}",
            "session_count": len(manifest.sessions),
            "execution_mode": BenchmarkExecutionMode.LIVE_EXTERNAL.value,
            "world_snapshot_ref": world_snapshot_ref,
            "session_scores": session_scores,
        }
    finally:
        if client is not None:
            await client.aclose()
        await engine.dispose()


async def _execute_session_cases(
    manifest: QABenchmarkManifest,
    *,
    factory: Any,
    store: BenchmarkStore,
    recorder: QABenchmarkRecorder,
    provider: Any,
    benchmark_run_id: str,
    suite_revision: int,
) -> dict[str, object]:
    assert manifest.knowledge_revision is not None
    per_session: dict[str, object] = {}
    for session_case in manifest.sessions:
        async with factory() as session, session.begin():
            case_run = await store.start_case_run(
                session,
                benchmark_run_id=benchmark_run_id,
                case_ref=f"{session_case.case_id}@{suite_revision}",
            )
        product_session_id: str | None = None
        execution_refs: list[str] = []
        turn_scores: dict[str, object] = {}
        try:
            for ordinal, turn in enumerate(session_case.turns, start=1):
                question = turn.question
                request_id = (
                    f"benchmark:{benchmark_run_id}:{session_case.case_id}:"
                    f"turn:{turn.turn_id}"
                )
                execution = await execute_product_question_qa_execution(
                    factory,
                    settings=get_settings(),
                    benchmark_case_id=turn.gold.case_id,
                    request_id=request_id,
                    provider=provider,
                    question=question.question,
                    cve_id=question.cve_id,
                    object_id=question.object_id,
                    task_kind=question.task_kind,
                    required_source_roles=question.required_source_roles,
                    priority=question.priority,
                    interactive_timeout_seconds=question.interactive_timeout_seconds,
                    retrieval_limit=question.retrieval_limit,
                    principal=session_case.principal,
                    session_id=product_session_id,
                    citation_support=_citation_support(turn.citation_support),
                    expected_knowledge_revision=manifest.knowledge_revision,
                )
                if execution.turn_index != ordinal:
                    raise ValueError(
                        "Product QA session turn index drifted: "
                        f"expected={ordinal}, observed={execution.turn_index}"
                    )
                if product_session_id is None:
                    product_session_id = execution.session_id
                elif execution.session_id != product_session_id:
                    raise ValueError("Product QA session identity changed between turns")
                score = score_qa(gold=turn.gold, prediction=execution.prediction)
                async with factory() as session, session.begin():
                    await recorder.record_case_score(
                        session,
                        case_run_id=case_run.case_run_id,
                        score=score,
                        subject_ref=f"qa-session:{session_case.case_id}#turn:{turn.turn_id}",
                    )
                execution_refs.extend(execution.prediction.execution_refs)
                turn_scores[turn.turn_id] = score.model_dump(mode="json")

            assert product_session_id is not None
            async with factory() as session:
                trace = await load_product_question_session_trace(
                    session,
                    product_session_id,
                )
                await session.rollback()
            if len(trace.turns) != len(session_case.turns):
                raise ValueError("Product QA session durable turn count does not match manifest")
            context_chain_correctness = _session_context_chain_correctness(trace.turns)
            target_carry_correctness = _session_target_carry_correctness(
                trace.turns,
                session_case.turns,
            )
            retrieval_overlap_rate = _session_retrieval_overlap_rate(
                trace.turns,
                session_case.turns,
            )
            async with factory() as session, session.begin():
                await recorder.record_session_trace_score(
                    session,
                    case_run_id=case_run.case_run_id,
                    context_chain_correctness=context_chain_correctness,
                    target_carry_correctness=target_carry_correctness,
                    retrieval_overlap_rate=retrieval_overlap_rate,
                    subject_ref=f"qa-session:{session_case.case_id}",
                )
                await store.finish_case_run(
                    session,
                    case_run.case_run_id,
                    status=BenchmarkCaseRunStatus.PASSED,
                    artifact_refs=list(
                        dict.fromkeys(
                            [f"question-session:{product_session_id}", *execution_refs]
                        )
                    ),
                )
            per_session[session_case.case_id] = {
                "session_id": product_session_id,
                "turn_scores": turn_scores,
                "context_chain_correctness": context_chain_correctness,
                "target_carry_correctness": target_carry_correctness,
                "retrieval_overlap_rate": retrieval_overlap_rate,
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
                    benchmark_run_id,
                    status=BenchmarkRunStatus.FAILED,
                )
            raise
    return per_session


def _session_context_chain_correctness(turns: list[Any]) -> float:
    if not turns:
        return 0.0
    if turns[0].context_id is None or turns[0].parent_context_id is not None:
        return 0.0
    for previous, current in pairwise(turns):
        if current.context_id is None or current.parent_context_id != previous.context_id:
            return 0.0
    return 1.0


def _session_target_carry_correctness(
    observed_turns: list[Any],
    expected_turns: list[QASessionManifestTurn],
) -> float:
    checks = [
        set(observed.target_keys) == set(expected.expected_target_keys)
        for index, (observed, expected) in enumerate(
            zip(observed_turns, expected_turns, strict=True),
            start=1,
        )
        if index > 1
    ]
    return sum(checks) / len(checks) if checks else 1.0


def _session_retrieval_overlap_rate(
    observed_turns: list[Any],
    expected_turns: list[QASessionManifestTurn],
) -> float | None:
    prior_refs: set[str] = set()
    overlaps: list[float] = []
    for index, (observed, expected) in enumerate(
        zip(observed_turns, expected_turns, strict=True),
        start=1,
    ):
        current_refs = set(observed.retrieval_refs)
        if (
            index > 1
            and expected.question.task_kind is TaskKind.RETRIEVE
            and current_refs
        ):
            overlaps.append(len(current_refs & prior_refs) / len(current_refs))
        prior_refs.update(current_refs)
    if not overlaps:
        return None
    return sum(overlaps) / len(overlaps)


def _citation_support(values: dict[str, bool]) -> dict[tuple[int, str], bool]:
    result: dict[tuple[int, str], bool] = {}
    for key, supports in values.items():
        index, _, evidence_ref = key.partition(":")
        result[(int(index), evidence_ref)] = supports
    return result


def _execution_profile(item: QABenchmarkManifestCase) -> str:
    if item.live_product_question is not None:
        return "product_question_live"
    if item.live_product_case_id is not None:
        return "product_case_decision_live"
    if item.product_case_id is not None:
        return "product_decision_projection"
    return "offline_scorer"


def _is_live_case(item: QABenchmarkManifestCase) -> bool:
    return item.live_product_case_id is not None or item.live_product_question is not None


def _live_question_target_refs(question: LiveProductQuestion) -> list[str]:
    refs: list[str] = []
    if question.object_id:
        refs.append(f"object:{question.object_id}")
    if question.cve_id:
        refs.append(f"cve:{question.cve_id.upper()}")
    return refs


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
