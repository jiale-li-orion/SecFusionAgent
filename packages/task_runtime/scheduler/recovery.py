from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.storage.models import ExecutionRunModel
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import TaskEventType, TaskRunStatus
from packages.task_runtime.storage.models import (
    TaskEventDeliveryModel,
    TaskEventModel,
    TaskRunModel,
)
from packages.task_runtime.storage.service import append_task_event, transition_task_run

DISPATCHED_ROLES = ("EnrichmentRole", "InvestigationRole")


async def recover_queued_role_tasks(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    stale_seconds: int = 300,
    limit: int = 100,
    stream_name: str = "secfusion:task-events",
) -> tuple[list[str], list[str]]:
    """Retry lost Role dispatches and close queued tasks past their deadline.

    Retries append a durable event through the normal task-event outbox. A queued
    Role is never executed inline by the scheduler, and the worker's row-lock
    claim remains the authority for duplicate Celery deliveries.
    """
    if stale_seconds < 1 or limit < 1:
        raise ValueError("role recovery bounds must be positive")
    instant = now or datetime.now(UTC)
    threshold = instant - timedelta(seconds=stale_seconds)
    runs = list(
        await session.scalars(
            select(TaskRunModel)
            .where(
                TaskRunModel.status == TaskRunStatus.QUEUED.value,
                TaskRunModel.role_id.in_(DISPATCHED_ROLES),
                TaskRunModel.updated_at <= threshold,
            )
            .order_by(TaskRunModel.updated_at, TaskRunModel.run_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    retried: list[str] = []
    closed: list[str] = []
    execution_service = ExecutionRunService(now=lambda: instant)
    for run in runs:
        execution = await session.get(ExecutionRunModel, run.execution_envelope_ref)
        envelope: ExecutionEnvelope | None = None
        if execution is not None:
            try:
                envelope = ExecutionEnvelope.model_validate(execution.envelope_json)
            except ValidationError:
                pass
        if envelope is None or envelope.task_run_id != run.run_id:
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.BLOCKED,
                payload_ref="role-recovery:execution-envelope-unavailable",
                idempotency_key=f"role-recovery:invalid-execution:{run.run_id}",
                stream_name=stream_name,
                producer="task-runtime-recovery",
                stop_reason="execution_envelope_unavailable",
                now=instant,
            )
            if execution is not None and execution.status in {"created", "running"}:
                await execution_service.finish(
                    session,
                    execution.execution_id,
                    status="blocked",
                    stop_reason="execution_envelope_unavailable",
                )
            closed.append(run.run_id)
            continue
        if envelope.deadline_at <= instant:
            await transition_task_run(
                session,
                run_id=run.run_id,
                target=TaskRunStatus.TIMED_OUT,
                payload_ref="role-recovery:deadline-before-start",
                idempotency_key=f"role-recovery:deadline:{run.run_id}",
                stream_name=stream_name,
                producer="task-runtime-recovery",
                stop_reason="deadline_reached_before_start",
                now=instant,
            )
            if execution is not None and execution.status in {"created", "running"}:
                await execution_service.finish(
                    session,
                    execution.execution_id,
                    status="timed_out",
                    stop_reason="deadline_reached_before_start",
                )
            closed.append(run.run_id)
            continue

        last_dispatch_event = await session.scalar(
            select(TaskEventModel)
            .where(
                TaskEventModel.task_run_id == run.run_id,
                (TaskEventModel.event_type == TaskEventType.TASK_PATCHED.value)
                | TaskEventModel.payload_ref.like("role-dispatch-recovery:%"),
            )
            .order_by(TaskEventModel.emitted_at.desc(), TaskEventModel.seq.desc())
            .limit(1)
        )
        if last_dispatch_event is not None:
            delivery = await session.get(TaskEventDeliveryModel, last_dispatch_event.event_id)
            if delivery is not None and delivery.status == "pending":
                continue
            emitted_at = last_dispatch_event.emitted_at
            if emitted_at.tzinfo is None:
                emitted_at = emitted_at.replace(tzinfo=UTC)
            if emitted_at > threshold:
                continue
            if delivery is not None and delivery.delivered_at is not None:
                delivered_at = delivery.delivered_at
                if delivered_at.tzinfo is None:
                    delivered_at = delivered_at.replace(tzinfo=UTC)
                if delivered_at > threshold:
                    continue
        await append_task_event(
            session,
            task_run_id=run.run_id,
            event_type=TaskEventType.PROGRESS,
            producer="task-runtime-recovery",
            base_context_revision=run.context_revision,
            payload_ref=f"role-dispatch-recovery:{run.run_id}",
            idempotency_key=(
                f"role-dispatch-recovery:{run.run_id}:{int(instant.timestamp()) // stale_seconds}"
            ),
            stream_name=stream_name,
            now=instant,
        )
        retried.append(run.run_id)
    return retried, closed
