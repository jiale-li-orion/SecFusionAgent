from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.application.commands.finalize_investigation import _partial_evidence_report
from apps.application.question_sessions import QuestionSessionStore
from apps.runtime_models import register_runtime_models
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionService
from packages.shared.db import Base


def test_partial_report_keeps_confirmed_citations_and_unknown_boundary() -> None:
    state = InvestigationState(
        case_id="case-1",
        case_revision=3,
        goal="What did the operator do?",
        confirmed=[
            InvestigationStateItem(
                proposition="The operator notified its partners.",
                evidence_refs=["evidence:notice"],
                writer="InvestigationRole",
                reason_code="verified",
                updated_revision=2,
            )
        ],
        unknowns=[
            InvestigationStateItem(
                proposition="Whether funds were frozen remains unverified.",
                writer="InvestigationRole",
                reason_code="not_in_source",
                updated_revision=3,
            )
        ],
        evidence_need_ids=["need-1"],
        updated_at=datetime(2026, 10, 9, tzinfo=UTC),
    )

    decision = DecisionService().decide(
        state,
        _partial_evidence_report(state),
        citation_sources=[
            CitationSource(
                evidence_ref="evidence:notice",
                source_ref="source:notice",
                locator={"field": "body"},
            )
        ],
    )

    assert decision.conclusions[0].statement == state.confirmed[0].proposition
    assert decision.citations[0].evidence_ref == "evidence:notice"
    assert decision.unknowns == [state.unknowns[0].proposition]
    assert len(decision.report_paragraphs) == 2


@pytest.mark.asyncio
async def test_decision_binding_is_exact_to_one_owned_investigation_turn() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    store = QuestionSessionStore()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session, session.begin():
            await store.append_turn(
                session,
                session_id="session-1",
                principal="user:owner",
                request_id="request-1",
                question="What happened?",
                task_kind="investigate_incident",
                target_object_ids=[],
                knowledge_revision=1,
                context_id=None,
                decision_ref=None,
                investigation_ref="case:case-1",
            )
            assert not await store.bind_investigation_decision(
                session, principal="user:other", request_id="request-1",
                case_id="case-1", decision_id="decision:1",
            )
            assert await store.bind_investigation_decision(
                session, principal="user:owner", request_id="request-1",
                case_id="case-1", decision_id="decision:1",
            )
            assert await store.bind_investigation_decision(
                session, principal="user:owner", request_id="request-1",
                case_id="case-1", decision_id="decision:1",
            )
            with pytest.raises(ValueError, match="already bound"):
                await store.bind_investigation_decision(
                    session, principal="user:owner", request_id="request-1",
                    case_id="case-1", decision_id="decision:2",
                )
            turn = (await store.resolve(
                session, session_id="session-1", principal="user:owner",
            )).latest_turn
            assert turn is not None and turn.decision_ref == "decision:1"
    finally:
        await engine.dispose()
