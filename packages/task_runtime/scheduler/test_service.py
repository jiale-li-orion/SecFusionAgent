from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.shared.db import Base
from packages.task_runtime.contracts.dependencies import task_dependency_reason
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
from packages.task_runtime.scheduler.service import (
    DependencyWakeDisposition,
    DependencyWakeScheduler,
)
from packages.task_runtime.storage.service import (
    append_task_event,
    create_task_run,
    get_task_run,
    list_task_events,
    transition_task_run,
)

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
STREAM = "secfusion:task-events:scheduler-test"
PARENT_ID = "00000000-0000-0000-0000-000000008001"
CHILD_ID = "00000000-0000-0000-0000-000000008002"
OTHER_CHILD_ID = "00000000-0000-0000-0000-000000008003"


def _contract(task_id: str, task_kind: TaskKind, *, parent: bool = False) -> TaskContract:
    return TaskContract(
        task_contract_id=task_id,
        contract_revision=1,
        principal="user:test",
        task_kind=task_kind,
        target_resources=["object:vuln-1"],
        desired_state={"predicate": "resolved"},
        evidence_contract={},
        output_contract={"type": "test"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=(
            DelegationCeiling(
                allowed=True,
                max_depth=1,
                allowed_task_kinds=[TaskKind.ENRICHMENT],
                child_effect_ceiling=EffectCeiling.INTERNAL_STATE,
            )
            if parent
            else DelegationCeiling()
        ),
        completion_predicate={"type": "test"},
        policy_revision="policy-v1",
    )


def _manifest(contract: TaskContract, *, context_id: str, role_ref: str) -> ContextManifest:
    return ContextManifest(
        context_id=context_id,
        context_revision=1,
        task_contract_ref=f"{contract.task_contract_id}@1",
        role_ref=role_ref,
        knowledge_revision=1,
        object_refs=["vuln-1"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref=f"capability:{context_id}",
        budget_ref=f"budget:{context_id}",
    )


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _running_parent_with_children(factory):
    parent_contract = _contract("parent-verify", TaskKind.VERIFY_VERSION_FIX, parent=True)
    parent_manifest = _manifest(
        parent_contract,
        context_id="context-parent",
        role_ref="InvestigationRole@1",
    )
    child_contract = _contract("child-enrichment", TaskKind.ENRICHMENT)
    child_manifest = _manifest(
        child_contract,
        context_id="context-child",
        role_ref="EnrichmentRole@1",
    )
    other_contract = _contract("other-child-enrichment", TaskKind.ENRICHMENT)
    other_manifest = _manifest(
        other_contract,
        context_id="context-other-child",
        role_ref="EnrichmentRole@1",
    )
    async with factory() as session, session.begin():
        await create_task_run(
            session,
            contract=parent_contract,
            manifest=parent_manifest,
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{PARENT_ID}",
            stream_name=STREAM,
            run_id=PARENT_ID,
            now=NOW,
        )
        await transition_task_run(
            session,
            run_id=PARENT_ID,
            target=TaskRunStatus.QUEUED,
            payload_ref="queue:parent",
            idempotency_key="queue:parent",
            stream_name=STREAM,
            now=NOW,
        )
        await transition_task_run(
            session,
            run_id=PARENT_ID,
            target=TaskRunStatus.RUNNING,
            payload_ref="start:parent",
            idempotency_key="start:parent",
            stream_name=STREAM,
            now=NOW,
        )
        for child_id, contract, manifest in (
            (CHILD_ID, child_contract, child_manifest),
            (OTHER_CHILD_ID, other_contract, other_manifest),
        ):
            await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["EnrichmentRole"],
                execution_envelope_ref=f"execution:{child_id}",
                stream_name=STREAM,
                parent_run_id=PARENT_ID,
                run_id=child_id,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=child_id,
                target=TaskRunStatus.QUEUED,
                payload_ref=f"queue:{child_id}",
                idempotency_key=f"queue:{child_id}",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=child_id,
                target=TaskRunStatus.RUNNING,
                payload_ref=f"start:{child_id}",
                idempotency_key=f"start:{child_id}",
                stream_name=STREAM,
                now=NOW,
            )
        await transition_task_run(
            session,
            run_id=PARENT_ID,
            target=TaskRunStatus.WAITING_DEPENDENCY,
            payload_ref="wait:parent",
            idempotency_key="wait:parent",
            stream_name=STREAM,
            stop_reason=task_dependency_reason(CHILD_ID),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_dependency_scheduler_only_wakes_declared_child_on_relevant_event() -> None:
    engine, factory = await _database()
    scheduler = DependencyWakeScheduler(stream_name=STREAM, now=lambda: NOW)
    try:
        await _running_parent_with_children(factory)
        async with factory() as session, session.begin():
            progress = await append_task_event(
                session,
                task_run_id=CHILD_ID,
                event_type=TaskEventType.PROGRESS,
                producer="EnrichmentRole",
                base_context_revision=1,
                payload_ref="enrichment-attempt:test",
                idempotency_key="progress:child",
                stream_name=STREAM,
                now=NOW,
            )
            unrelated = await append_task_event(
                session,
                task_run_id=OTHER_CHILD_ID,
                event_type=TaskEventType.ENRICHMENT_STATE_CHANGED,
                producer="EnrichmentRole",
                base_context_revision=1,
                payload_ref="enrichment-state:vuln-1@2",
                idempotency_key="state:other-child",
                stream_name=STREAM,
                now=NOW,
            )
            relevant = await append_task_event(
                session,
                task_run_id=CHILD_ID,
                event_type=TaskEventType.ENRICHMENT_STATE_CHANGED,
                producer="EnrichmentRole",
                base_context_revision=1,
                payload_ref="enrichment-state:vuln-1@2",
                idempotency_key="state:child",
                stream_name=STREAM,
                now=NOW,
            )

        async with factory() as session, session.begin():
            progress_result = await scheduler.process_event(session, progress.event)
            unrelated_result = await scheduler.process_event(session, unrelated.event)
            assert progress_result.disposition is DependencyWakeDisposition.IRRELEVANT_EVENT
            assert unrelated_result.disposition is DependencyWakeDisposition.DIFFERENT_DEPENDENCY
            parent_before_wake = await get_task_run(session, PARENT_ID)
            assert parent_before_wake.status is TaskRunStatus.WAITING_DEPENDENCY

            relevant_result = await scheduler.process_event(session, relevant.event)
            assert relevant_result.disposition is DependencyWakeDisposition.QUEUED
            parent = await get_task_run(session, PARENT_ID)
            assert parent.status is TaskRunStatus.QUEUED
            assert parent.stop_reason is None

        async with factory() as session:
            events = await list_task_events(session, PARENT_ID)
        wake_events = [
            event
            for event in events
            if event.producer == "task-runtime-scheduler"
            and event.payload_ref
            == f"dependency-wake:{CHILD_ID}:{TaskEventType.ENRICHMENT_STATE_CHANGED.value}"
        ]
        assert len(wake_events) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dependency_scheduler_dedupes_old_event_before_mutating_new_wait_state() -> None:
    engine, factory = await _database()
    scheduler = DependencyWakeScheduler(stream_name=STREAM, now=lambda: NOW)
    try:
        await _running_parent_with_children(factory)
        async with factory() as session, session.begin():
            changed = await append_task_event(
                session,
                task_run_id=CHILD_ID,
                event_type=TaskEventType.ENRICHMENT_STATE_CHANGED,
                producer="EnrichmentRole",
                base_context_revision=1,
                payload_ref="enrichment-state:vuln-1@2",
                idempotency_key="state:child:replay",
                stream_name=STREAM,
                now=NOW,
            )
            first = await scheduler.process_event(session, changed.event)
            assert first.disposition is DependencyWakeDisposition.QUEUED

        async with factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=PARENT_ID,
                target=TaskRunStatus.RUNNING,
                payload_ref="resume:parent",
                idempotency_key="resume:parent",
                stream_name=STREAM,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=PARENT_ID,
                target=TaskRunStatus.WAITING_DEPENDENCY,
                payload_ref="wait:parent:again",
                idempotency_key="wait:parent:again",
                stream_name=STREAM,
                stop_reason=task_dependency_reason(CHILD_ID),
                now=NOW,
            )
            replay = await scheduler.process_event(session, changed.event)
            assert replay.disposition is DependencyWakeDisposition.REPLAY
            parent = await get_task_run(session, PARENT_ID)
            assert parent.status is TaskRunStatus.WAITING_DEPENDENCY
            assert parent.stop_reason == task_dependency_reason(CHILD_ID)
    finally:
        await engine.dispose()
