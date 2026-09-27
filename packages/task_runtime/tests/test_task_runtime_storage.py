from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.shared.db import Base
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskEventType,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.events.redis_stream import dispatch_pending_task_events
from packages.task_runtime.storage.models import (
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import (
    append_task_event,
    create_task_run,
    list_task_events,
    persist_context_manifest,
    persist_task_contract,
    transition_task_run,
    update_task_context,
)

NOW = datetime(2026, 9, 27, 1, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:test"


def _contract(
    *,
    task_id: str = "verify-vllm-fix",
    revision: int = 1,
    kind: TaskKind = TaskKind.VERIFY_VERSION_FIX,
    effect: EffectCeiling = EffectCeiling.READ_ONLY,
    delegation: DelegationCeiling | None = None,
) -> TaskContract:
    return TaskContract(
        task_contract_id=task_id,
        contract_revision=revision,
        principal="user:alice",
        task_kind=kind,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={"required_source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"freshness": "current"},
        effect_ceiling=effect,
        delegation_ceiling=delegation or DelegationCeiling(),
        completion_predicate={"any": ["evidence_sufficient", "conflict", "blocked"]},
        policy_revision="policy-v1",
    )


def _manifest(
    contract: TaskContract, *, context_id: str = "context-root", revision: int = 1
) -> ContextManifest:
    role = (
        "EnrichmentRole@1" if contract.task_kind is TaskKind.ENRICHMENT else "InvestigationRole@1"
    )
    return ContextManifest(
        context_id=context_id,
        context_revision=revision,
        task_contract_ref=f"{contract.task_contract_id}@{contract.contract_revision}",
        role_ref=role,
        knowledge_revision=42,
        evidence_refs=["observation:seed"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability-view:v1",
        budget_ref="budget:root",
    )


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_task_contract_and_context_revision_are_immutable() -> None:
    engine, factory = await _database()
    contract = _contract()
    manifest = _manifest(contract)
    try:
        async with factory() as session, session.begin():
            first = await persist_task_contract(session, contract, now=NOW)
            replay = await persist_task_contract(session, contract, now=NOW)
            assert first.replay is False
            assert replay.replay is True
            first_context = await persist_context_manifest(session, manifest, now=NOW)
            replay_context = await persist_context_manifest(session, manifest, now=NOW)
            assert first_context.replay is False
            assert replay_context.replay is True

        changed_contract = contract.model_copy(update={"desired_state": {"predicate": "different"}})
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="task contract revision is immutable"):
                await persist_task_contract(session, changed_contract, now=NOW)

        changed_manifest = manifest.model_copy(update={"evidence_refs": ["observation:changed"]})
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="context manifest revision is immutable"):
                await persist_context_manifest(session, changed_manifest, now=NOW)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_context_patch_is_versioned_and_rejects_stale_or_unrelated_fork() -> None:
    engine, factory = await _database()
    contract = _contract()
    manifest = _manifest(contract)
    try:
        async with factory() as session, session.begin():
            run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:context",
                stream_name=STREAM,
                run_id="00000000-0000-0000-0000-000000000831",
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:context",
                idempotency_key="context:queued",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="execution:context",
                idempotency_key="context:running",
                stream_name=STREAM,
                now=NOW,
            )

        patched = manifest.model_copy(
            update={
                "context_revision": 2,
                "evidence_refs": ["observation:seed", "observation:new"],
                "budget_ref": "budget:patched",
            }
        )
        async with factory() as session, session.begin():
            updated = await update_task_context(
                session,
                run_id=run.run_id,
                manifest=patched,
                stream_name=STREAM,
                now=NOW,
            )
            assert updated.context_manifest_ref == "context-root@2"
            assert updated.base_context_revision == 2

        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="advance monotonically"):
                await update_task_context(
                    session,
                    run_id=run.run_id,
                    manifest=patched,
                    stream_name=STREAM,
                    now=NOW,
                )

        unrelated = patched.model_copy(
            update={
                "context_id": "unrelated-context",
                "context_revision": 1,
                "parent_context_id": "wrong-parent",
            }
        )
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="current context as parent_context_id"):
                await update_task_context(
                    session,
                    run_id=run.run_id,
                    manifest=unrelated,
                    stream_name=STREAM,
                    now=NOW,
                )

        forked = patched.model_copy(
            update={
                "context_id": "context-fork",
                "context_revision": 1,
                "parent_context_id": "context-root",
            }
        )
        async with factory() as session, session.begin():
            fork_result = await update_task_context(
                session,
                run_id=run.run_id,
                manifest=forked,
                stream_name=STREAM,
                now=NOW,
            )
            assert fork_result.context_manifest_ref == "context-fork@1"

        async with factory() as session:
            events = await list_task_events(session, run.run_id)
            context_events = [
                event for event in events if event.event_type is TaskEventType.CONTEXT_UPDATED
            ]
            assert [event.base_context_revision for event in context_events] == [2, 1]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_run_lifecycle_events_are_monotonic_idempotent_and_terminal_immutable() -> None:
    engine, factory = await _database()
    contract = _contract()
    manifest = _manifest(contract)
    role = canonical_roles()["InvestigationRole"]
    try:
        async with factory() as session, session.begin():
            run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=role,
                execution_envelope_ref="execution:root",
                stream_name=STREAM,
                run_id="00000000-0000-0000-0000-000000000801",
                now=NOW,
            )
            assert run.status is TaskRunStatus.SUBMITTED

        async with factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:default",
                idempotency_key="queued:1",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="execution:root",
                idempotency_key="started:1",
                stream_name=STREAM,
                now=NOW,
            )
            first = await append_task_event(
                session,
                task_run_id=run.run_id,
                event_type=TaskEventType.PROGRESS,
                producer="test",
                base_context_revision=1,
                payload_ref="progress:1",
                idempotency_key="progress:1",
                stream_name=STREAM,
                now=NOW,
            )
            replay = await append_task_event(
                session,
                task_run_id=run.run_id,
                event_type=TaskEventType.PROGRESS,
                producer="test",
                base_context_revision=1,
                payload_ref="progress:1",
                idempotency_key="progress:1",
                stream_name=STREAM,
                now=NOW,
            )
            assert replay.replay is True
            assert replay.event.event_id == first.event.event_id
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.COMPLETED,
                payload_ref="result:verified",
                idempotency_key="completed:1",
                stream_name=STREAM,
                result_ref="result:verified",
                stop_reason="goal_satisfied",
                now=NOW,
            )

        async with factory() as session:
            events = await list_task_events(session, run.run_id)
            assert [event.seq for event in events] == list(range(1, len(events) + 1))
            assert [event.event_type for event in events] == [
                TaskEventType.TASK_CREATED,
                TaskEventType.TASK_PATCHED,
                TaskEventType.TASK_STARTED,
                TaskEventType.PROGRESS,
                TaskEventType.TASK_COMPLETED,
            ]
            assert await session.scalar(select(func.count()).select_from(TaskEventModel)) == 5
            assert (
                await session.scalar(select(func.count()).select_from(TaskEventDeliveryModel)) == 5
            )
            model = await session.get(TaskRunModel, run.run_id)
            assert model is not None and model.status == TaskRunStatus.COMPLETED.value
            assert model.result_ref == "result:verified"

        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="terminal task run is immutable"):
                await transition_task_run(
                    session,
                    run_id=run.run_id,
                    target=TaskRunStatus.RUNNING,
                    payload_ref="illegal",
                    idempotency_key="illegal",
                    stream_name=STREAM,
                    now=NOW,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_child_task_enforces_parent_delegation_and_effect_ceiling() -> None:
    engine, factory = await _database()
    parent_contract = _contract(
        delegation=DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.READ_ONLY,
        )
    )
    parent_manifest = _manifest(parent_contract)
    parent_role = canonical_roles()["InvestigationRole"]
    try:
        async with factory() as session, session.begin():
            parent = await create_task_run(
                session,
                contract=parent_contract,
                manifest=parent_manifest,
                role=parent_role,
                execution_envelope_ref="execution:parent",
                stream_name=STREAM,
                run_id="00000000-0000-0000-0000-000000000811",
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent.run_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:default",
                idempotency_key="parent:queued",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent.run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="execution:parent",
                idempotency_key="parent:running",
                stream_name=STREAM,
                now=NOW,
            )

        child = _contract(
            task_id="child-enrichment",
            kind=TaskKind.ENRICHMENT,
            effect=EffectCeiling.READ_ONLY,
        )
        child_manifest = _manifest(child, context_id="context-child")
        child_role = canonical_roles()["EnrichmentRole"]
        async with factory() as session, session.begin():
            created = await create_task_run(
                session,
                contract=child,
                manifest=child_manifest,
                role=child_role,
                execution_envelope_ref="execution:child",
                stream_name=STREAM,
                parent_run_id=parent.run_id,
                run_id="00000000-0000-0000-0000-000000000812",
                now=NOW,
            )
            assert created.parent_run_id == parent.run_id

        elevated = _contract(
            task_id="child-elevated",
            kind=TaskKind.ENRICHMENT,
            effect=EffectCeiling.INTERNAL_STATE,
        )
        elevated_manifest = _manifest(elevated, context_id="context-child-elevated")
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="exceeds_parent_effect_ceiling"):
                await create_task_run(
                    session,
                    contract=elevated,
                    manifest=elevated_manifest,
                    role=child_role,
                    execution_envelope_ref="execution:child-elevated",
                    stream_name=STREAM,
                    parent_run_id=parent.run_id,
                    run_id="00000000-0000-0000-0000-000000000813",
                    now=NOW,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_event_delivery_uses_separate_redis_stream() -> None:
    engine, factory = await _database()
    redis = FakeRedis(decode_responses=False)
    contract = _contract()
    manifest = _manifest(contract)
    try:
        async with factory() as session, session.begin():
            run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:stream",
                stream_name=STREAM,
                run_id="00000000-0000-0000-0000-000000000821",
                now=NOW,
            )
        async with factory() as session, session.begin():
            delivered = await dispatch_pending_task_events(session, redis, now=NOW)
            assert delivered == 1
        messages = await redis.xrange(STREAM)
        assert len(messages) == 1
        fields = messages[0][1]
        assert fields[b"task_run_id"] == run.run_id.encode()
        assert fields[b"event_type"] == TaskEventType.TASK_CREATED.value.encode()
        assert fields[b"seq"] == b"1"

        async with factory() as session, session.begin():
            assert await dispatch_pending_task_events(session, redis, now=NOW) == 0
        assert len(await redis.xrange(STREAM)) == 1
    finally:
        await redis.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_task_event_publish_commit_gap_is_at_least_once_with_stable_event_identity() -> None:
    engine, factory = await _database()
    redis = FakeRedis(decode_responses=False)
    contract = _contract()
    manifest = _manifest(contract)
    try:
        async with factory() as session, session.begin():
            run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:commit-gap",
                stream_name=STREAM,
                run_id="00000000-0000-0000-0000-000000000841",
                now=NOW,
            )

        async with factory() as session:
            await session.begin()
            assert await dispatch_pending_task_events(session, redis, now=NOW) == 1
            await session.rollback()

        async with factory() as session, session.begin():
            assert await dispatch_pending_task_events(session, redis, now=NOW) == 1

        messages = await redis.xrange(STREAM)
        assert len(messages) == 2
        event_ids = [fields[b"event_id"] for _, fields in messages]
        idempotency_keys = [fields[b"idempotency_key"] for _, fields in messages]
        assert event_ids[0] == event_ids[1]
        assert idempotency_keys == [
            f"task-created:{run.run_id}".encode(),
            f"task-created:{run.run_id}".encode(),
        ]
    finally:
        await redis.aclose()
        await engine.dispose()
