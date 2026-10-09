from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.errors import LifecycleConflictError, PermissionDeniedError
from apps.application.queries.agents import get_agent_task_detail
from apps.application.queries.decisions import DecisionQueries
from apps.application.question_facts import render_relation_fact
from apps.application.question_intent import (
    QueryIntent,
    infer_question_route,
    lexical_queries,
    needs_semantic_query,
    unbound_target_message,
)
from apps.application.question_sessions import QuestionSessionModel, QuestionSessionTurnModel
from apps.evaluation_runtime import load_product_question_session_trace
from apps.runtime_models import register_runtime_models
from packages.intelligence.retrieval.contracts import CandidateKind, RetrievedCandidate
from packages.intelligence.retrieval.operators import LexicalRetrievalOperator
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    ExternalIdentifierModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import EvidenceNeedModel, InvestigationCaseModel
from packages.reasoning.decision import (
    ConclusionType,
    DecisionConclusion,
    DecisionReportParagraph,
)
from packages.reasoning.model import (
    ContinuationProposal,
    DecisionPlannerResponse,
    FinalDecisionProposal,
)
from packages.runtime.model.service import RecordedModelProvider
from packages.runtime.retrieval.storage import RetrievalInvocationModel
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.models import TaskKind, TaskRunStatus
from packages.task_runtime.storage.models import ContextManifestVersionModel, TaskRunModel
from packages.task_runtime.storage.service import transition_task_run

NOW = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
CVE = "CVE-2026-51515"
OBJECT_ID = "question-vuln-object"
CLAIM_ID = "question-cvss-claim"
EVIDENCE_ID = "question-cvss-evidence"
RELATION_ID = "question-applicability-relation"
RELATION_EVIDENCE_ID = "question-applicability-evidence"
PRODUCT_ID = "question-product-object"
DOCUMENT_ID = "question-document-object"
PROPOSITION = f"cve:{CVE} cvss_score = 9.8"
RELATION_PROPOSITION = render_relation_fact(
    f"cve:{CVE}",
    "applicability-status",
    "product:fixture:test-product",
    qualifier={
        "state": "fixed",
        "source_semantics": "csaf_vex",
        "csaf_status": "fixed",
        "scope": {"kind": "csaf_product_status", "product_id": "test-product:1.2.3"},
        "product_context": {
            "full_product_id": "test-product:1.2.3",
            "full_product_name": "test-product 1.2.3 as a component of Test Platform",
            "component": {
                "product_id": "test-product:1.2.3",
                "name": "test-product 1.2.3",
            },
            "platform": {"product_id": "test-platform", "name": "Test Platform"},
        },
    },
    target_properties={
        "identity_scheme": "csaf_product_id",
        "csaf_product_id": "test-product:1.2.3",
    },
)


class _Provider:
    name = "fixture-question"
    version = "v1"

    def __init__(self, response: DecisionPlannerResponse) -> None:
        self.response = response
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is DecisionPlannerResponse
        self.requests.append(request)
        return self.response


class _FailingProvider:
    name = "fixture-question-failing"
    version = "v1"

    async def generate_structured(self, request, response_model):
        raise RuntimeError("provider failed")


class _FixtureRetrieval(LexicalRetrievalOperator):
    async def search(
        self,
        session,
        *,
        query: str,
        limit: int = 20,
        source_ids: Sequence[str] | None = None,
    ) -> list[RetrievedCandidate]:
        del session, query, limit, source_ids
        return [
            RetrievedCandidate(
                candidate_id="chunk:question-doc-chunk",
                candidate_kind=CandidateKind.DOCUMENT_CHUNK,
                object_id=DOCUMENT_ID,
                document_chunk_id="question-doc-chunk",
                source_id="vendor-test",
                revision="document-r1",
                locator={"section": "fix"},
                payload={
                    "canonical_url": "https://vendor.example/research-note",
                    "title": "Research note",
                    "text": "The current note does not establish the requested relation.",
                },
            )
        ]


class _ReusableFixtureRetrieval(_FixtureRetrieval):
    def __init__(self) -> None:
        self.search_calls = 0
        self.replay_calls = 0

    async def search(
        self,
        session,
        *,
        query: str,
        limit: int = 20,
        source_ids: Sequence[str] | None = None,
    ) -> list[RetrievedCandidate]:
        self.search_calls += 1
        return await super().search(
            session,
            query=query,
            limit=limit,
            source_ids=source_ids,
        )

    async def by_chunk_refs(
        self,
        session,
        *,
        refs: Sequence[str],
    ) -> list[RetrievedCandidate]:
        self.replay_calls += 1
        assert refs == ["document-chunk:question-doc-chunk@document-r1"]
        return await _FixtureRetrieval.search(
            self,
            session,
            query="replayed",
            limit=len(refs),
        )


async def _factory():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add(
            SourceModel(
                source_id="vendor-test",
                adapter_type="fixture",
                source_class="vendor",
                authority_scope=["vulnerability"],
                source_role="primary",
                source_family="vendor-test",
                access_mode="fixture",
                update_semantics="immutable",
                discovery_method={},
                time_semantics={},
                identity_semantics={},
                rate_limit_policy={},
                access_rights={},
                retention_mode="durable",
                schedule_policy={},
                schema_version="1",
                definition_hash="source-hash",
                updated_at=NOW,
            )
        )
        observation = ObservationModel(
            observation_id="question-observation",
            source_id="vendor-test",
            acquisition_run_id=None,
            acquisition_trigger="replay",
            external_object_id=CVE,
            external_revision="vendor-r1",
            canonical_url="https://vendor.example/advisory",
            published_at=NOW,
            updated_at=NOW,
            observed_at=NOW,
            content_hash="observation-hash",
            request_metadata={},
            request_metadata_captured=False,
            idempotency_key="question-observation-key",
            created_at=NOW,
        )
        session.add(observation)
        revision = KnowledgeRevisionModel(
            cause_observation_id=observation.observation_id,
            committed_at=NOW,
        )
        session.add(revision)
        await session.flush()
        session.add(
            ObjectModel(
                object_id=DOCUMENT_ID,
                object_type="Document",
                canonical_key="document:fixture:research-note",
                properties={"title": "Research note"},
                created_revision=revision.revision,
            )
        )
        session.add(
            ObjectModel(
                object_id=OBJECT_ID,
                object_type="Vulnerability",
                canonical_key=f"cve:{CVE}",
                properties={"display_name": CVE},
                created_revision=revision.revision,
            )
        )
        session.add(
            ExternalIdentifierModel(
                external_identifier_id="question-cve-id",
                namespace="cve",
                value=CVE,
                object_id=OBJECT_ID,
            )
        )
        session.add(
            ClaimModel(
                claim_id=CLAIM_ID,
                subject_id=OBJECT_ID,
                predicate="cvss_score",
                value=9.8,
                qualifier={},
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=revision.revision,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id=EVIDENCE_ID,
                target_kind="claim",
                target_id=CLAIM_ID,
                observation_id=observation.observation_id,
                artifact_id=None,
                locator={"field": "cvss_score"},
                locator_hash="locator-hash",
            )
        )
        session.add(
            ObjectModel(
                object_id=PRODUCT_ID,
                object_type="Product",
                canonical_key="product:fixture:test-product",
                properties={
                    "identity_scheme": "csaf_product_id",
                    "csaf_product_id": "test-product:1.2.3",
                },
                created_revision=revision.revision,
            )
        )
        session.add(
            RelationModel(
                relation_id=RELATION_ID,
                source_object_id=OBJECT_ID,
                relation_type="applicability-status",
                target_object_id=PRODUCT_ID,
                qualifier={
                    "state": "fixed",
                    "source_semantics": "csaf_vex",
                    "csaf_status": "fixed",
                    "scope": {
                        "kind": "csaf_product_status",
                        "product_id": "test-product:1.2.3",
                    },
                    "product_context": {
                        "full_product_id": "test-product:1.2.3",
                        "full_product_name": (
                            "test-product 1.2.3 as a component of Test Platform"
                        ),
                        "component": {
                            "product_id": "test-product:1.2.3",
                            "name": "test-product 1.2.3",
                        },
                        "platform": {
                            "product_id": "test-platform",
                            "name": "Test Platform",
                        },
                    },
                },
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=revision.revision,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id=RELATION_EVIDENCE_ID,
                target_kind="relation",
                target_id=RELATION_ID,
                observation_id=observation.observation_id,
                artifact_id=None,
                locator={"field": "product_status.fixed[0]"},
                locator_hash="relation-locator-hash",
            )
        )
    return engine, factory


def _use_case(
    provider,
    *,
    retrieval: LexicalRetrievalOperator | None = None,
    query_planner_provider=None,
) -> AskQuestionUseCase:
    settings = get_settings()
    return AskQuestionUseCase(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
        model_provider=provider,
        query_planner_provider=query_planner_provider,
        retrieval=retrieval,
    )


async def _complete_investigation_episode(factory, case_id: str) -> None:
    settings = get_settings()
    async with factory() as session, session.begin():
        run = await session.scalar(
            select(TaskRunModel).where(
                TaskRunModel.case_id == case_id,
                TaskRunModel.role_id == "InvestigationRole",
            )
        )
        assert run is not None and run.status == TaskRunStatus.QUEUED.value
        await transition_task_run(
            session,
            run_id=run.run_id,
            target=TaskRunStatus.RUNNING,
            payload_ref=f"test:{run.run_id}:running",
            idempotency_key=f"test-running:{run.run_id}",
            stream_name=settings.task_event_stream_name,
            producer="test",
        )
        await transition_task_run(
            session,
            run_id=run.run_id,
            target=TaskRunStatus.COMPLETED,
            payload_ref=f"test:{run.run_id}:completed",
            idempotency_key=f"test-completed:{run.run_id}",
            stream_name=settings.task_event_stream_name,
            producer="test",
            stop_reason="test_episode_complete",
        )


async def _confirm_case_fact(factory, case_id: str) -> int:
    service = InvestigationStateService()
    async with factory() as session, session.begin():
        state = await service.get_state(session, case_id)
        applied = await service.apply_patch(
            session,
            StatePatch(
                patch_id=f"case-read-confirm:{case_id}",
                case_id=case_id,
                base_case_revision=state.case_revision,
                producer="test:case-read",
                operations=[
                    StatePatchOperation(
                        proposition=PROPOSITION,
                        target_ref=f"object:{OBJECT_ID}",
                        proposed_state=ProposedState.CONFIRMED,
                        evidence_refs=[EVIDENCE_ID],
                    )
                ],
            ),
        )
        return applied.state.case_revision


@pytest.mark.asyncio
async def test_lookup_question_runs_read_only_decision_without_durable_case() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"cvss_score": 9.8},
                report_paragraphs=[
                    DecisionReportParagraph(
                        text=f"The confirmed CVSS score for {CVE} is 9.8.",
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            result = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-direct-1",
                    question=f"What is the CVSS score for {CVE}?",
                    cve_id=CVE,
                    task_kind=TaskKind.LOOKUP,
                ),
            )
            assert result.mode == "completed"
            assert result.execution_profile == "DIRECT"
            assert result.decision is not None
            assert result.decision.answer == {"cvss_score": 9.8}
            assert result.decision.citations[0].evidence_ref == f"evidence:{EVIDENCE_ID}"
            assert result.decision.citations[0].locator == {"field": "cvss_score"}
            assert result.decision.report_paragraphs[0].text.endswith("9.8.")
            reread = await DecisionQueries().get(session, result.decision.decision_id)
            assert reread.decision_id == result.decision.decision_id
            assert reread.answer == {"cvss_score": 9.8}
            assert reread.report_paragraphs[0].evidence_refs == [f"evidence:{EVIDENCE_ID}"]

        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 0
            run = await session.scalar(select(TaskRunModel))
            assert run is not None
            assert run.role_id == "DecisionRole"
            assert run.status == "completed"
            execution = await session.scalar(select(ExecutionRunModel))
            assert execution is not None and execution.status == "completed"
        state_payload = provider.requests[0].data["investigation_state"]
        assert PROPOSITION in str(state_payload)
        metadata = provider.requests[0].metadata
        owner_ref = metadata["request_owner_ref"]
        assert isinstance(owner_ref, str)
        assert owner_ref.startswith("task-run:")
        assert metadata["task_run_id"]
        assert metadata["execution_id"]
        assert metadata["case_id"] is None
        assert metadata["product_request_id"] == "question-direct-1"
        assert metadata["prompt_revision"] == "decision-model-v4"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_rejects_unsupported_model_fact_with_retryable_error() -> None:
    from apps.application.errors import DecisionValidationError

    engine, factory = await _factory()
    provider = _Provider(DecisionPlannerResponse(action=FinalDecisionProposal(
        conclusions=[DecisionConclusion(
            statement="An unsupported reformulation of the vulnerability fact.",
            type=ConclusionType.FACT,
            evidence_refs=[f"evidence:{EVIDENCE_ID}"],
        )],
        stop_reason="evidence_sufficient",
    )))
    try:
        async with factory() as session:
            with pytest.raises(DecisionValidationError) as failure:
                await _use_case(provider).execute(session, AskQuestionCommand(
                    principal="user:test", request_id="question-invalid-decision",
                    question=f"What is the CVSS score for {CVE}?", cve_id=CVE,
                ))
            assert failure.value.retryable
            assert "evidence validation" in failure.value.detail
            failed_run_id = failure.value.context["run_id"]
        async with factory() as session:
            run = await session.scalar(select(TaskRunModel))
            assert run is not None and run.status == "failed"
            assert run.run_id == failed_run_id
            assert run.stop_reason == "question_decision_rejected"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_idempotency_replays_decision_without_second_model_call() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[DecisionConclusion(
                    statement=PROPOSITION,
                    type=ConclusionType.FACT,
                    evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                )],
                answer_payload={"cvss_score": 9.8},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            command = AskQuestionCommand(
                principal="user:test",
                request_id="question-idempotent-1",
                idempotency_key="same-question",
                question=f"What is the CVSS score for {CVE}?",
                cve_id=CVE,
                task_kind=TaskKind.LOOKUP,
            )
            first = await _use_case(provider).execute(session, command)
        async with factory() as session:
            second = await _use_case(provider).execute(
                session, command.model_copy(update={"request_id": "question-idempotent-2"})
            )
            assert second == first
            assert len(provider.requests) == 1
            assert int(await session.scalar(
                select(func.count()).select_from(TaskRunModel)
            ) or 0) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pre_context_retrieval_failure_records_attempt_without_empty_session() -> None:
    class TimedOutRetrieval(LexicalRetrievalOperator):
        async def search(
            self, session, *, query: str, limit: int = 20,
            source_ids: Sequence[str] | None = None,
        ) -> list[RetrievedCandidate]:
            raise TimeoutError("fixture retrieval timeout")

    engine, factory = await _factory()
    try:
        async with factory() as session:
            with pytest.raises(TimeoutError):
                await _use_case(_FailingProvider(), retrieval=TimedOutRetrieval()).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="pre-context-retrieval-failure",
                        idempotency_key="retryable-retrieval-failure",
                        question="Find evidence about this fix",
                        cve_id=CVE,
                        task_kind=TaskKind.RETRIEVE,
                    ),
                )
        async with factory() as session:
            attempt = await session.scalar(select(RetrievalInvocationModel))
            assert attempt is not None
            assert attempt.disposition == "failed"
            assert attempt.failure_class == "TimeoutError"
            assert attempt.result_refs == []
            assert int(await session.scalar(
                select(func.count()).select_from(QuestionSessionModel)
            ) or 0) == 0
            assert int(await session.scalar(
                select(func.count()).select_from(TaskRunModel)
            ) or 0) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retrieve_session_rejects_stale_live_case_world() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[],
                answer_payload={},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            first = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-case-retrieve-investigate",
                    question="Investigate this vulnerability.",
                    cve_id=CVE,
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                ),
            )
        assert first.investigation is not None

        async with factory() as session, session.begin():
            session.add(
                KnowledgeRevisionModel(
                    cause_processing_run_id=None,
                    cause_observation_id=None,
                    committed_at=NOW,
                )
            )

        async with factory() as session:
            with pytest.raises(
                LifecycleConflictError,
                match="must be refreshed before retrieval follow-up",
            ):
                await _use_case(provider).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="question-case-retrieve-stale",
                        session_id=first.session_id,
                        question="Retrieve more evidence for the active investigation.",
                        task_kind=TaskKind.RETRIEVE,
                    ),
                )

        assert provider.requests == []
        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(RetrievalInvocationModel))
                or 0
            ) == 0
            assert int(
                await session.scalar(select(func.count()).select_from(TaskRunModel)) or 0
            ) == 1
            assert int(
                await session.scalar(select(func.count()).select_from(QuestionSessionTurnModel))
                or 0
            ) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_case_read_continuation_keeps_same_investigation_case() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Which primary source closes the remaining gap?",
                purpose="case_read_followup_gap",
                target_objects=[OBJECT_ID],
                preferred_source_roles=["primary"],
                evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
                priority=85,
                reason="active case still has an evidence gap",
            )
        )
    )
    try:
        async with factory() as session:
            first = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-case-continuation-investigate",
                    question="Investigate this vulnerability.",
                    cve_id=CVE,
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                ),
            )
        assert first.investigation is not None
        case_id = first.investigation.case_id
        await _complete_investigation_episode(factory, case_id)

        async with factory() as session:
            second = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-case-continuation-read",
                    session_id=first.session_id,
                    question="What evidence is still missing?",
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert second.mode == "accepted"
        assert second.investigation is not None
        assert second.investigation.case_id == case_id
        assert any(
            item.question == "Which primary source closes the remaining gap?"
            and item.purpose == "case_read_followup_gap"
            and item.priority == 85
            for item in second.investigation.open_evidence_needs
        )

        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 1
            assert int(
                await session.scalar(select(func.count()).select_from(EvidenceNeedModel)) or 0
            ) == 2
            investigation_runs = list(
                await session.scalars(
                    select(TaskRunModel)
                    .where(
                        TaskRunModel.case_id == case_id,
                        TaskRunModel.role_id == "InvestigationRole",
                    )
                    .order_by(TaskRunModel.created_at)
                )
            )
            assert [item.status for item in investigation_runs] == ["completed", "queued"]
            turns = list(
                await session.scalars(
                    select(QuestionSessionTurnModel)
                    .where(QuestionSessionTurnModel.session_id == first.session_id)
                    .order_by(QuestionSessionTurnModel.turn_index)
                )
            )
            assert [turn.investigation_ref for turn in turns] == [
                f"case:{case_id}",
                f"case:{case_id}",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_session_reads_live_case_without_m4_decision_commit() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"cvss_score": 9.8},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            first = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-case-read-investigate",
                    question="Investigate this vulnerability.",
                    cve_id=CVE,
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                ),
            )
        assert first.investigation is not None
        case_id = first.investigation.case_id
        case_revision = await _confirm_case_fact(factory, case_id)

        async with factory() as session:
            second = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-case-read-lookup",
                    session_id=first.session_id,
                    question="What has this investigation confirmed so far?",
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert second.mode == "completed"
        assert second.decision is not None
        assert second.decision.answer == {"cvss_score": 9.8}
        state_payload = provider.requests[0].data["investigation_state"]
        assert isinstance(state_payload, dict)
        assert state_payload["case_id"] == case_id
        assert state_payload["goal"] == "What has this investigation confirmed so far?"
        assert PROPOSITION in str(state_payload["confirmed"])
        assert provider.requests[0].metadata["case_id"] == case_id

        async with factory() as session:
            decision_run = await session.scalar(
                select(TaskRunModel).where(
                    TaskRunModel.role_id == "DecisionRole",
                    TaskRunModel.case_id == case_id,
                )
            )
            assert decision_run is not None
            context = await session.get(
                ContextManifestVersionModel,
                decision_run.context_manifest_version_id,
            )
            assert context is not None
            assert context.manifest_json["case_ref"] == case_id
            assert context.manifest_json["investigation_state_ref"] == (
                f"case:{case_id}@{case_revision}"
            )
            assert context.manifest_json["capability_envelope_ref"] == (
                "capability:question:case-read-v1"
            )
            state = await InvestigationStateService().get_state(session, case_id)
            assert state.case_revision == case_revision
            assert state.current_decision is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_followup_rejects_concurrent_runtime_episode() -> None:
    engine, factory = await _factory()
    try:
        async with factory() as session:
            first = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-investigation-concurrent-1",
                    question="Investigate this vulnerability.",
                    cve_id=CVE,
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                ),
            )
        assert first.investigation is not None

        async with factory() as session:
            with pytest.raises(
                LifecycleConflictError,
                match="already has an active runtime episode",
            ):
                await _use_case(None).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="question-investigation-concurrent-2",
                        session_id=first.session_id,
                        question="Investigate another gap in the same case.",
                        task_kind=TaskKind.INVESTIGATE_RELATION,
                    ),
                )

        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 1
            assert int(
                await session.scalar(select(func.count()).select_from(EvidenceNeedModel)) or 0
            ) == 1
            assert int(
                await session.scalar(select(func.count()).select_from(TaskRunModel)) or 0
            ) == 1
            turns = list(
                await session.scalars(
                    select(QuestionSessionTurnModel).where(
                        QuestionSessionTurnModel.session_id == first.session_id
                    )
                )
            )
            assert len(turns) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_followup_reuses_case_after_prior_episode_finishes() -> None:
    engine, factory = await _factory()
    try:
        async with factory() as session:
            first = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-investigation-session-1",
                    question="Investigate the fix evidence for this vulnerability.",
                    cve_id=CVE,
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                ),
            )
        assert first.investigation is not None
        case_id = first.investigation.case_id
        await _complete_investigation_episode(factory, case_id)

        async with factory() as session:
            second = await _use_case(None).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-investigation-session-2",
                    session_id=first.session_id,
                    question="Now verify the remaining primary-source gap.",
                    task_kind=TaskKind.INVESTIGATE_RELATION,
                    required_source_roles=["primary"],
                    priority=75,
                ),
            )
        assert second.session_id == first.session_id
        assert second.turn_index == 2
        assert second.investigation is not None
        assert second.investigation.case_id == case_id
        assert len(second.investigation.open_evidence_needs) == 2
        assert any(
            item.question == "Now verify the remaining primary-source gap."
            and item.required_source_roles == ["primary"]
            and item.priority == 75
            for item in second.investigation.open_evidence_needs
        )

        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 1
            assert int(
                await session.scalar(select(func.count()).select_from(EvidenceNeedModel)) or 0
            ) == 2
            runs = list(
                await session.scalars(
                    select(TaskRunModel)
                    .where(TaskRunModel.case_id == case_id)
                    .order_by(TaskRunModel.created_at)
                )
            )
            assert [run.status for run in runs] == ["completed", "queued"]
            turns = list(
                await session.scalars(
                    select(QuestionSessionTurnModel)
                    .where(QuestionSessionTurnModel.session_id == first.session_id)
                    .order_by(QuestionSessionTurnModel.turn_index)
                )
            )
            assert [turn.investigation_ref for turn in turns] == [
                f"case:{case_id}",
                f"case:{case_id}",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_identical_retrieve_followup_reuses_prior_chunk_results() -> None:
    engine, factory = await _factory()
    retrieval = _ReusableFixtureRetrieval()
    response = DecisionPlannerResponse(
        action=FinalDecisionProposal(
            conclusions=[
                DecisionConclusion(
                    statement=PROPOSITION,
                    type=ConclusionType.FACT,
                    evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                )
            ],
            answer_payload={"score": 9.8},
            stop_reason="evidence_sufficient",
        )
    )
    question = f"Retrieve supporting context for the CVSS score of {CVE}."
    try:
        async with factory() as session:
            first = await _use_case(_Provider(response), retrieval=retrieval).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-reuse-1",
                    question=question,
                    cve_id=CVE,
                    task_kind=TaskKind.RETRIEVE,
                ),
            )
        async with factory() as session:
            second = await _use_case(_Provider(response), retrieval=retrieval).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-reuse-2",
                    session_id=first.session_id,
                    question=question,
                    task_kind=TaskKind.RETRIEVE,
                ),
            )

        assert first.mode == "completed" and second.mode == "completed"
        assert second.turn_index == 2
        assert retrieval.search_calls == 1
        assert retrieval.replay_calls == 1

        async with factory() as session:
            invocations = list(
                await session.scalars(
                    select(RetrievalInvocationModel).order_by(
                        RetrievalInvocationModel.product_turn_index
                    )
                )
            )
            assert [item.disposition for item in invocations] == ["executed", "reused"]
            assert invocations[1].reuse_of_invocation_id == invocations[0].invocation_id
            assert invocations[0].request_digest == invocations[1].request_digest
            assert invocations[0].result_refs == invocations[1].result_refs

            runs = list(
                await session.scalars(
                    select(TaskRunModel)
                    .where(TaskRunModel.role_id == "DecisionRole")
                    .order_by(TaskRunModel.created_at)
                )
            )
            contexts = [
                await session.get(ContextManifestVersionModel, run.context_manifest_version_id)
                for run in runs
            ]
            assert all(context is not None for context in contexts)
            assert contexts[0] is not None and contexts[1] is not None
            assert contexts[0].manifest_json["retrieval_invocation_refs"] == [
                f"retrieval-invocation:{invocations[0].invocation_id}"
            ]
            assert contexts[1].manifest_json["retrieval_invocation_refs"] == [
                f"retrieval-invocation:{invocations[1].invocation_id}"
            ]
            trace = await load_product_question_session_trace(session, first.session_id)
            assert trace.turns[0].retrieval_refs == invocations[0].result_refs
            assert trace.turns[1].retrieval_refs == invocations[1].result_refs
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_followup_question_carries_target_and_non_evidence_session_history() -> None:
    engine, factory = await _factory()
    first_provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"score": 9.8},
                stop_reason="evidence_sufficient",
            )
        )
    )
    second_provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"score": 9.8, "followup": True},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            first = await _use_case(first_provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-session-1",
                    question=f"What is the CVSS score for {CVE}?",
                    cve_id=CVE,
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert first.mode == "completed"
        assert first.turn_index == 1

        async with factory() as session:
            second = await _use_case(second_provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-session-2",
                    session_id=first.session_id,
                    question="What about that same vulnerability?",
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert second.mode == "completed"
        assert second.session_id == first.session_id
        assert second.turn_index == 2

        request = second_provider.requests[0]
        state_payload = request.data["investigation_state"]
        history_payload = request.data["session_context"]
        assert isinstance(state_payload, dict)
        assert isinstance(history_payload, list)
        assert state_payload["targets"] == [OBJECT_ID]
        assert len(history_payload) == 1
        first_turn = history_payload[0]
        assert isinstance(first_turn, dict)
        assert first_turn["user_input"] == f"What is the CVSS score for {CVE}?"
        outcome = first_turn["outcome"]
        assert isinstance(outcome, dict)
        assert outcome["answer"] == {"score": 9.8}
        assert request.metadata["product_session_id"] == first.session_id
        assert request.metadata["product_turn_index"] == 2

        async with factory() as session:
            stored_session = await session.get(QuestionSessionModel, first.session_id)
            turns = list(
                await session.scalars(
                    select(QuestionSessionTurnModel)
                    .where(QuestionSessionTurnModel.session_id == first.session_id)
                    .order_by(QuestionSessionTurnModel.turn_index)
                )
            )
            runs = list(
                await session.scalars(
                    select(TaskRunModel)
                    .where(TaskRunModel.role_id == "DecisionRole")
                    .order_by(TaskRunModel.created_at)
                )
            )
            assert stored_session is not None
            assert stored_session.principal == "user:test"
            assert [turn.turn_index for turn in turns] == [1, 2]
            assert [turn.target_object_ids for turn in turns] == [[OBJECT_ID], [OBJECT_ID]]
            assert all(turn.decision_ref is not None for turn in turns)
            assert len(runs) == 2
            first_context = await session.get(
                ContextManifestVersionModel,
                runs[0].context_manifest_version_id,
            )
            second_context = await session.get(
                ContextManifestVersionModel,
                runs[1].context_manifest_version_id,
            )
            assert first_context is not None and second_context is not None
            assert second_context.parent_context_id == first_context.context_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_session_rejects_cross_principal_followup() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"score": 9.8},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            first = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:owner",
                    request_id="question-session-owner",
                    question=f"What is the CVSS score for {CVE}?",
                    cve_id=CVE,
                ),
            )
        async with factory() as session:
            with pytest.raises(PermissionDeniedError, match="belongs to another principal"):
                await _use_case(provider).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:other",
                        request_id="question-session-other",
                        session_id=first.session_id,
                        question="Follow up on that result",
                        task_kind=TaskKind.LOOKUP,
                    ),
                )
    finally:
        await engine.dispose()


def test_chat_intent_keeps_natural_question_and_extracts_stable_identifiers() -> None:
    assert infer_question_route("你知道Huggingface事件吗", cve_id=None, object_id=None) == (
        TaskKind.RETRIEVE, None,
    )
    assert lexical_queries("你知道Huggingface事件吗") == ["你知道Huggingface事件吗", "Huggingface"]
    assert infer_question_route(f"{CVE} 影响哪个版本?", cve_id=None, object_id=None) == (
        TaskKind.RETRIEVE, CVE,
    )
    assert "多个" in unbound_target_message("这件事是什么", ambiguous=True)
    assert needs_semantic_query("比较两个事件的攻击入口")
    assert not needs_semantic_query("你知道Huggingface事件吗")


@pytest.mark.asyncio
async def test_natural_chat_falls_back_to_named_term_and_escalates_with_trace() -> None:
    class SelectiveRetrieval(_FixtureRetrieval):
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, session, *, query: str, limit: int = 20, source_ids=None):
            self.queries.append(query)
            return []

        async def search_compact_name(self, session, *, query: str, limit: int = 20):
            self.queries.append(f"compact:{query}")
            return await super().search(session, query=query, limit=limit)

    engine, factory = await _factory()
    retrieval = SelectiveRetrieval()
    provider = _Provider(DecisionPlannerResponse(action=ContinuationProposal(
        proposition_or_question="Verify the event against a primary source",
        purpose="verify_retrieved_document",
        target_objects=[DOCUMENT_ID],
        reason="the retrieved passage needs primary confirmation",
    )))
    try:
        async with factory() as session:
            result = await _use_case(provider, retrieval=retrieval).execute(
                session,
                AskQuestionCommand(
                    principal="user:test", request_id="natural-chat-fallback-1",
                    question="你知道Huggingface事件吗",
                ),
            )
        assert result.mode == "accepted"
        assert result.investigation is not None
        assert result.investigation.target_object_ids == [DOCUMENT_ID]
        assert retrieval.queries == ["你知道Huggingface事件吗", "compact:Huggingface"]
        async with factory() as session:
            invocations = list(await session.scalars(select(RetrievalInvocationModel)))
            assert len(invocations) == 2
            turn = await session.scalar(select(QuestionSessionTurnModel))
            assert turn is not None and turn.task_kind == "retrieve"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_natural_chat_without_any_target_returns_clear_unknown() -> None:
    class NoResultsRetrieval(LexicalRetrievalOperator):
        async def search(self, session, *, query: str, limit: int = 20, source_ids=None):
            return []

        async def search_compact_name(self, session, *, query: str, limit: int = 20):
            return []

    engine, factory = await _factory()
    provider = _Provider(DecisionPlannerResponse(action=ContinuationProposal(
        proposition_or_question="Find a source for the event",
        purpose="find_missing_event",
        target_objects=[],
        reason="No bounded source is available",
    )))
    try:
        async with factory() as session:
            result = await _use_case(provider, retrieval=NoResultsRetrieval()).execute(
                session,
                AskQuestionCommand(
                    principal="user:test", request_id="natural-chat-empty-1",
                    question="你知道不存在的事件吗",
                ),
            )
        assert result.mode == "completed"
        assert result.decision is not None
        assert result.decision.answer == {"status": "insufficient_evidence"}
        assert result.decision.report_paragraphs[0].evidence_refs == []
        assert "没有找到可继续调查的对象" in result.decision.report_paragraphs[0].text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complex_chat_compiles_model_query_intent_into_audited_retrievals() -> None:
    class QueryPlanner:
        name = "fixture-query-planner"
        version = "v1"

        def __init__(self) -> None:
            self.requests: list[StructuredModelRequest] = []

        async def generate_structured(self, request, response_model):
            assert response_model is QueryIntent
            self.requests.append(request)
            return QueryIntent(
                original_text=request.data["question"],
                targets=["Hugging Face", "Bitget"],
                comparison_dimensions=["attack entry"],
                candidate_subquestions=["How did each incident begin?"],
                search_phrases=["Hugging Face Incident", "Bitget Incident"],
            )

    class RecordingRetrieval(_FixtureRetrieval):
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, session, *, query: str, limit: int = 20, source_ids=None):
            self.queries.append(query)
            return await super().search(session, query=query, limit=limit, source_ids=source_ids)

    engine, factory = await _factory()
    planner = QueryPlanner()
    retrieval = RecordingRetrieval()
    provider = _Provider(DecisionPlannerResponse(action=ContinuationProposal(
        proposition_or_question="Check the reported attack entry",
        purpose="verify_compared_incidents",
        target_objects=[DOCUMENT_ID],
        reason="the passages need primary confirmation",
    )))
    try:
        async with factory() as session:
            result = await _use_case(
                provider, retrieval=retrieval,
                query_planner_provider=RecordedModelProvider(factory, planner),
            ).execute(session, AskQuestionCommand(
                principal="user:test", request_id="complex-chat-plan-1",
                question="比较 Hugging Face 与 Bitget 事件的攻击入口",
            ))
        assert result.mode == "accepted"
        assert retrieval.queries == ["Hugging Face", "Bitget"]
        assert planner.requests[0].metadata["model_purpose"] == "product.query_intent"
        async with factory() as session:
            run = await session.scalar(
                select(TaskRunModel).where(TaskRunModel.role_id == "DecisionRole")
            )
            assert run is not None
            context = await session.get(
                ContextManifestVersionModel, run.context_manifest_version_id,
            )
            assert context is not None
            assert context.manifest_json["query_intent"]["comparison_dimensions"] == [
                "attack entry",
            ]
            assert context.manifest_json["query_intent"]["compiled_queries"] == [
                "Hugging Face", "Bitget",
            ]
            assert len(context.manifest_json["retrieval_invocation_refs"]) == 2
            assert context.manifest_json["query_intent_model_ref"].startswith("model-request:")
            detail = await get_agent_task_detail(session, run.run_id, principal="user:test")
            assert detail is not None
            assert [attempt.purpose for attempt in detail.model_attempts] == [
                "product.query_intent",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_targetless_retrieve_continuation_binds_retrieved_document_target() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Which primary source can verify the missing relation?",
                purpose="verify_retrieved_document",
                target_objects=[DOCUMENT_ID],
                preferred_source_roles=["primary"],
                evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
                priority=70,
                reason="retrieved passage is insufficient for a confirmed answer",
            )
        )
    )
    try:
        async with factory() as session:
            result = await _use_case(
                provider,
                retrieval=_FixtureRetrieval(),
            ).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-retrieve-escalate-1",
                    question="What does the research note establish about the fix?",
                    task_kind=TaskKind.RETRIEVE,
                ),
            )
        assert result.mode == "accepted"
        assert result.execution_profile == "INVESTIGATE"
        assert result.investigation is not None
        assert result.investigation.target_object_ids == [DOCUMENT_ID]

        state_payload = provider.requests[0].data["investigation_state"]
        assert isinstance(state_payload, dict)
        assert state_payload["targets"] == [DOCUMENT_ID]
        async with factory() as session:
            need = await session.get(
                EvidenceNeedModel,
                result.investigation.open_evidence_needs[0].need_id,
            )
            assert need is not None
            assert need.target_objects == [DOCUMENT_ID]
            runs = list(
                await session.scalars(select(TaskRunModel).order_by(TaskRunModel.created_at))
            )
            assert len(runs) == 2
            assert runs[0].role_id == "DecisionRole"
            assert runs[0].status == "completed"
            assert runs[1].role_id == "InvestigationRole"
            assert runs[1].status == "queued"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comparison_continuation_keeps_both_canonical_targets() -> None:
    class TwoTargetRetrieval(_FixtureRetrieval):
        async def search(self, session, *, query: str, limit: int = 20, source_ids=None):
            first = await super().search(
                session, query=query, limit=limit, source_ids=source_ids,
            )
            return [*first, RetrievedCandidate(
                candidate_id="chunk:question-second-chunk",
                candidate_kind=CandidateKind.DOCUMENT_CHUNK,
                object_id=OBJECT_ID,
                document_chunk_id="question-second-chunk",
                source_id="vendor-test",
                revision="document-r1",
                locator={"section": "comparison"},
                payload={"text": "The second target needs an independent check."},
            )]

    engine, factory = await _factory()
    provider = _Provider(DecisionPlannerResponse(action=ContinuationProposal(
        proposition_or_question="Compare both sources with primary evidence",
        purpose="compare_two_targets",
        target_objects=[DOCUMENT_ID, OBJECT_ID],
        reason="both sources need verification",
    )))
    try:
        async with factory() as session:
            result = await _use_case(provider, retrieval=TwoTargetRetrieval()).execute(
                session, AskQuestionCommand(
                    principal="user:test", request_id="comparison-two-targets-1",
                    question="Compare both reported events", task_kind=TaskKind.RETRIEVE,
                ),
            )
        assert result.mode == "accepted"
        assert result.investigation is not None
        assert result.investigation.target_object_ids == [DOCUMENT_ID, OBJECT_ID]
        async with factory() as session:
            need = await session.get(
                EvidenceNeedModel, result.investigation.open_evidence_needs[0].need_id,
            )
            assert need is not None and need.target_objects == [DOCUMENT_ID, OBJECT_ID]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_targetless_retrieve_continuation_rejects_target_escape() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Fetch another object",
                purpose="escape_attempt",
                target_objects=[OBJECT_ID],
                reason="try a target outside bounded retrieval results",
            )
        )
    )
    try:
        async with factory() as session:
            with pytest.raises(ValueError, match="target_objects escape M4 state"):
                await _use_case(provider, retrieval=_FixtureRetrieval()).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="question-retrieve-escape-1",
                        question="Find evidence about the research note",
                        task_kind=TaskKind.RETRIEVE,
                    ),
                )
        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 0
            run = await session.scalar(select(TaskRunModel))
            assert run is not None
            assert run.status == "failed"
            assert run.stop_reason == "question_reasoning_failed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_targetless_retrieve_continuation_binds_single_found_target() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Need more evidence",
                purpose="missing_target_selection",
                target_objects=[],
                reason="no durable target was selected",
            )
        )
    )
    try:
        async with factory() as session:
            result = await _use_case(provider, retrieval=_FixtureRetrieval()).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-retrieve-blocked-1",
                    question="Find more evidence about the research note",
                    task_kind=TaskKind.RETRIEVE,
                ),
            )
        assert result.mode == "accepted"
        assert result.investigation is not None
        assert result.investigation.target_object_ids == [DOCUMENT_ID]
        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 1
            run = await session.scalar(select(TaskRunModel))
            execution = await session.scalar(select(ExecutionRunModel))
            assert run is not None and run.status == "completed"
            assert execution is not None and execution.status == "completed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_expands_bounded_development_graph_to_second_hop() -> None:
    engine, factory = await _factory()
    first_relation_id = "question-dev-reference-relation"
    first_evidence_id = "question-dev-reference-evidence"
    second_relation_id = "question-merged-as-relation"
    second_evidence_id = "question-merged-as-evidence"
    pr_id = "question-pr-object"
    commit_id = "question-commit-object"
    pr_key = "github:vllm-project/vllm:pull:43426"
    commit_key = "git:commit:2b94d1c0caf69d4108d720986f4e792960b02cf7"
    first_fact = render_relation_fact(
        f"cve:{CVE}",
        "references-development-object",
        pr_key,
        qualifier={
            "reference_url": "https://github.com/vllm-project/vllm/pull/43426",
            "reference_kind": "pull_request",
        },
        target_properties={"number": 43426},
    )
    second_fact = render_relation_fact(
        pr_key,
        "merged-as",
        commit_key,
        qualifier={},
        target_properties={"sha": "2b94d1c0caf69d4108d720986f4e792960b02cf7"},
    )
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=second_fact,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{second_evidence_id}"],
                    )
                ],
                answer_payload={"merge_commit": commit_key},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session, session.begin():
            revision = int(
                await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 1
            )
            session.add_all(
                [
                    ObjectModel(
                        object_id=pr_id,
                        object_type="PullRequest",
                        canonical_key=pr_key,
                        properties={"number": 43426},
                        created_revision=revision,
                    ),
                    ObjectModel(
                        object_id=commit_id,
                        object_type="Commit",
                        canonical_key=commit_key,
                        properties={"sha": commit_key.removeprefix("git:commit:")},
                        created_revision=revision,
                    ),
                    RelationModel(
                        relation_id=first_relation_id,
                        source_object_id=OBJECT_ID,
                        relation_type="references-development-object",
                        target_object_id=pr_id,
                        qualifier={
                            "reference_url": (
                                "https://github.com/vllm-project/vllm/pull/43426"
                            ),
                            "reference_kind": "pull_request",
                        },
                        origin="deterministic_derived",
                        lifecycle="accepted",
                        created_revision=revision,
                    ),
                    RelationModel(
                        relation_id=second_relation_id,
                        source_object_id=pr_id,
                        relation_type="merged-as",
                        target_object_id=commit_id,
                        qualifier={},
                        origin="source_asserted",
                        lifecycle="accepted",
                        created_revision=revision,
                    ),
                    EvidenceLinkModel(
                        evidence_link_id=first_evidence_id,
                        target_kind="relation",
                        target_id=first_relation_id,
                        observation_id="question-observation",
                        artifact_id=None,
                        locator={"field": "references"},
                        locator_hash="dev-reference-locator",
                    ),
                    EvidenceLinkModel(
                        evidence_link_id=second_evidence_id,
                        target_kind="relation",
                        target_id=second_relation_id,
                        observation_id="question-observation",
                        artifact_id=None,
                        locator={"field": "merge_commit_sha"},
                        locator_hash="merged-as-locator",
                    ),
                ]
            )

        async with factory() as session:
            result = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-depth2-1",
                    question=f"Which commit was the referenced fix PR for {CVE} merged as?",
                    cve_id=CVE,
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert result.mode == "completed"
        assert result.decision is not None
        assert result.decision.answer == {"merge_commit": commit_key}
        state_payload = provider.requests[0].data["investigation_state"]
        assert first_fact in str(state_payload)
        assert second_fact in str(state_payload)

        async with factory() as session:
            run = await session.scalar(
                select(TaskRunModel).where(
                    TaskRunModel.run_id == provider.requests[0].metadata["task_run_id"]
                )
            )
            assert run is not None
            context = await session.get(
                ContextManifestVersionModel,
                run.context_manifest_version_id,
            )
            assert context is not None
            assert f"relation:{first_relation_id}" in context.manifest_json["relation_refs"]
            assert f"relation:{second_relation_id}" in context.manifest_json["relation_refs"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_relation_context_preserves_compact_applicability_semantics() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=FinalDecisionProposal(
                conclusions=[
                    DecisionConclusion(
                        statement=RELATION_PROPOSITION,
                        type=ConclusionType.FACT,
                        evidence_refs=[f"evidence:{RELATION_EVIDENCE_ID}"],
                    )
                ],
                answer_payload={"status": "fixed", "product": "test-product:1.2.3"},
                stop_reason="evidence_sufficient",
            )
        )
    )
    try:
        async with factory() as session:
            result = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-relation-1",
                    question=f"What is the applicability status for {CVE}?",
                    cve_id=CVE,
                    task_kind=TaskKind.LOOKUP,
                ),
            )
        assert result.mode == "completed"
        assert result.decision is not None
        assert result.decision.citations[0].evidence_ref == (
            f"evidence:{RELATION_EVIDENCE_ID}"
        )
        state_payload = provider.requests[0].data["investigation_state"]
        assert RELATION_PROPOSITION in str(state_payload)
        assert "fixed" in RELATION_PROPOSITION
        assert "test-product 1.2.3" in RELATION_PROPOSITION
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lookup_continuation_escalates_to_durable_investigation() -> None:
    engine, factory = await _factory()
    provider = _Provider(
        DecisionPlannerResponse(
            action=ContinuationProposal(
                proposition_or_question="Which primary advisory confirms the fixed release?",
                purpose="verify_fix_release",
                target_objects=[OBJECT_ID],
                preferred_source_roles=["primary"],
                evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
                priority=80,
                reason="current evidence does not establish a fixed release",
            )
        )
    )
    try:
        async with factory() as session:
            result = await _use_case(provider).execute(
                session,
                AskQuestionCommand(
                    principal="user:test",
                    request_id="question-escalate-1",
                    question=f"Which version fixes {CVE}?",
                    cve_id=CVE,
                    task_kind=TaskKind.LOOKUP,
                ),
            )
            assert result.mode == "accepted"
            assert result.execution_profile == "INVESTIGATE"
            assert result.investigation is not None
            assert result.investigation.status == "active"
            assert result.investigation.open_evidence_needs[0].purpose == "verify_fix_release"
            assert result.investigation.open_evidence_needs[0].priority == 80
            assert result.investigation.open_evidence_needs[0].required_source_roles == ["primary"]

        async with factory() as session:
            runs = list(
                await session.scalars(select(TaskRunModel).order_by(TaskRunModel.created_at))
            )
            assert len(runs) == 2
            assert runs[0].role_id == "DecisionRole"
            assert runs[0].status == "completed"
            assert runs[0].stop_reason == "escalated_to_investigation"
            assert runs[1].role_id == "InvestigationRole"
            assert runs[1].status == "queued"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_runtime_terminates_failed_model_attempt() -> None:
    engine, factory = await _factory()
    try:
        async with factory() as session:
            with pytest.raises(RuntimeError, match="provider failed"):
                await _use_case(_FailingProvider()).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="question-failure-1",
                        question=f"What is the CVSS score for {CVE}?",
                        cve_id=CVE,
                    ),
                )
        async with factory() as session:
            run = await session.scalar(select(TaskRunModel))
            execution = await session.scalar(select(ExecutionRunModel))
            assert run is not None and run.status == "failed"
            assert run.stop_reason == "question_reasoning_failed"
            assert execution is not None and execution.status == "failed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_question_timeout_returns_retryable_problem_after_terminating_runtime() -> None:
    from apps.application.errors import DeadlineExceededError

    class TimedOutProvider:
        name = 'timeout-fixture'
        version = '1'

        async def generate_structured(self, request, response_model):
            raise TimeoutError('logical deadline exhausted')

    engine, factory = await _factory()
    try:
        async with factory() as session:
            with pytest.raises(DeadlineExceededError) as failure:
                await _use_case(TimedOutProvider()).execute(session, AskQuestionCommand(
                    principal='user:test', request_id='question-timeout',
                    question=f'What is the CVSS score for {CVE}?', cve_id=CVE,
                ))
            assert failure.value.retryable
            assert failure.value.context['timeout_seconds'] == 5
        async with factory() as session:
            run = await session.scalar(select(TaskRunModel))
            execution = await session.scalar(select(ExecutionRunModel))
            assert run.status == 'failed'
            assert run.stop_reason == 'question_deadline_exceeded'
            assert execution.status == 'failed'
    finally:
        await engine.dispose()
