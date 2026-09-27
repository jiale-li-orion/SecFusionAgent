from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.storage.models import ExecutionRunModel
from packages.task_runtime.contracts.execution import ExecutionEnvelope


class ExecutionRunService:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def create(
        self,
        session: AsyncSession,
        envelope: ExecutionEnvelope,
    ) -> ExecutionEnvelope:
        existing = await session.get(ExecutionRunModel, envelope.execution_id)
        payload = envelope.model_dump(mode="json")
        if existing is not None:
            if existing.envelope_json != payload:
                raise ValueError("ExecutionEnvelope identity is immutable")
            return ExecutionEnvelope.model_validate(existing.envelope_json)
        if envelope.parent_execution_id is not None:
            parent = await session.get(ExecutionRunModel, envelope.parent_execution_id)
            if parent is None:
                raise LookupError(f"parent execution not found: {envelope.parent_execution_id}")
        model = ExecutionRunModel(
            execution_id=envelope.execution_id,
            parent_execution_id=envelope.parent_execution_id,
            task_run_id=envelope.task_run_id,
            envelope_json=payload,
            status="created",
            created_at=self._now(),
        )
        session.add(model)
        await session.flush()
        return envelope

    async def get(self, session: AsyncSession, execution_id: str) -> ExecutionEnvelope:
        model = await session.get(ExecutionRunModel, execution_id)
        if model is None:
            raise LookupError(f"execution run not found: {execution_id}")
        return ExecutionEnvelope.model_validate(model.envelope_json)

    async def start(self, session: AsyncSession, execution_id: str) -> ExecutionEnvelope:
        model = await self._lock(session, execution_id)
        if model.status == "running":
            return ExecutionEnvelope.model_validate(model.envelope_json)
        if model.status != "created":
            raise ValueError(f"cannot start execution status={model.status}")
        model.status = "running"
        model.started_at = self._now()
        await session.flush()
        return ExecutionEnvelope.model_validate(model.envelope_json)

    async def finish(
        self,
        session: AsyncSession,
        execution_id: str,
        *,
        status: str,
        stop_reason: str,
    ) -> None:
        if status not in {"completed", "failed", "cancelled", "timed_out", "blocked"}:
            raise ValueError("invalid terminal execution status")
        model = await self._lock(session, execution_id)
        if model.status == status and model.finished_at is not None:
            return
        if model.status not in {"created", "running"}:
            raise ValueError(f"execution already terminal: {model.status}")
        model.status = status
        model.stop_reason = stop_reason
        model.finished_at = self._now()
        await session.flush()

    async def _lock(self, session: AsyncSession, execution_id: str) -> ExecutionRunModel:
        model = await session.scalar(
            select(ExecutionRunModel)
            .where(ExecutionRunModel.execution_id == execution_id)
            .with_for_update()
        )
        if model is None:
            raise LookupError(f"execution run not found: {execution_id}")
        return model
