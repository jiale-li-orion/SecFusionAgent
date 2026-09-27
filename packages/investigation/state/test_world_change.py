from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import (
    EvidenceNeedStatus,
    ProposedState,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.state.world_change import KnowledgeChangeNotice, WorldChangeService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 9, 27, 5, 30, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_confirmed_waiting_case(session) -> tuple[str, str, str, str, int]:
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-80808",
            properties={},
            created_revision=revision.revision,
        )
    )
    source_id = f"vendor-primary-{uuid4()}"
    session.add(
        SourceModel(
            source_id=source_id,
            adapter_type="fixture",
            source_class="vendor_security_material",
            authority_scope=["fix_status"],
            source_role="primary",
            source_family="vendor",
            upstream_source=None,
            access_mode="fixture",
            update_semantics="mutable",
            discovery_method={},
            time_semantics={},
            identity_semantics={},
            auth_ref=None,
            rate_limit_policy={},
            access_rights={},
            retention_mode="durable_managed",
            schedule_policy={},
            schema_version="1",
            definition_hash=uuid4().hex,
            managed_by="test",
            enabled=True,
            updated_at=NOW,
        )
    )
    await session.flush()
    observation_id = str(uuid4())
    session.add(
        ObservationModel(
            observation_id=observation_id,
            source_id=source_id,
            acquisition_run_id=None,
            acquisition_trigger="replay",
            external_object_id="vendor-advisory",
            external_revision="v1",
            canonical_url="https://example.invalid/advisory",
            published_at=NOW,
            updated_at=NOW,
            observed_at=NOW,
            content_hash=uuid4().hex + uuid4().hex,
            request_metadata={},
            request_metadata_captured=True,
            idempotency_key=uuid4().hex + uuid4().hex,
            created_at=NOW,
        )
    )
    await session.flush()
    claim_id = str(uuid4())
    session.add(
        ClaimModel(
            claim_id=claim_id,
            subject_id=object_id,
            predicate="fixed_version",
            value="0.22.0",
            qualifier={"source_id": source_id, "vocabulary_scope": "canonical"},
            origin="source_asserted",
            lifecycle="accepted",
            processing_run_id=None,
            created_revision=revision.revision,
        )
    )
    await session.flush()
    evidence_id = str(uuid4())
    session.add(
        EvidenceLinkModel(
            evidence_link_id=evidence_id,
            target_kind="claim",
            target_id=claim_id,
            observation_id=observation_id,
            artifact_id=None,
            locator={"kind": "fixture", "field": "fixed_version"},
            locator_hash=uuid4().hex + uuid4().hex,
        )
    )
    await session.flush()

    case_service = CaseService(now=lambda: NOW)
    state_service = InvestigationStateService(now=lambda: NOW)
    case = await case_service.create(
        session,
        task_signature="verify-fix-world-change",
        target_object_ids=[object_id],
        goal="Verify the current fixed release.",
        initial_knowledge_revision=revision.revision,
    )
    need_id = str(uuid4())
    opened = await state_service.open_evidence_need(
        session,
        case_id=case.case_id,
        base_case_revision=0,
        need_id=need_id,
        proposition_or_question="Fixed release is v0.22.0",
        purpose="verify_fix_release",
        target_objects=[object_id],
    )
    confirmed = await state_service.apply_patch(
        session,
        StatePatch(
            patch_id=str(uuid4()),
            case_id=case.case_id,
            base_case_revision=opened.state.case_revision,
            producer="InvestigationRole:test",
            operations=[
                StatePatchOperation(
                    proposition="Fixed release is v0.22.0",
                    target_ref=f"object:{object_id}",
                    proposed_state=ProposedState.CONFIRMED,
                    evidence_refs=[evidence_id],
                    resolves_need_id=need_id,
                )
            ],
        ),
    )
    await case_service.wait(session, case.case_id)
    return case.case_id, object_id, claim_id, need_id, confirmed.state.case_revision


@pytest.mark.asyncio
async def test_relevant_world_change_invalidates_confirmed_state_reopens_need_and_wakes_case() -> (
    None
):
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            (
                case_id,
                object_id,
                claim_id,
                need_id,
                before_revision,
            ) = await _seed_confirmed_waiting_case(session)
            impacts = await WorldChangeService().process(
                session,
                KnowledgeChangeNotice(
                    revision=2,
                    object_ids=[object_id],
                    claim_ids=[claim_id],
                ),
            )
            assert len(impacts) == 1
            impact = impacts[0]
            assert impact.case_id == case_id
            assert impact.case_activated is True
            assert impact.affected_propositions == ["Fixed release is v0.22.0"]
            assert impact.opened_or_reopened_need_ids == [need_id]

            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None and case.status == "active"
            state = await InvestigationStateService().get_state(session, case_id)
            assert state.confirmed == []
            assert [item.proposition for item in state.unknowns] == ["Fixed release is v0.22.0"]
            assert state.case_revision > before_revision
            need = await InvestigationStateService().get_evidence_need(session, need_id)
            assert need.status is EvidenceNeedStatus.OPEN
            assert need.resolution_evidence_refs == []
            first_revision = state.case_revision

        async with factory() as session, session.begin():
            replay = await WorldChangeService().process(
                session,
                KnowledgeChangeNotice(
                    revision=2,
                    object_ids=[object_id],
                    claim_ids=[claim_id],
                ),
            )
            assert len(replay) == 1
            state = await InvestigationStateService().get_state(session, case_id)
            assert state.case_revision == first_revision
            need = await InvestigationStateService().get_evidence_need(session, need_id)
            assert need.status is EvidenceNeedStatus.OPEN
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_irrelevant_world_change_does_not_mutate_case() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, _, _, _, before_revision = await _seed_confirmed_waiting_case(session)
            impacts = await WorldChangeService().process(
                session,
                KnowledgeChangeNotice(
                    revision=2,
                    object_ids=[str(uuid4())],
                    claim_ids=[str(uuid4())],
                ),
            )
            assert impacts == []
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None
            assert case.status == "waiting"
            assert case.current_revision == before_revision
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_target_only_change_wakes_waiting_case_without_inventing_state() -> None:
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
                    canonical_key="cve:CVE-2026-81818",
                    properties={},
                    created_revision=revision.revision,
                )
            )
            await session.flush()
            case_service = CaseService(now=lambda: NOW)
            case = await case_service.create(
                session,
                task_signature="watch-target-change",
                target_object_ids=[object_id],
                goal="Watch target changes.",
                initial_knowledge_revision=revision.revision,
            )
            await case_service.activate(session, case.case_id)
            await case_service.wait(session, case.case_id)
            impacts = await WorldChangeService().process(
                session,
                KnowledgeChangeNotice(revision=2, object_ids=[object_id]),
            )
            assert len(impacts) == 1
            assert impacts[0].case_activated is True
            assert impacts[0].affected_propositions == []
            state = await InvestigationStateService().get_state(session, case.case_id)
            assert state.confirmed == []
            assert state.unknowns == []
            assert state.evidence_need_ids == []
    finally:
        await engine.dispose()
