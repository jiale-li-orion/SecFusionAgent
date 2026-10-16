"""Durable, bounded public editorial jobs. No source data grants execution authority."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import JSON, DateTime, Integer, String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.storage.models import OutboxEventModel

MAX_ATTEMPTS = 2
LEASE_SECONDS = 1200
TERMINAL = {"published", "review_required", "skipped", "failed"}


class EditorialRunModel(Base):
    __tablename__ = "editorial_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claim_token: Mapped[str | None] = mapped_column(String(36))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selection: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    brief_id: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enqueue(session: AsyncSession, run: EditorialRunModel, now: datetime) -> None:
    session.add(
        OutboxEventModel(
            event_id=str(uuid5(NAMESPACE_URL, f"editorial:{run.run_id}:{run.attempts}")),
            topic="editorial.requested",
            aggregate_id=run.run_id,
            payload={"run_id": run.run_id},
            status="pending",
            attempts=0,
            available_at=now,
        )
    )


async def schedule_editorial(
    session: AsyncSession,
    *,
    now: datetime,
    interval_hours: int = 6,
) -> str:
    instant = utc(now)
    # Recovery is separate from publication; expired owners cannot publish or finish.
    stale = list(
        await session.scalars(
            select(EditorialRunModel)
            .where(
                EditorialRunModel.status.in_(["running", "retry"]),
                EditorialRunModel.available_at <= instant,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for run in stale:
        if run.status == "running" and run.lease_until and utc(run.lease_until) > instant:
            continue
        run.claim_token = None
        run.lease_until = None
        run.updated_at = instant
        if run.attempts >= MAX_ATTEMPTS:
            run.status = "failed"
            run.last_error = run.last_error or "editorial worker lease expired"
        else:
            run.status = "queued"
            enqueue(session, run, instant)
    seconds = interval_hours * 3600
    slot = datetime.fromtimestamp(int(instant.timestamp()) // seconds * seconds, UTC)
    run_id = "editorial:" + slot.strftime("%Y%m%dT%H%MZ")
    if await session.get(EditorialRunModel, run_id):
        return run_id
    try:
        async with session.begin_nested():
            run = EditorialRunModel(
                run_id=run_id,
                slot_at=slot,
                status="queued",
                attempts=0,
                available_at=instant,
                selection={},
                updated_at=instant,
            )
            session.add(run)
            await session.flush()
            enqueue(session, run, instant)
            await session.flush()
    except IntegrityError:
        if await session.get(EditorialRunModel, run_id) is None:
            raise
    return run_id


async def claim_run(session: AsyncSession, run_id: str, *, now: datetime) -> str | None:
    token = str(uuid4())
    result = await session.execute(
        update(EditorialRunModel)
        .execution_options(synchronize_session="fetch")
        .where(
            EditorialRunModel.run_id == run_id,
            EditorialRunModel.status == "queued",
            EditorialRunModel.available_at <= now,
            EditorialRunModel.attempts < MAX_ATTEMPTS,
        )
        .values(
            status="running",
            claim_token=token,
            attempts=EditorialRunModel.attempts + 1,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
            updated_at=now,
        )
    )
    return token if result.rowcount else None  # type: ignore[attr-defined]


async def verify_claim(
    session: AsyncSession, run_id: str, token: str, *, now: datetime
) -> EditorialRunModel:
    run = await session.scalar(
        select(EditorialRunModel)
        .where(
            EditorialRunModel.run_id == run_id,
        )
        .with_for_update()
    )
    if (
        run is None
        or run.status != "running"
        or run.claim_token != token
        or run.lease_until is None
        or utc(run.lease_until) <= utc(now)
    ):
        raise ValueError("editorial claim expired or replaced")
    return run


async def finish_run(
    session: AsyncSession,
    run_id: str,
    token: str,
    *,
    status: str,
    now: datetime,
    brief_id: str | None = None,
    error: str | None = None,
) -> bool:
    if status not in TERMINAL | {"retry"}:
        raise ValueError("invalid editorial terminal/retry state")
    try:
        run = await verify_claim(session, run_id, token, now=now)
    except ValueError:
        return False
    run.status = "failed" if status == "retry" and run.attempts >= MAX_ATTEMPTS else status
    run.brief_id, run.last_error = brief_id, error
    run.claim_token, run.lease_until = None, None
    run.updated_at = now
    run.available_at = now + timedelta(minutes=5) if run.status == "retry" else now
    return True
