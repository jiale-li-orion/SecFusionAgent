from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.monitoring.hot_window import HotWindowCollectionResult
from packages.monitoring.storage.mapper import source_state_from_model
from packages.monitoring.storage.models import AcquisitionRunModel, SourceStateModel
from packages.shared.storage.models import OutboxEventModel
from packages.sources.contracts import AcquisitionTrigger, SourceDefinition, SourceState
from packages.sources.errors import (
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)
from packages.sources.storage.mapper import source_definition_from_model
from packages.sources.storage.models import SourceModel

TERMINAL_STATUSES = frozenset(
    {
        "success",
        "no_change",
        "rate_limited",
        "auth_failed",
        "schema_changed",
        "fetch_failed",
        "internal_error",
    }
)


class AcquisitionContext(BaseModel):
    run_id: str
    trigger: AcquisitionTrigger
    source: SourceDefinition
    state: SourceState


class AcquisitionFailure(BaseModel):
    status: str
    error_code: str
    error_detail: str
    backoff_seconds: int


async def start_acquisition_run(
    session: AsyncSession,
    run_id: str,
    *,
    now: datetime | None = None,
) -> AcquisitionContext | None:
    instant = now or datetime.now(UTC)
    run = await session.scalar(
        select(AcquisitionRunModel).where(AcquisitionRunModel.run_id == run_id).with_for_update()
    )
    if run is None:
        raise LookupError(f"unknown acquisition run: {run_id}")
    if run.status in TERMINAL_STATUSES or run.status == "running":
        return None
    if run.status != "queued":
        raise RuntimeError(f"acquisition run {run_id} has invalid status {run.status!r}")

    source = await session.get(SourceModel, run.source_id)
    state = await session.scalar(
        select(SourceStateModel)
        .where(SourceStateModel.source_id == run.source_id)
        .with_for_update()
    )
    if source is None or state is None:
        raise RuntimeError(f"source runtime state is incomplete for {run.source_id}")
    if not source.enabled:
        run.status = "internal_error"
        run.finished_at = instant
        run.error_code = "source_disabled"
        run.error_detail = "source was disabled before the queued run started"
        return None

    run.status = "running"
    run.started_at = instant
    run.attempt += 1
    run.error_code = None
    run.error_detail = None
    state.last_attempt_at = instant

    state_contract = source_state_from_model(state)
    state_contract.cursor = _json_dict(run.cursor_in)
    return AcquisitionContext(
        run_id=run.run_id,
        trigger=AcquisitionTrigger(run.trigger),
        source=source_definition_from_model(source),
        state=state_contract,
    )


async def complete_hot_window_run(
    session: AsyncSession,
    run_id: str,
    result: HotWindowCollectionResult,
    *,
    now: datetime | None = None,
) -> None:
    await complete_collection_run(
        session,
        run_id,
        next_cursor=_object_dict(result.next_cursor),
        accepted_count=len(result.accepted),
        changed=any(item.changed_fields for item in result.accepted),
        now=now,
    )


async def complete_collection_run(
    session: AsyncSession,
    run_id: str,
    *,
    next_cursor: dict[str, object],
    accepted_count: int,
    changed: bool,
    now: datetime | None = None,
) -> None:
    instant = now or datetime.now(UTC)
    run, state = await _locked_run_and_state(session, run_id)
    if run.status in TERMINAL_STATUSES:
        return
    if run.status != "running":
        raise RuntimeError(f"cannot complete acquisition run in status {run.status!r}")

    run.status = "success" if accepted_count else "no_change"
    run.cursor_out = dict(next_cursor)
    run.finished_at = instant
    state.cursor = dict(next_cursor)
    state.last_success_at = instant
    if changed:
        state.last_change_at = instant
    state.consecutive_failures = 0
    state.backoff_until = None


async def fail_acquisition_run(
    session: AsyncSession,
    run_id: str,
    failure: AcquisitionFailure,
    *,
    now: datetime | None = None,
) -> None:
    instant = now or datetime.now(UTC)
    run, state = await _locked_run_and_state(session, run_id)
    if run.status in TERMINAL_STATUSES:
        return
    if run.status != "running":
        raise RuntimeError(f"cannot fail acquisition run in status {run.status!r}")
    state.consecutive_failures += 1
    backoff_until = instant + timedelta(seconds=failure.backoff_seconds)
    state.backoff_until = backoff_until
    state.next_due_at = backoff_until
    run.status = failure.status
    run.finished_at = instant
    run.error_code = failure.error_code
    run.error_detail = failure.error_detail[:4000]


def classify_source_failure(exc: Exception, *, consecutive_failures: int = 0) -> AcquisitionFailure:
    if isinstance(exc, SourceRateLimited):
        return AcquisitionFailure(
            status="rate_limited",
            error_code="source_rate_limited",
            error_detail=str(exc),
            backoff_seconds=15 * 60,
        )
    if isinstance(exc, SourceAuthFailed):
        return AcquisitionFailure(
            status="auth_failed",
            error_code="source_auth_failed",
            error_detail=str(exc),
            backoff_seconds=6 * 60 * 60,
        )
    if isinstance(exc, SourceSchemaChanged):
        return AcquisitionFailure(
            status="schema_changed",
            error_code="source_schema_changed",
            error_detail=str(exc),
            backoff_seconds=6 * 60 * 60,
        )
    if isinstance(exc, SourceFetchFailed):
        exponent = min(max(consecutive_failures, 0), 4)
        return AcquisitionFailure(
            status="fetch_failed",
            error_code="source_fetch_failed",
            error_detail=str(exc),
            backoff_seconds=min(5 * 60 * (2**exponent), 60 * 60),
        )
    return AcquisitionFailure(
        status="internal_error",
        error_code=type(exc).__name__,
        error_detail=str(exc) or repr(exc),
        backoff_seconds=15 * 60,
    )


async def recover_stale_acquisition_runs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    timeout_seconds: int = 15 * 60,
    limit: int = 100,
) -> list[str]:
    instant = now or datetime.now(UTC)
    threshold = instant - timedelta(seconds=timeout_seconds)
    statement = (
        select(AcquisitionRunModel)
        .where(
            AcquisitionRunModel.status == "running",
            AcquisitionRunModel.started_at.is_not(None),
            AcquisitionRunModel.started_at <= threshold,
        )
        .order_by(AcquisitionRunModel.started_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    runs = list(await session.scalars(statement))
    recovered: list[str] = []
    for run in runs:
        run.status = "queued"
        run.started_at = None
        session.add(
            OutboxEventModel(
                event_id=str(uuid4()),
                topic="collection.requested",
                aggregate_id=run.run_id,
                payload={"run_id": run.run_id},
                status="pending",
                attempts=0,
                available_at=instant,
            )
        )
        recovered.append(run.run_id)
    return recovered


async def _locked_run_and_state(
    session: AsyncSession, run_id: str
) -> tuple[AcquisitionRunModel, SourceStateModel]:
    run = await session.scalar(
        select(AcquisitionRunModel).where(AcquisitionRunModel.run_id == run_id).with_for_update()
    )
    if run is None:
        raise LookupError(f"unknown acquisition run: {run_id}")
    state = await session.scalar(
        select(SourceStateModel)
        .where(SourceStateModel.source_id == run.source_id)
        .with_for_update()
    )
    if state is None:
        raise RuntimeError(f"source state missing for {run.source_id}")
    return run, state


def _json_dict(value: dict[str, object]) -> dict[str, Any]:
    return dict(value)


def _object_dict(value: dict[str, Any]) -> dict[str, object]:
    return dict(value)
