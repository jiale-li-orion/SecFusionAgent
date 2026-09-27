from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from packages.shared.config import get_settings
from packages.shared.db import create_engine, create_session_factory
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
from packages.task_runtime.events.redis_stream import (
    ack_task_event_message,
    dispatch_pending_task_events,
    read_task_event_messages,
)
from packages.task_runtime.scheduler import DependencyWakeDisposition, DependencyWakeScheduler
from packages.task_runtime.storage.models import (
    ContextManifestVersionModel,
    TaskContractVersionModel,
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import (
    append_task_event,
    create_task_run,
    get_task_event,
    get_task_run,
    list_task_events,
    transition_task_run,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SECFUSION_RUN_INTEGRATION") != "1",
        reason="set SECFUSION_RUN_INTEGRATION=1 to run local infrastructure tests",
    ),
]

NOW = datetime(2026, 9, 27, 1, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_real_postgres_task_runtime_and_redis_stream_roundtrip() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    suffix = uuid4().hex
    task_id = f"verify-{suffix}"
    context_id = f"context-{suffix}"
    run_id = str(uuid4())
    stream = f"{settings.task_event_stream_name}:integration:{suffix}"
    contract = TaskContract(
        task_contract_id=task_id,
        contract_revision=1,
        principal="integration:user",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["repo:vllm-project/vllm"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={"required_source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"freshness": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.READ_ONLY,
        ),
        completion_predicate={"any": ["evidence_sufficient", "conflict", "blocked"]},
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id=context_id,
        context_revision=1,
        task_contract_ref=f"{task_id}@1",
        role_ref="InvestigationRole@1",
        knowledge_revision=1,
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability-view:v1",
        budget_ref="budget:integration",
    )
    try:
        await redis.delete(stream)
        async with factory() as session, session.begin():
            run = await create_task_run(
                session,
                contract=contract,
                manifest=manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref="execution:integration",
                stream_name=stream,
                run_id=run_id,
                now=NOW,
            )
            assert run.status is TaskRunStatus.SUBMITTED

        async with factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:integration",
                idempotency_key="queue:1",
                stream_name=stream,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="execution:integration",
                idempotency_key="start:1",
                stream_name=stream,
                now=NOW,
            )
            progress = await append_task_event(
                session,
                task_run_id=run_id,
                event_type=TaskEventType.PROGRESS,
                producer="integration",
                base_context_revision=1,
                payload_ref="progress:integration",
                idempotency_key="progress:1",
                stream_name=stream,
                now=NOW,
            )
            replay = await append_task_event(
                session,
                task_run_id=run_id,
                event_type=TaskEventType.PROGRESS,
                producer="integration",
                base_context_revision=1,
                payload_ref="progress:integration",
                idempotency_key="progress:1",
                stream_name=stream,
                now=NOW,
            )
            assert replay.replay is True
            assert replay.event.event_id == progress.event.event_id
            await transition_task_run(
                session,
                run_id=run_id,
                target=TaskRunStatus.COMPLETED,
                payload_ref="result:integration",
                idempotency_key="complete:1",
                stream_name=stream,
                result_ref="result:integration",
                stop_reason="goal_satisfied",
                now=NOW,
            )

        async with factory() as session, session.begin():
            delivered = await dispatch_pending_task_events(session, redis, now=NOW)
            assert delivered == 5

        messages = await redis.xrange(stream)
        assert len(messages) == 5
        assert [fields["seq"] for _, fields in messages] == ["1", "2", "3", "4", "5"]
        assert [fields["event_type"] for _, fields in messages] == [
            TaskEventType.TASK_CREATED.value,
            TaskEventType.TASK_PATCHED.value,
            TaskEventType.TASK_STARTED.value,
            TaskEventType.PROGRESS.value,
            TaskEventType.TASK_COMPLETED.value,
        ]

        async with factory() as session:
            events = await list_task_events(session, run_id)
            assert [event.seq for event in events] == [1, 2, 3, 4, 5]
            model = await session.get(TaskRunModel, run_id)
            assert model is not None
            assert model.status == TaskRunStatus.COMPLETED.value
            deliveries = list(
                await session.scalars(
                    select(TaskEventDeliveryModel)
                    .join(
                        TaskEventModel, TaskEventModel.event_id == TaskEventDeliveryModel.event_id
                    )
                    .where(TaskEventModel.task_run_id == run_id)
                )
            )
            assert len(deliveries) == 5
            assert {item.status for item in deliveries} == {"delivered"}
            assert all(item.redis_message_id for item in deliveries)

        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="terminal task run is immutable"):
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.RUNNING,
                    payload_ref="illegal",
                    idempotency_key="illegal",
                    stream_name=stream,
                    now=NOW,
                )
    finally:
        async with factory() as session, session.begin():
            event_ids = list(
                await session.scalars(
                    select(TaskEventModel.event_id).where(TaskEventModel.task_run_id == run_id)
                )
            )
            if event_ids:
                await session.execute(
                    delete(TaskEventDeliveryModel).where(
                        TaskEventDeliveryModel.event_id.in_(event_ids)
                    )
                )
            await session.execute(
                delete(TaskEventModel).where(TaskEventModel.task_run_id == run_id)
            )
            await session.execute(delete(TaskRunModel).where(TaskRunModel.run_id == run_id))
            context_versions = list(
                await session.scalars(
                    select(ContextManifestVersionModel.context_manifest_version_id).where(
                        ContextManifestVersionModel.context_id == context_id
                    )
                )
            )
            if context_versions:
                await session.execute(
                    delete(ContextManifestVersionModel).where(
                        ContextManifestVersionModel.context_manifest_version_id.in_(
                            context_versions
                        )
                    )
                )
            await session.execute(
                delete(TaskContractVersionModel).where(
                    TaskContractVersionModel.task_contract_id == task_id
                )
            )
        await redis.delete(stream)
        await redis.aclose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_task_bus_dependency_wake_and_replay_are_idempotent() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_task_bus_url, decode_responses=True)
    suffix = uuid4().hex
    parent_id = str(uuid4())
    child_id = str(uuid4())
    parent_task_id = f"verify-wake-{suffix}"
    child_task_id = f"enrichment-wake-{suffix}"
    parent_context_id = f"context-parent-wake-{suffix}"
    child_context_id = f"context-child-wake-{suffix}"
    stream = f"{settings.task_event_stream_name}:wake-integration:{suffix}"
    group = f"task-scheduler:{suffix}"
    parent_contract = TaskContract(
        task_contract_id=parent_task_id,
        contract_revision=1,
        principal="integration:user",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["object:vuln-wake"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={"required_source_roles": ["primary"]},
        output_contract={"format": "decision"},
        temporal_contract={"freshness": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(
            allowed=True,
            max_depth=1,
            allowed_task_kinds=[TaskKind.ENRICHMENT],
            child_effect_ceiling=EffectCeiling.INTERNAL_STATE,
        ),
        completion_predicate={"any": ["evidence_sufficient", "blocked"]},
        policy_revision="policy-v1",
    )
    child_contract = TaskContract(
        task_contract_id=child_task_id,
        contract_revision=1,
        principal="integration:user",
        on_behalf_of=parent_id,
        task_kind=TaskKind.ENRICHMENT,
        target_resources=["object:vuln-wake"],
        desired_state={"required_dimensions": ["fix_remediation"]},
        evidence_contract={"fact_authority": "m1_m3_evidence_world"},
        output_contract={"result_type": "EnrichmentTaskResult"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.INTERNAL_STATE,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "enrichment_dimensions_terminal"},
        policy_revision="policy-v1",
    )
    parent_manifest = ContextManifest(
        context_id=parent_context_id,
        context_revision=1,
        task_contract_ref=f"{parent_task_id}@1",
        role_ref="InvestigationRole@1",
        knowledge_revision=1,
        object_refs=["vuln-wake"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:verify:wake",
        budget_ref=f"budget:{parent_id}",
    )
    child_manifest = ContextManifest(
        context_id=child_context_id,
        context_revision=1,
        parent_context_id=parent_context_id,
        task_contract_ref=f"{child_task_id}@1",
        role_ref="EnrichmentRole@1",
        knowledge_revision=1,
        object_refs=["vuln-wake"],
        policy_context_ref="policy-context:v1",
        capability_envelope_ref="capability:enrichment:wake",
        budget_ref=f"budget:{child_id}",
    )
    scheduler = DependencyWakeScheduler(stream_name=stream, now=lambda: NOW)
    try:
        await redis.delete(stream)
        async with factory() as session, session.begin():
            await create_task_run(
                session,
                contract=parent_contract,
                manifest=parent_manifest,
                role=canonical_roles()["InvestigationRole"],
                execution_envelope_ref=f"execution:{parent_id}",
                stream_name=stream,
                run_id=parent_id,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:parent",
                idempotency_key="queue:parent",
                stream_name=stream,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="start:parent",
                idempotency_key="start:parent",
                stream_name=stream,
                now=NOW,
            )
            await create_task_run(
                session,
                contract=child_contract,
                manifest=child_manifest,
                role=canonical_roles()["EnrichmentRole"],
                execution_envelope_ref=f"execution:{child_id}",
                stream_name=stream,
                parent_run_id=parent_id,
                run_id=child_id,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=child_id,
                target=TaskRunStatus.QUEUED,
                payload_ref="queue:child",
                idempotency_key="queue:child",
                stream_name=stream,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=child_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="start:child",
                idempotency_key="start:child",
                stream_name=stream,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent_id,
                target=TaskRunStatus.WAITING_DEPENDENCY,
                payload_ref="wait:parent",
                idempotency_key="wait:parent",
                stream_name=stream,
                stop_reason=task_dependency_reason(child_id),
                now=NOW,
            )
            changed = await append_task_event(
                session,
                task_run_id=child_id,
                event_type=TaskEventType.ENRICHMENT_STATE_CHANGED,
                producer="EnrichmentRole",
                base_context_revision=1,
                payload_ref="enrichment-state:vuln-wake@2",
                idempotency_key="enrichment-state:wake",
                stream_name=stream,
                now=NOW,
            )

        async with factory() as session, session.begin():
            delivered = await dispatch_pending_task_events(session, redis, now=NOW)
            assert delivered == 8

        messages = await read_task_event_messages(
            redis,
            stream_name=stream,
            group_name=group,
            consumer_name="integration-consumer-a",
            claim_idle_ms=0,
            block_ms=None,
        )
        dispositions: list[DependencyWakeDisposition] = []
        for message in messages:
            async with factory() as session, session.begin():
                event = await get_task_event(session, message.event_id)
                result = await scheduler.process_event(session, event)
                dispositions.append(result.disposition)
            assert (
                await ack_task_event_message(
                    redis,
                    stream_name=stream,
                    group_name=group,
                    message_id=message.message_id,
                )
                == 1
            )
        assert dispositions.count(DependencyWakeDisposition.QUEUED) == 1
        async with factory() as session:
            parent = await get_task_run(session, parent_id)
            assert parent.status is TaskRunStatus.QUEUED

        async with factory() as session, session.begin():
            await transition_task_run(
                session,
                run_id=parent_id,
                target=TaskRunStatus.RUNNING,
                payload_ref="resume:parent",
                idempotency_key="resume:parent",
                stream_name=stream,
                now=NOW,
            )
            await transition_task_run(
                session,
                run_id=parent_id,
                target=TaskRunStatus.WAITING_DEPENDENCY,
                payload_ref="wait:parent:again",
                idempotency_key="wait:parent:again",
                stream_name=stream,
                stop_reason=task_dependency_reason(child_id),
                now=NOW,
            )
        await redis.xadd(
            stream,
            {
                "event_id": changed.event.event_id,
                "task_run_id": child_id,
                "parent_run_id": parent_id,
                "event_type": TaskEventType.ENRICHMENT_STATE_CHANGED.value,
            },
        )
        replay_messages = await read_task_event_messages(
            redis,
            stream_name=stream,
            group_name=group,
            consumer_name="integration-consumer-b",
            claim_idle_ms=0,
            block_ms=None,
        )
        assert len(replay_messages) == 1
        async with factory() as session, session.begin():
            replay_event = await get_task_event(session, replay_messages[0].event_id)
            replay_result = await scheduler.process_event(session, replay_event)
            assert replay_result.disposition is DependencyWakeDisposition.REPLAY
            parent = await get_task_run(session, parent_id)
            assert parent.status is TaskRunStatus.WAITING_DEPENDENCY
    finally:
        async with factory() as session, session.begin():
            run_ids = [parent_id, child_id]
            event_ids = list(
                await session.scalars(
                    select(TaskEventModel.event_id).where(TaskEventModel.task_run_id.in_(run_ids))
                )
            )
            if event_ids:
                await session.execute(
                    delete(TaskEventDeliveryModel).where(
                        TaskEventDeliveryModel.event_id.in_(event_ids)
                    )
                )
            await session.execute(
                delete(TaskEventModel).where(TaskEventModel.task_run_id.in_(run_ids))
            )
            await session.execute(delete(TaskRunModel).where(TaskRunModel.run_id.in_(run_ids)))
            await session.execute(
                delete(ContextManifestVersionModel).where(
                    ContextManifestVersionModel.context_id.in_(
                        [parent_context_id, child_context_id]
                    )
                )
            )
            await session.execute(
                delete(TaskContractVersionModel).where(
                    TaskContractVersionModel.task_contract_id.in_([parent_task_id, child_task_id])
                )
            )
        await redis.delete(stream)
        await redis.aclose()
        await engine.dispose()
