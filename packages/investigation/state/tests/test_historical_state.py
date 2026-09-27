from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import (
    DecisionCommit,
    EvidenceNeedContract,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 23, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_state_at_revision_replays_state_without_mutating_current_projection() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="historical-state",
                target_object_ids=[],
                goal="Rebuild the exact historical M4 state.",
                initial_knowledge_revision=7,
            )
            opened = await service.open_evidence_need(
                session,
                case_id=case.case_id,
                base_case_revision=0,
                need_id="need-history",
                proposition_or_question="Is the proposition currently knowable?",
                purpose="historical-replay",
                target_objects=[],
                evidence_contract=EvidenceNeedContract(require_evidence=False),
            )
            assert opened.state.case_revision == 1

            patched = await service.apply_patch(
                session,
                StatePatch(
                    patch_id="patch-history",
                    case_id=case.case_id,
                    base_case_revision=1,
                    producer="test",
                    operations=[
                        StatePatchOperation(
                            proposition="The proposition remains unknown.",
                            proposed_state=ProposedState.UNKNOWN,
                            resolves_need_id="need-history",
                        )
                    ],
                ),
            )
            assert patched.state.case_revision == 3

            committed = await service.commit_decision(
                session,
                DecisionCommit(
                    decision_id="decision-history",
                    case_id=case.case_id,
                    base_case_revision=3,
                    decision={
                        "decision_id": "decision-history",
                        "case_id": case.case_id,
                        "case_revision": 3,
                        "status": "partial",
                    },
                ),
            )
            assert committed.state.case_revision == 4
            current_before = await service.get_state(session, case.case_id)

            revision_0 = await service.get_state_at_revision(session, case.case_id, 0)
            revision_1 = await service.get_state_at_revision(session, case.case_id, 1)
            revision_3 = await service.get_state_at_revision(session, case.case_id, 3)
            revision_4 = await service.get_state_at_revision(session, case.case_id, 4)
            current_after = await service.get_state(session, case.case_id)

            assert revision_0.case_revision == 0
            assert revision_0.evidence_need_ids == []
            assert revision_0.last_world_revision == 7
            assert revision_1.evidence_need_ids == ["need-history"]
            assert revision_1.unknowns == []
            assert revision_3.evidence_need_ids == []
            assert [item.proposition for item in revision_3.unknowns] == [
                "The proposition remains unknown."
            ]
            assert revision_3.current_decision is None
            assert revision_4.current_decision is not None
            assert revision_4.current_decision["decision_id"] == "decision-history"
            assert current_after == current_before

            with pytest.raises(ValueError, match="outside durable range"):
                await service.get_state_at_revision(session, case.case_id, 5)
    finally:
        await engine.dispose()
