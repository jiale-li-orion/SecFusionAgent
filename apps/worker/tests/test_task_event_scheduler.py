from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from apps.worker.task_event_scheduler import _role_dispatch_for_event
from packages.shared.db import Base
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import (
    create_task_run,
    list_task_events,
    transition_task_run,
)

NOW = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:worker-dispatch-test"


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _queued_run(factory, *, role_id: str) -> str:
    run_id = str(uuid4())
    task_kind = TaskKind.ENRICHMENT if role_id == "EnrichmentRole" else TaskKind.VERIFY_VERSION_FIX
    contract = TaskContract(
        task_contract_id=f"dispatch:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=task_kind,
        target_resources=["object:test"],
        desired_state={"test": True},
        evidence_contract={},
        output_contract={},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "test"},
        policy_revision="policy-v1",
    )
    role = canonical_roles()[role_id]
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref=f"{role.role_id}@{role.version}",
        knowledge_revision=1,
        object_refs=["test"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:test",
        budget_ref=f"budget:{run_id}",
    )
    async with factory() as session, session.begin():
        await create_task_run(
            session,
            contract=contract,
            manifest=manifest,
            role=role,
            execution_envelope_ref=f"execution:{run_id}",
            stream_name=STREAM,
            run_id=run_id,
            now=NOW,
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref="queue:test",
            idempotency_key=f"queue:{run_id}",
            stream_name=STREAM,
            now=NOW,
        )
    return run_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role_id", "task_name"),
    [
        ("EnrichmentRole", "secfusion.enrichment.run"),
        ("InvestigationRole", "secfusion.investigation.run"),
    ],
)
async def test_queued_role_taskpatched_event_maps_to_celery_task(
    role_id: str,
    task_name: str,
) -> None:
    engine, factory = await _database()
    try:
        run_id = await _queued_run(factory, role_id=role_id)
        async with factory() as session:
            events = await list_task_events(session, run_id)
            dispatch = await _role_dispatch_for_event(session, events[-1])
        assert dispatch == (task_name, run_id)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_old_queue_event_stops_dispatching_after_run_is_running() -> None:
    engine, factory = await _database()
    try:
        run_id = await _queued_run(factory, role_id="InvestigationRole")
        async with factory() as session, session.begin():
            events = await list_task_events(session, run_id)
            queued_event = events[-1]
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="start:test",
                idempotency_key=f"start:{run_id}",
                stream_name=STREAM,
                now=NOW,
            )
            dispatch = await _role_dispatch_for_event(session, queued_event)
        assert dispatch is None
    finally:
        await engine.dispose()
