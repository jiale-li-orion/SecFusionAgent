from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
from packages.task_runtime.scheduler.executor import (
    QueuedRoleExecutor,
    RoleDispatchDisposition,
)
from packages.task_runtime.storage.service import (
    create_task_run,
    get_task_run,
    list_task_events,
    transition_task_run,
)

NOW = datetime(2026, 9, 27, 16, 30, tzinfo=UTC)
STREAM = "secfusion:task-events:role-executor-test"


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _queued_run(factory, *, role_id: str = "InvestigationRole") -> str:
    run_id = str(uuid4())
    task_kind = (
        TaskKind.VERIFY_VERSION_FIX if role_id == "InvestigationRole" else TaskKind.ENRICHMENT
    )
    contract = TaskContract(
        task_contract_id=f"executor:{run_id}",
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
async def test_role_executor_claims_once_before_invoking_handler() -> None:
    engine, factory = await _database()
    calls: list[str] = []

    async def handler(run_id: str) -> None:
        calls.append(run_id)
        async with factory() as session, session.begin():
            run = await get_task_run(session, run_id)
            assert run.status is TaskRunStatus.RUNNING
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.COMPLETED,
                payload_ref="result:test",
                idempotency_key=f"complete:{run_id}",
                stream_name=STREAM,
                result_ref="result:test",
                stop_reason="test_complete",
                now=NOW,
            )

    try:
        run_id = await _queued_run(factory)
        executor = QueuedRoleExecutor(
            factory,
            {"InvestigationRole": handler},
            stream_name=STREAM,
        )
        first = await executor.execute(run_id)
        replay = await executor.execute(run_id)

        assert first.disposition is RoleDispatchDisposition.EXECUTED
        assert first.final_status is TaskRunStatus.COMPLETED
        assert replay.disposition is RoleDispatchDisposition.NOT_QUEUED
        assert replay.final_status is TaskRunStatus.COMPLETED
        assert calls == [run_id]

        async with factory() as session:
            events = await list_task_events(session, run_id)
        assert [event.event_type.value for event in events] == [
            "TaskCreated",
            "TaskPatched",
            "TaskStarted",
            "TaskCompleted",
        ]
        assert events[2].producer == "task-runtime-executor"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_role_executor_marks_claimed_run_failed_when_handler_crashes() -> None:
    engine, factory = await _database()

    async def handler(run_id: str) -> None:
        del run_id
        raise RuntimeError("composition failed")

    try:
        run_id = await _queued_run(factory)
        executor = QueuedRoleExecutor(
            factory,
            {"InvestigationRole": handler},
            stream_name=STREAM,
        )
        with pytest.raises(RuntimeError, match="composition failed"):
            await executor.execute(run_id)
        async with factory() as session:
            run = await get_task_run(session, run_id)
            events = await list_task_events(session, run_id)
        assert run.status is TaskRunStatus.FAILED
        assert run.stop_reason == "role_executor_error:RuntimeError"
        assert events[-1].event_type.value == "TaskFailed"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_role_executor_leaves_unsupported_role_queued() -> None:
    engine, factory = await _database()
    try:
        run_id = await _queued_run(factory, role_id="EnrichmentRole")
        result = await QueuedRoleExecutor(factory, {}, stream_name=STREAM).execute(run_id)
        assert result.disposition is RoleDispatchDisposition.UNSUPPORTED_ROLE
        assert result.final_status is TaskRunStatus.QUEUED
        async with factory() as session:
            run = await get_task_run(session, run_id)
        assert run.status is TaskRunStatus.QUEUED
    finally:
        await engine.dispose()
