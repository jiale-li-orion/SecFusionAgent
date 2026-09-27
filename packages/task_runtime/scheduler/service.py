from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.task_runtime.contracts.dependencies import dependency_run_id
from packages.task_runtime.contracts.models import TaskEvent, TaskEventType, TaskRunStatus
from packages.task_runtime.storage.models import TaskEventModel, TaskRunModel
from packages.task_runtime.storage.service import transition_task_run

DEPENDENCY_WAKE_EVENT_TYPES = frozenset(
    {
        TaskEventType.ENRICHMENT_STATE_CHANGED,
        TaskEventType.TASK_COMPLETED,
        TaskEventType.TASK_BLOCKED,
        TaskEventType.TASK_FAILED,
        TaskEventType.TASK_CANCELED,
    }
)


class DependencyWakeDisposition(StrEnum):
    QUEUED = "queued"
    REPLAY = "replay"
    IRRELEVANT_EVENT = "irrelevant_event"
    NO_PARENT = "no_parent"
    PARENT_NOT_WAITING = "parent_not_waiting"
    DIFFERENT_DEPENDENCY = "different_dependency"


class DependencyWakeResult(BaseModel):
    source_event_id: str
    child_run_id: str
    parent_run_id: str | None = None
    disposition: DependencyWakeDisposition

    @property
    def queued(self) -> bool:
        return self.disposition is DependencyWakeDisposition.QUEUED


class DependencyWakeScheduler:
    """Turn relevant child TaskEvents into idempotent parent wake transitions."""

    def __init__(
        self,
        *,
        stream_name: str = "secfusion:task-events",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._stream_name = stream_name
        self._now = now or (lambda: datetime.now(UTC))

    async def process_event(
        self,
        session: AsyncSession,
        event: TaskEvent,
    ) -> DependencyWakeResult:
        if event.event_type not in DEPENDENCY_WAKE_EVENT_TYPES:
            return self._result(event, DependencyWakeDisposition.IRRELEVANT_EVENT)
        if event.parent_run_id is None:
            return self._result(event, DependencyWakeDisposition.NO_PARENT)

        wake_key = _wake_idempotency_key(event.parent_run_id, event.event_id)
        prior_wake = await session.scalar(
            select(TaskEventModel.event_id).where(
                TaskEventModel.task_run_id == event.parent_run_id,
                TaskEventModel.idempotency_key == wake_key,
            )
        )
        if prior_wake is not None:
            return self._result(event, DependencyWakeDisposition.REPLAY)

        child = await session.get(TaskRunModel, event.task_run_id)
        if child is None or child.parent_run_id != event.parent_run_id:
            return self._result(event, DependencyWakeDisposition.NO_PARENT)

        parent = await session.scalar(
            select(TaskRunModel).where(TaskRunModel.run_id == event.parent_run_id).with_for_update()
        )
        if parent is None:
            return self._result(event, DependencyWakeDisposition.NO_PARENT)
        if TaskRunStatus(parent.status) is not TaskRunStatus.WAITING_DEPENDENCY:
            return self._result(event, DependencyWakeDisposition.PARENT_NOT_WAITING)
        if dependency_run_id(parent.stop_reason) != event.task_run_id:
            return self._result(event, DependencyWakeDisposition.DIFFERENT_DEPENDENCY)

        await transition_task_run(
            session,
            run_id=parent.run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref=f"dependency-wake:{event.task_run_id}:{event.event_type.value}",
            idempotency_key=wake_key,
            stream_name=self._stream_name,
            producer="task-runtime-scheduler",
            stop_reason=None,
            now=self._now(),
        )
        return self._result(event, DependencyWakeDisposition.QUEUED)

    @staticmethod
    def _result(event: TaskEvent, disposition: DependencyWakeDisposition) -> DependencyWakeResult:
        return DependencyWakeResult(
            source_event_id=event.event_id,
            child_run_id=event.task_run_id,
            parent_run_id=event.parent_run_id,
            disposition=disposition,
        )


def _wake_idempotency_key(parent_run_id: str, source_event_id: str) -> str:
    return f"dependency-wake:{parent_run_id}:{source_event_id}"
