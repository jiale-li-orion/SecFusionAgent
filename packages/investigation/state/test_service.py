from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
)
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import (
    EvidenceNeedContract,
    EvidenceNeedStatus,
    ProposedState,
    ReasoningRelation,
    ReasoningSemantics,
    StatePatch,
    StatePatchOperation,
)
from packages.investigation.state.service import (
    InvestigationStateService,
    StatePatchRejected,
    StateRevisionConflict,
)
from packages.investigation.storage.models import (
    CaseStateEventModel,
    EvidenceNeedModel,
    InvestigationCaseModel,
    InvestigationStateCurrentModel,
)
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel

NOW = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_case(session) -> tuple[str, str]:
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-51515",
            properties={},
            created_revision=revision.revision,
        )
    )
    await session.flush()
    case = await CaseService(now=lambda: NOW).create(
        session,
        task_signature="verify-fix-boundary",
        target_object_ids=[object_id],
        goal="Verify the first release containing the fix commit.",
        initial_knowledge_revision=revision.revision,
    )
    return case.case_id, object_id


async def _seed_evidence(
    session,
    *,
    source_id: str,
    source_role: str,
    source_family: str,
    target_object_id: str,
    upstream_source: str | None = None,
) -> str:
    source = await session.get(SourceModel, source_id)
    if source is None:
        session.add(
            SourceModel(
                source_id=source_id,
                adapter_type="fixture",
                source_class="test",
                authority_scope=["test"],
                source_role=source_role,
                source_family=source_family,
                upstream_source=upstream_source,
                access_mode="fixture",
                update_semantics="append",
                discovery_method={},
                time_semantics={},
                identity_semantics={},
                auth_ref=None,
                rate_limit_policy={},
                access_rights={},
                retention_mode="durable_managed",
                schedule_policy={},
                schema_version="1",
                definition_hash=f"hash-{source_id}",
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
            external_object_id=f"external-{observation_id}",
            external_revision="v1",
            canonical_url=f"https://example.invalid/{observation_id}",
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
    evidence_id = str(uuid4())
    session.add(
        EvidenceLinkModel(
            evidence_link_id=evidence_id,
            target_kind="object",
            target_id=target_object_id,
            observation_id=observation_id,
            artifact_id=None,
            locator={"kind": "fixture"},
            locator_hash=uuid4().hex + uuid4().hex,
        )
    )
    await session.flush()
    return evidence_id


@pytest.mark.asyncio
async def test_case_state_starts_revision_zero_and_evidence_need_is_append_only_event() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            state = await InvestigationStateService(now=lambda: NOW).get_state(session, case_id)
            assert state.case_revision == 0
            opened = await InvestigationStateService(now=lambda: NOW).open_evidence_need(
                session,
                case_id=case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Which release first contains fix commit abc123?",
                purpose="verify_release_containment",
                target_objects=[object_id],
            )
            assert opened.need.status is EvidenceNeedStatus.OPEN
            assert opened.event.case_revision == 1
            assert opened.state.evidence_need_ids == [opened.need.need_id]
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None
            assert case.status == "active"
            assert case.current_revision == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_evidence_ref_cannot_confirm_the_wrong_target_object() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            revision = await session.scalar(select(KnowledgeRevisionModel.revision).limit(1))
            assert revision is not None
            other_object_id = str(uuid4())
            session.add(
                ObjectModel(
                    object_id=other_object_id,
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-99999",
                    properties={},
                    created_revision=revision,
                )
            )
            await session.flush()
            unrelated_evidence = await _seed_evidence(
                session,
                source_id="unrelated-primary",
                source_role="primary",
                source_family="unrelated-vendor",
                target_object_id=other_object_id,
            )
            with pytest.raises(
                StatePatchRejected, match="does not support StatePatch target object"
            ):
                await service.apply_patch(
                    session,
                    StatePatch(
                        patch_id=str(uuid4()),
                        case_id=case_id,
                        base_case_revision=0,
                        producer="model:test",
                        operations=[
                            StatePatchOperation(
                                proposition="unrelated advisory proves this vulnerability is fixed",
                                target_ref=f"object:{object_id}",
                                proposed_state=ProposedState.CONFIRMED,
                                evidence_refs=[unrelated_evidence],
                            )
                        ],
                    ),
                )
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None and case.current_revision == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_patch_and_unknown_evidence_ref_fail_closed_without_revision_change() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            opened = await service.open_evidence_need(
                session,
                case_id=case_id,
                base_case_revision=0,
                need_id=str(uuid4()),
                proposition_or_question="Need primary confirmation",
                purpose="confirm_fix",
                target_objects=[object_id],
            )
            with pytest.raises(StateRevisionConflict, match="stale case revision"):
                await service.apply_patch(
                    session,
                    StatePatch(
                        patch_id=str(uuid4()),
                        case_id=case_id,
                        base_case_revision=0,
                        producer="model:test",
                        operations=[
                            StatePatchOperation(
                                proposition="v0.22.0 contains abc123",
                                target_ref=f"object:{object_id}",
                                proposed_state=ProposedState.CONFIRMED,
                                evidence_refs=[str(uuid4())],
                            )
                        ],
                    ),
                )
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None and case.current_revision == opened.event.case_revision

        async with factory() as session, session.begin():
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None
            with pytest.raises(StatePatchRejected, match="unknown EvidenceRef"):
                await service.apply_patch(
                    session,
                    StatePatch(
                        patch_id=str(uuid4()),
                        case_id=case_id,
                        base_case_revision=case.current_revision,
                        producer="model:test",
                        operations=[
                            StatePatchOperation(
                                proposition="v0.22.0 contains abc123",
                                target_ref=f"object:{object_id}",
                                proposed_state=ProposedState.CONFIRMED,
                                evidence_refs=[str(uuid4())],
                            )
                        ],
                    ),
                )
            assert case.current_revision == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_inferred_relation_cannot_bypass_state_gate_into_confirmed() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            evidence = await _seed_evidence(
                session,
                source_id="github-primary",
                source_role="primary",
                source_family="github",
                target_object_id=object_id,
            )
            with pytest.raises(StatePatchRejected, match="inferred reasoning relation"):
                await service.apply_patch(
                    session,
                    StatePatch(
                        patch_id=str(uuid4()),
                        case_id=case_id,
                        base_case_revision=0,
                        producer="model:test",
                        operations=[
                            StatePatchOperation(
                                proposition="PR merge time proves first fixed release",
                                target_ref=f"object:{object_id}",
                                proposed_state=ProposedState.CONFIRMED,
                                evidence_refs=[evidence],
                                reasoning_relation=ReasoningRelation(
                                    relation_type="release-contains-commit",
                                    semantics=ReasoningSemantics.INFERRED,
                                ),
                            )
                        ],
                    ),
                )
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None and case.current_revision == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_evidence_need_requires_roles_and_independent_sources_before_resolution() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            primary = await _seed_evidence(
                session,
                source_id="vendor-primary",
                source_role="primary",
                source_family="vendor",
                target_object_id=object_id,
            )
            forensic = await _seed_evidence(
                session,
                source_id="forensic-independent",
                source_role="forensic",
                source_family="forensic-lab",
                target_object_id=object_id,
            )
            need_id = str(uuid4())
            await service.open_evidence_need(
                session,
                case_id=case_id,
                base_case_revision=0,
                need_id=need_id,
                proposition_or_question="Is the fix in release v0.22.0?",
                purpose="verify_fix_release",
                target_objects=[object_id],
                evidence_contract=EvidenceNeedContract(
                    required_source_roles=["primary", "forensic"],
                    min_independent_sources=2,
                ),
            )

        async with factory() as session, session.begin():
            with pytest.raises(StatePatchRejected, match="required source role missing: forensic"):
                await service.apply_patch(
                    session,
                    StatePatch(
                        patch_id=str(uuid4()),
                        case_id=case_id,
                        base_case_revision=1,
                        producer="InvestigationRole",
                        operations=[
                            StatePatchOperation(
                                proposition="v0.22.0 contains the fix",
                                target_ref=f"object:{object_id}",
                                proposed_state=ProposedState.CONFIRMED,
                                evidence_refs=[primary],
                                resolves_need_id=need_id,
                            )
                        ],
                    ),
                )
            case = await session.get(InvestigationCaseModel, case_id)
            assert case is not None and case.current_revision == 1

        patch_id = str(uuid4())
        async with factory() as session, session.begin():
            result = await service.apply_patch(
                session,
                StatePatch(
                    patch_id=patch_id,
                    case_id=case_id,
                    base_case_revision=1,
                    producer="InvestigationRole",
                    operations=[
                        StatePatchOperation(
                            proposition="v0.22.0 contains the fix",
                            target_ref=f"object:{object_id}",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[primary, forensic],
                            reasoning_relation=ReasoningRelation(
                                relation_type="release-contains-commit",
                                semantics=ReasoningSemantics.DETERMINISTIC,
                            ),
                            resolves_need_id=need_id,
                        )
                    ],
                ),
            )
            assert result.state.case_revision == 3
            assert [item.proposition for item in result.state.confirmed] == [
                "v0.22.0 contains the fix"
            ]
            assert result.state.evidence_need_ids == []
            need = await session.get(EvidenceNeedModel, need_id)
            assert need is not None and need.status == EvidenceNeedStatus.RESOLVED.value
            assert need.resolution_evidence_refs == [primary, forensic]

        async with factory() as session, session.begin():
            replay = await service.apply_patch(
                session,
                StatePatch(
                    patch_id=patch_id,
                    case_id=case_id,
                    base_case_revision=1,
                    producer="InvestigationRole",
                    operations=[
                        StatePatchOperation(
                            proposition="v0.22.0 contains the fix",
                            target_ref=f"object:{object_id}",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[primary, forensic],
                            reasoning_relation=ReasoningRelation(
                                relation_type="release-contains-commit",
                                semantics=ReasoningSemantics.DETERMINISTIC,
                            ),
                            resolves_need_id=need_id,
                        )
                    ],
                ),
            )
            assert replay.replay is True
            assert replay.state.case_revision == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_materialized_investigation_state_rebuilds_from_append_only_events() -> None:
    engine, factory = await _database()
    service = InvestigationStateService(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            case_id, object_id = await _seed_case(session)
            evidence = await _seed_evidence(
                session,
                source_id="primary-a",
                source_role="primary",
                source_family="vendor-a",
                target_object_id=object_id,
            )
            result = await service.apply_patch(
                session,
                StatePatch(
                    patch_id=str(uuid4()),
                    case_id=case_id,
                    base_case_revision=0,
                    producer="analyst:test",
                    operations=[
                        StatePatchOperation(
                            proposition="fix commit is abc123",
                            target_ref=f"object:{object_id}",
                            proposed_state=ProposedState.CONFIRMED,
                            evidence_refs=[evidence],
                        ),
                        StatePatchOperation(
                            proposition="first containing release is not yet known",
                            target_ref=f"object:{object_id}",
                            proposed_state=ProposedState.UNKNOWN,
                        ),
                    ],
                ),
            )
            expected = result.state.model_dump(mode="json", exclude={"updated_at"})
            await session.execute(
                delete(InvestigationStateCurrentModel).where(
                    InvestigationStateCurrentModel.case_id == case_id
                )
            )

        async with factory() as session, session.begin():
            rebuilt = await service.rebuild(session, case_id)
            assert rebuilt.model_dump(mode="json", exclude={"updated_at"}) == expected
            events = list(
                await session.scalars(
                    select(CaseStateEventModel)
                    .where(CaseStateEventModel.case_id == case_id)
                    .order_by(CaseStateEventModel.case_revision)
                )
            )
            assert [item.case_revision for item in events] == [1, 2]
            assert [item.base_case_revision for item in events] == [0, 1]
    finally:
        await engine.dispose()
