from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps import evaluation_runtime
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import BenchmarkStore, DeploymentRevision
from packages.evaluation.qa import QAGold
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import (
    DecisionCommit,
    InvestigationState,
    InvestigationStateItem,
)
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.citation import DecisionCitation
from packages.reasoning.decision import ConclusionType, DecisionConclusion, DecisionResult
from packages.reasoning.model import DecisionPlannerResponse, FinalDecisionProposal
from packages.runtime.model.service import RecordedModelProvider
from packages.shared.config import Settings
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.models import TaskKind
from packages.task_runtime.storage.models import TaskRunModel


class _MetricCaptureStore:
    def __init__(self) -> None:
        self.metric_names: list[str] = []
        self.observations: list[dict[str, object]] = []

    async def observe_metric(self, session, **kwargs) -> None:
        del session
        self.metric_names.append(kwargs["metric_name"])
        self.observations.append(dict(kwargs))


def _deployment(identity: str) -> DeploymentRevision:
    return DeploymentRevision(
        deployment_revision_id=identity,
        git_commit="abc+dirty.123",
        schema_revision="20260927_0025",
        source_inventory_hash="a" * 64,
        vocabulary_revision="enrichment-v1",
        policy_revision="policy-v1",
        capability_registry_revision="unbound",
        skill_registry_revision="seed-skills:test",
        model_provider_revision="unconfigured",
        configuration_digest="b" * 64,
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


class _DecisionProvider:
    name = "fixture-live-qa"
    version = "v1"

    def __init__(self, response: DecisionPlannerResponse) -> None:
        self.response = response
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is DecisionPlannerResponse
        self.requests.append(request)
        return self.response


def _state(*, current_decision: dict[str, JsonValue] | None = None) -> InvestigationState:
    return InvestigationState(
        case_id="product-case-1",
        case_revision=5,
        goal="Determine whether the deployment is affected",
        targets=["vulnerability:CVE-2026-0001"],
        confirmed=[
            InvestigationStateItem(
                proposition="affected:true",
                target_ref="vulnerability:CVE-2026-0001",
                evidence_refs=["evidence:nvd-1"],
                writer="M3",
                reason_code="structured_fact",
                updated_revision=4,
            )
        ],
        updated_at=datetime(2026, 9, 28, tzinfo=UTC),
        current_decision=current_decision,
    )


def _decision() -> DecisionResult:
    return DecisionResult(
        decision_id="decision:abc",
        case_id="product-case-1",
        case_revision=4,
        conclusions=[
            DecisionConclusion(
                statement="affected:true",
                type=ConclusionType.FACT,
                evidence_refs=["evidence:nvd-1"],
            ),
            DecisionConclusion(
                statement="upgrade:recommended",
                type=ConclusionType.RECOMMENDATION,
            ),
        ],
        conflicts=["vendor-status-conflict"],
        unknowns=["exploitability:unknown"],
        assumptions=["deployment-version:1.2.3"],
        citations=[
            DecisionCitation(
                conclusion_index=0,
                evidence_ref="evidence:nvd-1",
                source_ref="source:nvd-cves-2:CVE-2026-0001",
            )
        ],
        stop_reason="answer_supported",
        model_prompt_revision="decision-model-v1",
    )


def test_project_decision_to_qa_prediction_uses_m4_support_and_omits_recommendation() -> None:
    decision = _decision()
    state = _state(current_decision=decision.model_dump(mode="json"))
    prediction = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
        relation_paths=[
            ["deployment:1", "affected-by", "vulnerability:CVE-2026-0001"]
        ],
        interactive_latency_seconds=0.42,
    )
    assert prediction.case_id == "qa-affected-1"
    assert prediction.conclusion_facts == ["affected:true"]
    assert prediction.unknowns == ["exploitability:unknown"]
    assert prediction.conflicts == ["vendor-status-conflict"]
    assert prediction.assumptions == ["deployment-version:1.2.3"]
    assert prediction.citations[0].supports is True
    assert prediction.relation_paths == [
        ["deployment:1", "affected-by", "vulnerability:CVE-2026-0001"]
    ]
    assert "case:product-case-1" in prediction.execution_refs
    assert "decision:abc" in prediction.execution_refs


def test_project_decision_to_qa_prediction_requires_adjudication_for_paraphrase() -> None:
    decision = _decision().model_copy(deep=True)
    decision.conclusions[0].statement = "The deployment is affected."
    state = _state(current_decision=decision.model_dump(mode="json"))
    without_adjudication = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
    )
    assert without_adjudication.citations[0].supports is False
    with_adjudication = evaluation_runtime.project_decision_to_qa_prediction(
        benchmark_case_id="qa-affected-1",
        decision=decision,
        state=state,
        citation_support={(0, "evidence:nvd-1"): True},
    )
    assert with_adjudication.citations[0].supports is True


def test_project_decision_to_qa_prediction_rejects_stale_adjudication() -> None:
    decision = _decision()
    state = _state(current_decision=decision.model_dump(mode="json"))
    with pytest.raises(ValueError, match="does not match decision citation"):
        evaluation_runtime.project_decision_to_qa_prediction(
            benchmark_case_id="qa-affected-1",
            decision=decision,
            state=state,
            citation_support={(1, "evidence:missing"): True},
        )


def test_project_continuation_state_to_qa_prediction_preserves_gap_state() -> None:
    state = _state()
    state.unknowns = [
        InvestigationStateItem(
            proposition="exploitability:unknown",
            target_ref="vulnerability:CVE-2026-0001",
            evidence_refs=[],
            writer="M6",
            reason_code="insufficient_evidence",
            updated_revision=5,
        )
    ]
    state.conflicts = [
        InvestigationStateItem(
            proposition="vendor-status-conflict",
            target_ref="vulnerability:CVE-2026-0001",
            evidence_refs=["evidence:nvd-1"],
            writer="M4",
            reason_code="source_conflict",
            updated_revision=5,
        )
    ]
    prediction = evaluation_runtime.project_continuation_state_to_qa_prediction(
        benchmark_case_id="qa-continue-1",
        state=state,
        evidence_need_refs=["evidence-need:need-1"],
    )
    assert prediction.conclusion_facts == []
    assert prediction.completion_status == "continuation_requested"
    assert prediction.unknowns == ["exploitability:unknown"]
    assert prediction.conflicts == ["vendor-status-conflict"]
    assert "evidence-need:need-1" in prediction.execution_refs


@pytest.mark.asyncio
async def test_qa_recorder_owns_session_trace_metrics() -> None:
    store = _MetricCaptureStore()
    recorder = evaluation_runtime.QABenchmarkRecorder(store)  # type: ignore[arg-type]
    await recorder.record_session_trace_score(
        None,  # type: ignore[arg-type]
        case_run_id="case-run:session",
        context_chain_correctness=1.0,
        target_carry_correctness=1.0,
        retrieval_overlap_rate=0.5,
        retrieval_invocation_coverage=1.0,
        retrieval_reuse_rate=1.0,
        subject_ref="qa-session:test",
    )
    assert store.metric_names == [
        "m6.session_context_chain_correctness",
        "m6.session_target_carry_correctness",
        "m6.session_retrieval_overlap_rate",
        "m6.session_retrieval_invocation_coverage",
        "m6.session_retrieval_reuse_rate",
    ]


@pytest.mark.asyncio
async def test_investigation_completion_trace_uses_m4_decision_event_time() -> None:
    engine, factory = await _database()
    created_at = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
    decision_at = created_at + timedelta(minutes=5)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: created_at).create(
                session,
                task_signature="long-investigation-test",
                target_object_ids=[],
                goal="Reach a final decision",
                initial_knowledge_revision=None,
            )
            state_service = InvestigationStateService(now=lambda: created_at + timedelta(minutes=1))
            opened = await state_service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id="long-investigation-need",
                proposition_or_question="What evidence closes the case?",
                purpose="benchmark_long_investigation",
                target_objects=[],
            )
            decision = DecisionResult(
                decision_id="decision:long-investigation",
                case_id=case.case_id,
                case_revision=opened.state.case_revision,
                answer_payload={"status": "complete"},
                stop_reason="evidence_sufficient",
                model_prompt_revision="decision-model-test",
            )
            await InvestigationStateService(now=lambda: decision_at).commit_decision(
                session,
                DecisionCommit(
                    decision_id=decision.decision_id,
                    case_id=case.case_id,
                    base_case_revision=decision.case_revision,
                    decision=decision.model_dump(mode="json"),
                ),
            )
            session.add(
                TaskRunModel(
                    run_id="long-investigation-run",
                    task_contract_version_id="contract-version:test",
                    task_contract_id="contract:test",
                    task_contract_revision=1,
                    context_manifest_version_id="context-version:test",
                    context_id="context:test",
                    context_revision=1,
                    case_id=case.case_id,
                    parent_run_id=None,
                    role_id="InvestigationRole",
                    role_version="1",
                    status="completed",
                    base_context_revision=1,
                    execution_envelope_ref="execution:test",
                    result_ref="investigation-result:test",
                    stop_reason="evidence_sufficient",
                    created_at=created_at + timedelta(minutes=1),
                    updated_at=created_at + timedelta(minutes=4),
                    finished_at=created_at + timedelta(minutes=4),
                )
            )

        async with factory() as session:
            trace = await evaluation_runtime.load_investigation_completion_trace(
                session,
                case.case_id,
            )
        assert trace.final_decision_present is True
        assert trace.final_decision_ref == "decision:long-investigation"
        assert trace.final_decision_case_revision == 1
        assert trace.final_decision_event_revision == 2
        assert trace.final_decision_at == decision_at
        assert trace.time_to_final_decision_seconds == 300.0
        assert trace.investigation_episode_count == 1
        assert trace.terminal_episode_count == 1
        assert trace.active_episode_count == 0
        assert trace.open_evidence_need_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_completion_trace_without_decision_has_no_latency() -> None:
    engine, factory = await _database()
    created_at = datetime(2026, 9, 30, 11, 0, tzinfo=UTC)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: created_at).create(
                session,
                task_signature="long-investigation-open",
                target_object_ids=[],
                goal="Still investigating",
                initial_knowledge_revision=None,
            )
        async with factory() as session:
            trace = await evaluation_runtime.load_investigation_completion_trace(
                session,
                case.case_id,
            )
        assert trace.final_decision_present is False
        assert trace.final_decision_at is None
        assert trace.time_to_final_decision_seconds is None
        assert trace.investigation_episode_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_recorder_separates_success_latency_and_diagnostics() -> None:
    store = _MetricCaptureStore()
    recorder = evaluation_runtime.InvestigationBenchmarkRecorder(store)  # type: ignore[arg-type]
    trace = evaluation_runtime.InvestigationCompletionTrace(
        case_id="case:long",
        case_status="active",
        case_revision=4,
        case_created_at=datetime(2026, 9, 30, 10, 0, tzinfo=UTC),
        final_decision_ref="decision:long",
        final_decision_case_revision=3,
        final_decision_event_revision=4,
        final_decision_at=datetime(2026, 9, 30, 10, 2, tzinfo=UTC),
        time_to_final_decision_seconds=120.0,
        investigation_episode_count=2,
        terminal_episode_count=2,
        active_episode_count=0,
        open_evidence_need_count=0,
    )
    await recorder.record_completion_trace(
        None,  # type: ignore[arg-type]
        case_run_id="case-run:long",
        trace=trace,
        subject_ref="case:long",
    )
    assert store.metric_names == [
        "agent.task_success",
        "m6.investigation_final_decision_completion",
        "m6.investigation_role_episode_count",
        "m6.investigation_open_need_count_at_measurement",
        "m6.investigation_time_to_final_decision_seconds",
    ]
    assert store.observations[0]["value"] == 1.0
    assert store.observations[-1]["value"] == 120.0

    late_store = _MetricCaptureStore()
    late_recorder = evaluation_runtime.InvestigationBenchmarkRecorder(
        late_store  # type: ignore[arg-type]
    )
    late_trace = trace.model_copy(
        update={
            "final_decision_at": datetime(2026, 9, 30, 10, 4, tzinfo=UTC),
            "time_to_final_decision_seconds": 240.0,
        }
    )
    await late_recorder.record_completion_trace(
        None,  # type: ignore[arg-type]
        case_run_id="case-run:late",
        trace=late_trace,
        subject_ref="case:late",
        decision_deadline=datetime(2026, 9, 30, 10, 3, tzinfo=UTC),
    )
    assert late_store.observations[0]["metric_name"] == "agent.task_success"
    assert late_store.observations[0]["value"] == 0.0
    assert late_store.observations[1]["metric_name"] == (
        "m6.investigation_final_decision_completion"
    )
    assert late_store.observations[1]["value"] == 1.0
    assert late_store.observations[-1]["value"] == 240.0

    no_decision_store = _MetricCaptureStore()
    no_decision_recorder = evaluation_runtime.InvestigationBenchmarkRecorder(
        no_decision_store  # type: ignore[arg-type]
    )
    await no_decision_recorder.record_completion_trace(
        None,  # type: ignore[arg-type]
        case_run_id="case-run:open",
        trace=trace.model_copy(
            update={
                "final_decision_ref": None,
                "final_decision_case_revision": None,
                "final_decision_event_revision": None,
                "final_decision_at": None,
                "time_to_final_decision_seconds": None,
            }
        ),
        subject_ref="case:open",
    )
    assert "m6.investigation_time_to_final_decision_seconds" not in (
        no_decision_store.metric_names
    )
    assert no_decision_store.observations[0]["value"] == 0.0


@pytest.mark.asyncio
async def test_structured_qa_gold_absence_check_fails_when_gap_is_filled() -> None:
    engine, factory = await _database()
    now = datetime(2026, 9, 29, tzinfo=UTC)
    try:
        async with factory() as session, session.begin():
            session.add(
                SourceModel(
                    source_id="cve-program-test",
                    adapter_type="fixture",
                    source_class="vulnerability_database",
                    authority_scope=["vulnerability"],
                    source_role="primary",
                    source_family="cve-program",
                    access_mode="fixture",
                    update_semantics="mutable",
                    discovery_method={},
                    time_semantics={},
                    identity_semantics={},
                    rate_limit_policy={},
                    access_rights={},
                    retention_mode="durable",
                    schedule_policy={},
                    schema_version="1",
                    definition_hash="fixture-source",
                    updated_at=now,
                )
            )
            observation = ObservationModel(
                observation_id="qa-absence-observation",
                source_id="cve-program-test",
                acquisition_run_id=None,
                acquisition_trigger="replay",
                external_object_id="CVE-2026-90909",
                external_revision="r1",
                canonical_url=None,
                published_at=now,
                updated_at=now,
                observed_at=now,
                content_hash="qa-absence-observation-hash",
                request_metadata={},
                request_metadata_captured=False,
                idempotency_key="qa-absence-observation-key",
                created_at=now,
            )
            session.add(observation)
            revision = KnowledgeRevisionModel(
                cause_observation_id=observation.observation_id,
                committed_at=now,
            )
            session.add(revision)
            await session.flush()
            subject = ObjectModel(
                object_id="qa-absence-object",
                object_type="Vulnerability",
                canonical_key="cve:CVE-2026-90909",
                properties={},
                created_revision=revision.revision,
            )
            session.add(subject)
            status = ClaimModel(
                claim_id="qa-absence-status",
                subject_id=subject.object_id,
                predicate="status",
                value="PUBLISHED",
                qualifier={
                    "source_id": "cve-program-test",
                    "vocabulary_scope": "source_specific",
                },
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=revision.revision,
            )
            session.add(status)
            session.add(
                EvidenceLinkModel(
                    evidence_link_id="qa-absence-evidence",
                    target_kind="claim",
                    target_id=status.claim_id,
                    observation_id=observation.observation_id,
                    artifact_id=None,
                    locator={"path": "$.state"},
                    locator_hash="qa-absence-locator",
                )
            )

        gold = QAGold(
            case_id="qa-absence",
            completion_expectation="continuation_requested",
        )
        async with factory() as session:
            await evaluation_runtime.validate_structured_qa_gold_provenance(
                session,
                gold=gold,
                evidence_refs=["evidence:qa-absence-evidence"],
                source_ids=["cve-program-test"],
                knowledge_revision=1,
                absence_checks=[("cve:CVE-2026-90909", "cvss_score")],
            )

        async with factory() as session, session.begin():
            session.add(
                ClaimModel(
                    claim_id="qa-absence-cvss",
                    subject_id="qa-absence-object",
                    predicate="cvss_score",
                    value=9.0,
                    qualifier={},
                    origin="source_asserted",
                    lifecycle="accepted",
                    created_revision=1,
                )
            )

        async with factory() as session:
            with pytest.raises(ValueError, match="absence check is false"):
                await evaluation_runtime.validate_structured_qa_gold_provenance(
                    session,
                    gold=gold,
                    evidence_refs=["evidence:qa-absence-evidence"],
                    source_ids=["cve-program-test"],
                    knowledge_revision=1,
                    absence_checks=[("cve:CVE-2026-90909", "cvss_score")],
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_product_case_qa_prediction_runs_gate_and_rolls_back_case_mutation() -> None:
    engine, factory = await _database()
    state_service = InvestigationStateService()
    try:
        async with factory() as session, session.begin():
            case = await CaseService().create(
                session,
                task_signature="qa-live-evaluation",
                target_object_ids=[],
                goal="Answer only from available evidence.",
                initial_knowledge_revision=0,
            )

        provider = _DecisionProvider(
            DecisionPlannerResponse(
                action=FinalDecisionProposal(
                    unknowns=["No evidence-backed conclusion is available."],
                    answer_payload={"status": "partial"},
                    stop_reason="insufficient_evidence",
                )
            )
        )
        prediction = await evaluation_runtime.execute_product_case_qa_prediction(
            factory,
            benchmark_case_id="qa-live-1",
            product_case_id=case.case_id,
            provider=provider,
        )

        assert prediction.case_id == "qa-live-1"
        assert prediction.completion_status == "answered"
        assert prediction.unknowns == ["No evidence-backed conclusion is available."]
        assert prediction.interactive_latency_seconds is not None
        assert prediction.interactive_latency_seconds >= 0
        assert f"case:{case.case_id}" in prediction.execution_refs
        assert len(provider.requests) == 1

        async with factory() as session:
            persisted = await state_service.get_state(session, case.case_id)
            assert persisted.case_revision == 0
            assert persisted.current_decision is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_product_question_qa_prediction_preserves_runtime_provenance() -> None:
    engine, factory = await _database()
    raw_provider = _DecisionProvider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                unknowns=["No evidence-backed conclusion is available."],
                answer_payload={"status": "partial"},
                stop_reason="insufficient_evidence",
            )
        )
    )
    provider = RecordedModelProvider(factory, raw_provider)
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=datetime.now(UTC))
            session.add(revision)
            await session.flush()
            session.add(
                ObjectModel(
                    object_id="qa-product-question-object",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-71717",
                    properties={"display_name": "CVE-2026-71717"},
                    created_revision=revision.revision,
                )
            )
            session.add(
                ExternalIdentifierModel(
                    external_identifier_id="qa-product-question-cve-id",
                    namespace="cve",
                    value="CVE-2026-71717",
                    object_id="qa-product-question-object",
                )
            )
        prediction = await evaluation_runtime.execute_product_question_qa_prediction(
            factory,
            settings=Settings(environment="test"),
            benchmark_case_id="qa-product-question-live-1",
            request_id="benchmark:run-1:qa-product-question-live-1",
            provider=provider,
            question="What can the current evidence establish?",
            cve_id="CVE-2026-71717",
            task_kind=TaskKind.LOOKUP,
            expected_knowledge_revision=1,
        )

        assert prediction.case_id == "qa-product-question-live-1"
        assert prediction.completion_status == "answered"
        assert prediction.unknowns == ["No evidence-backed conclusion is available."]
        assert prediction.interactive_latency_seconds is not None
        assert prediction.interactive_latency_seconds >= 0
        assert any(ref.startswith("model-request:") for ref in prediction.execution_refs)
        assert any(ref.startswith("task-run:") for ref in prediction.execution_refs)
        assert any(ref.startswith("execution:") for ref in prediction.execution_refs)
        assert any(ref.startswith("budget:") for ref in prediction.execution_refs)
        assert "product-request:benchmark:run-1:qa-product-question-live-1" in (
            prediction.execution_refs
        )
        assert len(raw_provider.requests) == 1
        metadata = raw_provider.requests[0].metadata
        assert metadata["product_request_id"] == "benchmark:run-1:qa-product-question-live-1"
        assert metadata["case_id"] is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_product_question_qa_prediction_rejects_world_drift() -> None:
    engine, factory = await _database()
    raw_provider = _DecisionProvider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                answer_payload={"status": "partial"},
                stop_reason="insufficient_evidence",
            )
        )
    )
    provider = RecordedModelProvider(factory, raw_provider)
    try:
        with pytest.raises(ValueError, match="drifted before execution"):
            await evaluation_runtime.execute_product_question_qa_prediction(
                factory,
                settings=Settings(environment="test"),
                benchmark_case_id="qa-world-drift",
                request_id="benchmark:run-1:qa-world-drift",
                provider=provider,
                question="What is known?",
                task_kind=TaskKind.RETRIEVE,
                expected_knowledge_revision=99,
            )
        assert raw_provider.requests == []
    finally:
        await engine.dispose()


def test_validated_product_decision_fact_support_is_inherited_from_m6_invariant() -> None:
    prediction = evaluation_runtime.project_validated_decision_to_qa_prediction(
        benchmark_case_id="qa-validated-1",
        decision=_decision(),
    )
    assert prediction.conclusion_facts == ["affected:true"]
    assert prediction.citations[0].supports is True


def test_validated_product_decision_inference_support_requires_adjudication() -> None:
    decision = _decision().model_copy(deep=True)
    decision.conclusions[0].type = ConclusionType.INFERENCE
    without_adjudication = evaluation_runtime.project_validated_decision_to_qa_prediction(
        benchmark_case_id="qa-validated-inference-1",
        decision=decision,
    )
    assert without_adjudication.citations[0].supports is False
    adjudicated = evaluation_runtime.project_validated_decision_to_qa_prediction(
        benchmark_case_id="qa-validated-inference-1",
        decision=decision,
        citation_support={(0, "evidence:nvd-1"): True},
    )
    assert adjudicated.citations[0].supports is True


@pytest.mark.asyncio
async def test_runtime_relation_refs_derive_actual_two_hop_path() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=datetime.now(UTC))
            session.add(revision)
            await session.flush()
            objects = [
                ObjectModel(
                    object_id="path-vuln",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-48746",
                    properties={},
                    created_revision=revision.revision,
                ),
                ObjectModel(
                    object_id="path-pr",
                    object_type="PullRequest",
                    canonical_key="github:vllm-project/vllm:pull:43426",
                    properties={},
                    created_revision=revision.revision,
                ),
                ObjectModel(
                    object_id="path-commit",
                    object_type="Commit",
                    canonical_key="git:commit:2b94d1c0caf69d4108d720986f4e792960b02cf7",
                    properties={},
                    created_revision=revision.revision,
                ),
            ]
            session.add_all(objects)
            session.add_all(
                [
                    RelationModel(
                        relation_id="path-reference",
                        source_object_id="path-vuln",
                        relation_type="references-development-object",
                        target_object_id="path-pr",
                        qualifier={},
                        origin="deterministic_derived",
                        lifecycle="accepted",
                        created_revision=revision.revision,
                    ),
                    RelationModel(
                        relation_id="path-merged",
                        source_object_id="path-pr",
                        relation_type="merged-as",
                        target_object_id="path-commit",
                        qualifier={},
                        origin="source_asserted",
                        lifecycle="accepted",
                        created_revision=revision.revision,
                    ),
                ]
            )

        async with factory() as session:
            paths = await evaluation_runtime._relation_paths_for_refs(
                session,
                ["relation:path-reference", "relation:path-merged"],
            )
        assert paths == [
            [
                "cve:CVE-2026-48746",
                "references-development-object",
                "github:vllm-project/vllm:pull:43426",
                "merged-as",
                "git:commit:2b94d1c0caf69d4108d720986f4e792960b02cf7",
            ]
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pinned_deployment_fails_closed_when_current_coordinate_drifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    drifted = _deployment("deployment:drifted")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return drifted

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            with pytest.raises(RuntimeError, match="no longer matches"):
                await evaluation_runtime.ensure_benchmark_deployment_revision(
                    session,
                    Settings(),
                    deployment_revision_id=pinned.deployment_revision_id,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pinned_deployment_accepts_same_current_coordinate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return pinned

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            resolved = await evaluation_runtime.ensure_benchmark_deployment_revision(
                session,
                Settings(),
                deployment_revision_id=pinned.deployment_revision_id,
            )
            assert resolved == pinned.deployment_revision_id
    finally:
        await engine.dispose()
