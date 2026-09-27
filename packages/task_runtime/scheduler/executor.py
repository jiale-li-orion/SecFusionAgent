from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.storage.service import (
    claim_queued_task_run,
    get_task_run,
    transition_task_run,
)

RoleRunHandler = Callable[[str], Awaitable[object]]


class RoleDispatchDisposition(StrEnum):
    EXECUTED = "executed"
    NOT_QUEUED = "not_queued"
    UNSUPPORTED_ROLE = "unsupported_role"


class RoleDispatchResult(BaseModel):
    run_id: str
    role_id: str
    disposition: RoleDispatchDisposition
    final_status: TaskRunStatus


class QueuedRoleExecutor:
    """Claim queued TaskRuns once and dispatch them to injected Role handlers."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        handlers: dict[str, RoleRunHandler],
        *,
        stream_name: str = "secfusion:task-events",
    ) -> None:
        self._session_factory = session_factory
        self._handlers = dict(handlers)
        self._stream_name = stream_name

    async def execute(self, run_id: str) -> RoleDispatchResult:
        async with self._session_factory() as session:
            run = await get_task_run(session, run_id)
        handler = self._handlers.get(run.role_id)
        if handler is None:
            return RoleDispatchResult(
                run_id=run_id,
                role_id=run.role_id,
                disposition=RoleDispatchDisposition.UNSUPPORTED_ROLE,
                final_status=run.status,
            )

        async with self._session_factory() as session, session.begin():
            claimed = await claim_queued_task_run(
                session,
                run_id=run_id,
                stream_name=self._stream_name,
            )
        if claimed is None:
            async with self._session_factory() as session:
                current = await get_task_run(session, run_id)
            return RoleDispatchResult(
                run_id=run_id,
                role_id=current.role_id,
                disposition=RoleDispatchDisposition.NOT_QUEUED,
                final_status=current.status,
            )

        try:
            await handler(run_id)
        except Exception as exc:
            async with self._session_factory() as session, session.begin():
                current = await get_task_run(session, run_id)
                if current.status is TaskRunStatus.RUNNING:
                    error_type = type(exc).__name__
                    await transition_task_run(
                        session,
                        run_id=run_id,
                        target=TaskRunStatus.FAILED,
                        payload_ref=f"role-executor-error:{error_type}",
                        idempotency_key=f"role-executor-failed:{run_id}:{error_type}",
                        stream_name=self._stream_name,
                        producer="task-runtime-executor",
                        stop_reason=f"role_executor_error:{error_type}",
                    )
            raise
        async with self._session_factory() as session:
            final = await get_task_run(session, run_id)
        return RoleDispatchResult(
            run_id=run_id,
            role_id=claimed.role_id,
            disposition=RoleDispatchDisposition.EXECUTED,
            final_status=final.status,
        )
