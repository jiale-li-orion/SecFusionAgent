from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.execution.recovery import recover_queued_role_tasks
from packages.runtime.execution.service import ExecutionRunService
from packages.shared.db import Base
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    ExecutionProfile,
    TaskContract,
    TaskEventType,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import TaskEventDeliveryModel, TaskEventModel
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_run,
    list_task_events,
    transition_task_run,
)

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:role-recovery-test"


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _queued_role(factory, *, deadline_at: datetime, queued_at: datetime) -> str:
    run_id = str(uuid4())
    contract = TaskContract(
        task_contract_id=f"recover:{run_id}",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
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
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref="InvestigationRole@1",
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
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{run_id}",
            stream_name=STREAM,
            run_id=run_id,
            now=queued_at,
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref="queue:test",
            idempotency_key=f"queue:{run_id}",
            stream_name=STREAM,
            now=queued_at,
        )
        await ExecutionRunService(now=lambda: queued_at).create(
            session,
            ExecutionEnvelope(
                execution_id=f"execution:{run_id}",
                task_contract_id=contract.task_contract_id,
                task_run_id=run_id,
                role_revision="InvestigationRole@1",
                context_manifest_revision=1,
                execution_profile=ExecutionProfile.VERIFY,
                deadline_at=deadline_at,
                budget_ref=f"budget:{run_id}",
                policy_revision="policy-v1",
                network_policy="proxied",
                side_effect_policy="internal-state",
                sandbox_profile_revision="process_restricted@1",
            ),
        )
        # The original event reached the scheduler, but its Celery delivery was lost.
        for delivery in await session.scalars(select(TaskEventDeliveryModel)):
            delivery.status = "delivered"
            delivery.delivered_at = queued_at
    return run_id


@pytest.mark.asyncio
async def test_stale_queued_role_emits_one_durable_dispatch_retry() -> None:
    engine, factory = await _database()
    try:
        run_id = await _queued_role(
            factory,
            deadline_at=NOW + timedelta(hours=1),
            queued_at=NOW - timedelta(minutes=10),
        )
        async with factory() as session, session.begin():
            assert await recover_queued_role_tasks(
                session, now=NOW, stale_seconds=300, stream_name=STREAM
            ) == ([run_id], [])
        async with factory() as session, session.begin():
            assert await recover_queued_role_tasks(
                session,
                now=NOW + timedelta(minutes=1),
                stale_seconds=300,
                stream_name=STREAM,
            ) == ([], [])
        async with factory() as session:
            events = await list_task_events(session, run_id)
            recovery = events[-1]
            delivery = await session.get(TaskEventDeliveryModel, recovery.event_id)
        assert recovery.event_type is TaskEventType.PROGRESS
        assert recovery.payload_ref == f"role-dispatch-recovery:{run_id}"
        assert delivery is not None and delivery.status == "pending"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_queued_role_times_out_instead_of_dispatching() -> None:
    engine, factory = await _database()
    try:
        run_id = await _queued_role(
            factory,
            deadline_at=NOW - timedelta(minutes=1),
            queued_at=NOW - timedelta(minutes=10),
        )
        async with factory() as session, session.begin():
            assert await recover_queued_role_tasks(
                session, now=NOW, stale_seconds=300, stream_name=STREAM
            ) == ([], [run_id])
        async with factory() as session:
            run = await get_task_run(session, run_id)
            events = await list_task_events(session, run_id)
            recovery_events = list(
                await session.scalars(
                    select(TaskEventModel).where(
                        TaskEventModel.task_run_id == run_id,
                        TaskEventModel.payload_ref.like("role-dispatch-recovery:%"),
                    )
                )
            )
        assert run.status is TaskRunStatus.TIMED_OUT
        assert run.stop_reason == "deadline_reached_before_start"
        assert events[-1].event_type is TaskEventType.TASK_FAILED
        assert recovery_events == []
    finally:
        await engine.dispose()
