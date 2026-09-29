from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.commands.ask_question import AskQuestionCommand, AskQuestionUseCase
from apps.application.errors import LifecycleConflictError
from apps.application.queries.decisions import DecisionQueries
from apps.application.question_facts import render_relation_fact
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
from packages.investigation.state.contracts import EvidenceNeedContract
from packages.investigation.storage.models import EvidenceNeedModel, InvestigationCaseModel
from packages.reasoning.decision import ConclusionType, DecisionConclusion
from packages.reasoning.model import (
    ContinuationProposal,
    DecisionPlannerResponse,
    FinalDecisionProposal,
)
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.config import get_settings
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest
from packages.sources.storage.models import SourceModel
from packages.task_runtime.contracts.models import TaskKind
from packages.task_runtime.storage.models import ContextManifestVersionModel, TaskRunModel

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
) -> AskQuestionUseCase:
    settings = get_settings()
    return AskQuestionUseCase(
        policy_path=settings.runtime_policy_path,
        task_event_stream_name=settings.task_event_stream_name,
        model_provider=provider,
        retrieval=retrieval,
    )


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
            reread = await DecisionQueries().get(session, result.decision.decision_id)
            assert reread.decision_id == result.decision.decision_id
            assert reread.answer == {"cvss_score": 9.8}

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
async def test_targetless_retrieve_continuation_without_selected_target_blocks() -> None:
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
            with pytest.raises(LifecycleConflictError, match="requires a bound target"):
                await _use_case(provider, retrieval=_FixtureRetrieval()).execute(
                    session,
                    AskQuestionCommand(
                        principal="user:test",
                        request_id="question-retrieve-blocked-1",
                        question="Find more evidence about the research note",
                        task_kind=TaskKind.RETRIEVE,
                    ),
                )
        async with factory() as session:
            assert int(
                await session.scalar(select(func.count()).select_from(InvestigationCaseModel)) or 0
            ) == 0
            run = await session.scalar(select(TaskRunModel))
            execution = await session.scalar(select(ExecutionRunModel))
            assert run is not None and run.status == "blocked"
            assert run.stop_reason == "continuation_requires_bound_target"
            assert execution is not None and execution.status == "blocked"
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
