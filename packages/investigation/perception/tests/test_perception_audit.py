from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.investigation.cases.service import CaseService
from packages.investigation.perception.audit import PerceptionAuditService
from packages.investigation.perception.contracts import (
    Percept,
    PerceptionOperation,
    PerceptionRequest,
    PerceptionTarget,
)
from packages.investigation.perception.planner import PerceptionPlanner
from packages.investigation.runtime.tasks import build_investigation_contract
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.state.snapshot import InvestigationSnapshotService
from packages.investigation.storage.models import (
    InvestigationStateCurrentModel,
    PerceptionEventModel,
)
from packages.shared.db import Base
from packages.task_runtime.contracts.models import ContextManifest, TaskKind
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run

NOW = datetime(2026, 9, 27, 5, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_case_and_run(session) -> tuple[str, str, str]:
    revision = KnowledgeRevisionModel(committed_at=NOW)
    session.add(revision)
    await session.flush()
    object_id = str(uuid4())
    session.add(
        ObjectModel(
            object_id=object_id,
            object_type="Vulnerability",
            canonical_key="cve:CVE-2026-78787",
            properties={},
            created_revision=revision.revision,
        )
    )
    await session.flush()
    case = await CaseService(now=lambda: NOW).create(
        session,
        task_signature="verify-perception-audit",
        target_object_ids=[object_id],
        goal="Verify durable perception state.",
        initial_knowledge_revision=revision.revision,
    )
    need_id = str(uuid4())
    await InvestigationStateService(now=lambda: NOW).open_evidence_need(
        session,
        case_id=case.case_id,
        base_case_revision=0,
        need_id=need_id,
        proposition_or_question="Need current evidence",
        purpose="perception_audit",
        target_objects=[object_id],
    )
    run_id = str(uuid4())
    contract = build_investigation_contract(
        task_contract_id=f"verify:{run_id}",
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        case_id=case.case_id,
        target_object_ids=[object_id],
        required_need_ids=[need_id],
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref="InvestigationRole@1",
        case_ref=case.case_id,
        knowledge_revision=revision.revision,
        investigation_state_ref=f"case:{case.case_id}@1",
        object_refs=[object_id],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:local-read:v1",
        budget_ref=f"budget:{run_id}",
    )
    await create_task_run(
        session,
        contract=contract,
        manifest=manifest,
        role=canonical_roles()["InvestigationRole"],
        execution_envelope_ref=f"execution:{run_id}",
        stream_name="secfusion:task-events:test",
        case_id=case.case_id,
        run_id=run_id,
        now=NOW,
    )
    return case.case_id, need_id, run_id


@pytest.mark.asyncio
async def test_perception_event_updates_and_rebuilds_world_coordinates() -> None:
    engine, factory = await _database()
    state_service = InvestigationStateService(now=lambda: NOW + timedelta(minutes=3))
    audit = PerceptionAuditService(state_service=state_service)
    try:
        async with factory() as session, session.begin():
            case_id, need_id, run_id = await _seed_case_and_run(session)
            request = PerceptionRequest(
                request_id="perception-1",
                case_id=case_id,
                need_id=need_id,
                operation=PerceptionOperation.SEARCH,
                target=PerceptionTarget(query_text="fixed release"),
                time_scope={"kind": "current"},
                budget_ref=f"budget:{run_id}",
            )
            plan = PerceptionPlanner().plan(request)
            percept = Percept(
                percept_id="perception-1",
                request_id=request.request_id,
                target_refs=["object:example"],
                evidence_handles=["evidence:1"],
                observation_handles=["ephemeral:1"],
                cost={"local_operator_calls": 1},
            )
            first = await audit.record(
                session,
                task_run_id=run_id,
                request=request,
                plan=plan,
                percept=percept,
                started_at=NOW + timedelta(minutes=1),
                finished_at=NOW + timedelta(minutes=2),
            )
            assert first.replay is False
            state = await state_service.get_state(session, case_id)
            assert state.last_world_revision == 1
            assert state.last_perception_at == NOW + timedelta(minutes=2)

        async with factory() as session, session.begin():
            request = PerceptionRequest(
                request_id="perception-1",
                case_id=case_id,
                need_id=need_id,
                operation=PerceptionOperation.SEARCH,
                target=PerceptionTarget(query_text="fixed release"),
                time_scope={"kind": "current"},
                budget_ref=f"budget:{run_id}",
            )
            plan = PerceptionPlanner().plan(request)
            percept = Percept(
                percept_id="perception-1",
                request_id=request.request_id,
                target_refs=["object:example"],
                evidence_handles=["evidence:1"],
                observation_handles=["ephemeral:1"],
                cost={"local_operator_calls": 1},
            )
            replay = await audit.record(
                session,
                task_run_id=run_id,
                request=request,
                plan=plan,
                percept=percept,
                started_at=NOW + timedelta(minutes=1),
                finished_at=NOW + timedelta(minutes=2),
            )
            assert replay.replay is True
            assert replay.perception_event_id == first.perception_event_id
            assert len(list(await session.scalars(select(PerceptionEventModel)))) == 1

        async with factory() as session, session.begin():
            await session.execute(
                delete(InvestigationStateCurrentModel).where(
                    InvestigationStateCurrentModel.case_id == case_id
                )
            )
        async with factory() as session, session.begin():
            rebuilt = await state_service.rebuild(session, case_id)
            assert rebuilt.last_world_revision == 1
            assert rebuilt.last_perception_at == NOW + timedelta(minutes=2)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_investigation_snapshot_captures_case_and_world_revision_pointers() -> None:
    engine, factory = await _database()
    try:
        async with factory() as session, session.begin():
            case_id, _, _ = await _seed_case_and_run(session)
            snapshot = await InvestigationSnapshotService().create(
                session,
                case_id=case_id,
                policy_revision="policy-v1",
                capability_registry_revision="capabilities-v1",
                routing_query_planner_revision="perception-planner-v1",
                model_revision="model-test",
                prompt_assembly_revision="prompt-v1",
                source_availability_snapshot={"github": "healthy"},
                created_at=NOW,
            )
            assert snapshot.case_revision == 1
            assert snapshot.knowledge_revision == 1
            assert snapshot.policy_revision == "policy-v1"
            assert snapshot.source_availability_snapshot == {"github": "healthy"}

        async with factory() as session:
            loaded = await InvestigationSnapshotService().get(session, snapshot.snapshot_id)
            assert loaded == snapshot
    finally:
        await engine.dispose()
