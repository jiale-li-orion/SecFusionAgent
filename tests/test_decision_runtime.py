from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.decision_runtime import DecisionRuntime
from apps.runtime_models import register_runtime_models
from packages.investigation.cases.service import CaseService
from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.service import InvestigationStateService
from packages.reasoning.decision import DecisionDraft
from packages.reasoning.model import (
    ContinuationProposal,
    DecisionPlannerResponse,
    FinalDecisionProposal,
    ModelDecisionPlanner,
)
from packages.shared.db import Base
from packages.shared.model_provider import StructuredModelRequest

NOW = datetime(2026, 9, 27, 19, 0, tzinfo=UTC)


class _DecisionProvider:
    name = "fixture-decision-runtime"
    version = "v1"

    def __init__(self, response: DecisionPlannerResponse) -> None:
        self.response = response
        self.requests: list[StructuredModelRequest] = []

    async def generate_structured(self, request, response_model):
        assert response_model is DecisionPlannerResponse
        self.requests.append(request)
        return self.response


@pytest.mark.asyncio
async def test_decision_runtime_commits_through_m4_gate_and_replays_by_decision_id() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    state_service = InvestigationStateService(now=lambda: NOW)
    runtime = DecisionRuntime(state_service=state_service)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="decision-runtime-test",
                target_object_ids=[],
                goal="Produce a partial decision without inventing missing evidence.",
                initial_knowledge_revision=0,
            )
            state = await state_service.get_state(session, case.case_id)
            draft = DecisionDraft(
                case_id=case.case_id,
                case_revision=state.case_revision,
                unknowns=["No primary evidence has been collected yet."],
                answer_payload={"status": "partial"},
                stop_reason="insufficient_evidence",
                model_prompt_revision="decision-v1",
            )
            decision, committed = await runtime.finalize(
                session,
                state=state,
                draft=draft,
                citation_sources=[],
            )
            replay_decision, replay = await runtime.finalize(
                session,
                state=state,
                draft=draft,
                citation_sources=[],
            )

            assert committed.replay is False
            assert replay.replay is True
            assert replay_decision.decision_id == decision.decision_id
            current = await state_service.get_state(session, case.case_id)
            assert current.case_revision == 1
            assert current.current_decision is not None
            assert current.current_decision["decision_id"] == decision.decision_id
            assert current.current_decision["case_revision"] == 0
    finally:
        await engine.dispose()


def test_continuation_intent_rejects_payload_or_target_tampering() -> None:
    runtime = DecisionRuntime()
    request = ContinuationRequest(
        request_id="continuation:test",
        case_id="case-1",
        base_case_revision=3,
        proposition_or_question="Which source confirms the incident?",
        purpose="confirm_incident",
        target_objects=["object-1"],
        reason="missing primary evidence",
    )
    envelope = runtime.continuation_intent(request)
    assert envelope.intent.trigger_ref == request.request_id
    assert envelope.intent.candidate_targets == ["object-1"]
    assert envelope.intent.context_refs == []
    assert envelope.intent.requested_actions == ["open_evidence_need"]
    assert envelope.intent.requested_output["continuation_request"] == request.model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_decision_runtime_execute_routes_model_gap_through_m4_continuation_gate() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    state_service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="decision-runtime-continuation",
                target_object_ids=[],
                goal="Determine whether more evidence is needed.",
                initial_knowledge_revision=0,
            )
            state = await state_service.get_state(session, case.case_id)
            provider = _DecisionProvider(
                DecisionPlannerResponse(
                    action=ContinuationProposal(
                        proposition_or_question="What primary evidence confirms the incident?",
                        purpose="confirm_incident",
                        target_objects=[],
                        reason="M4 state has no confirmation evidence",
                    )
                )
            )
            outcome = await DecisionRuntime(state_service=state_service).execute(
                session,
                state=state,
                planner=ModelDecisionPlanner(provider),
                citation_sources=[],
            )
            assert outcome.decision is None
            assert outcome.continuation_intent is not None
            assert outcome.continuation_intent.trigger_ref is not None
            assert outcome.continuation_intent.requested_actions == ["open_evidence_need"]
            assert outcome.continuation_intent.context_refs == []
            assert outcome.continuation is not None
            assert outcome.continuation.need.purpose == "confirm_incident"
            assert outcome.continuation.need.opened_revision == 1
            assert provider.requests[0].metadata["case_revision"] == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_decision_runtime_execute_routes_final_model_output_through_decision_gate() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    state_service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="decision-runtime-final",
                target_object_ids=[],
                goal="Return a partial answer without inventing facts.",
                initial_knowledge_revision=0,
            )
            state = await state_service.get_state(session, case.case_id)
            provider = _DecisionProvider(
                DecisionPlannerResponse(
                    action=FinalDecisionProposal(
                        unknowns=["No evidence-backed conclusion is available."],
                        answer_payload={"status": "partial"},
                        stop_reason="insufficient_evidence",
                    )
                )
            )
            outcome = await DecisionRuntime(state_service=state_service).execute(
                session,
                state=state,
                planner=ModelDecisionPlanner(provider),
                citation_sources=[],
            )
            assert outcome.decision is not None
            assert outcome.decision_commit is not None
            assert outcome.continuation_intent is None
            assert outcome.continuation is None
            current = await state_service.get_state(session, case.case_id)
            assert current.current_decision is not None
            assert current.current_decision["decision_id"] == outcome.decision.decision_id
    finally:
        await engine.dispose()
