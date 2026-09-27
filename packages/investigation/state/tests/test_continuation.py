from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.investigation.cases.service import CaseService
from packages.investigation.state.continuation import ContinuationGate, ContinuationRequest
from packages.investigation.state.contracts import EvidenceNeedContract, EvidenceNeedStatus
from packages.investigation.state.service import InvestigationStateService
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_continuation_gate_creates_one_deduped_evidence_need() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-92929",
                    properties={},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="decision-continuation-test",
                target_object_ids=[object_id],
                goal="Decide the affected range.",
                initial_knowledge_revision=revision.revision,
            )
            request = ContinuationRequest(
                request_id="decision-gap-1",
                case_id=case.case_id,
                base_case_revision=0,
                proposition_or_question="Which primary source confirms the affected range?",
                purpose="confirm_affected_range",
                target_objects=[object_id],
                evidence_contract=EvidenceNeedContract(required_source_roles=["primary"]),
                priority=80,
                reason="M6 cannot support a fact conclusion yet",
            )
            gate = ContinuationGate(InvestigationStateService(now=lambda: NOW))
            first = await gate.accept(session, request)
            replay = await gate.accept(
                session,
                request.model_copy(update={"request_id": "decision-gap-retry"}),
            )

            assert first.replay is False
            assert replay.replay is True
            assert replay.need.need_id == first.need.need_id
            assert first.need.status is EvidenceNeedStatus.OPEN
            assert first.need.priority == 80

            state = await InvestigationStateService(now=lambda: NOW).get_state(
                session,
                case.case_id,
            )
            assert state.evidence_need_ids == [first.need.need_id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_continuation_gate_rejects_target_outside_case() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            revision = KnowledgeRevisionModel(committed_at=NOW)
            session.add(revision)
            await session.flush()
            object_id = str(uuid4())
            other_id = str(uuid4())
            for current in (object_id, other_id):
                session.add(
                    ObjectModel(
                        object_id=current,
                        object_type="Vulnerability",
                        canonical_key=f"object:{current}",
                        properties={},
                        created_revision=revision.revision,
                    )
                )
            await session.flush()
            case = await CaseService(now=lambda: NOW).create(
                session,
                task_signature="decision-continuation-scope-test",
                target_object_ids=[object_id],
                goal="Decide target facts.",
                initial_knowledge_revision=revision.revision,
            )
            with pytest.raises(ValueError, match="escape Investigation Case"):
                await ContinuationGate().accept(
                    session,
                    ContinuationRequest(
                        request_id="bad-gap",
                        case_id=case.case_id,
                        base_case_revision=0,
                        proposition_or_question="Question outside case scope?",
                        purpose="test_scope",
                        target_objects=[other_id],
                        reason="test",
                    ),
                )
    finally:
        await engine.dispose()
