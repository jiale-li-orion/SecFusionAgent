from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.task_runtime.storage.models import TaskEventDeliveryModel, TaskEventModel


class TaskStreamMessage(BaseModel):
    message_id: str
    event_id: str


async def dispatch_pending_task_events(
    session: AsyncSession,
    redis: Redis,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    instant = now or datetime.now(UTC)
    deliveries = list(
        await session.scalars(
            select(TaskEventDeliveryModel)
            .join(TaskEventModel, TaskEventModel.event_id == TaskEventDeliveryModel.event_id)
            .where(
                TaskEventDeliveryModel.status == "pending",
                TaskEventDeliveryModel.available_at <= instant,
            )
            .order_by(
                TaskEventModel.task_run_id,
                TaskEventModel.seq,
                TaskEventDeliveryModel.event_id,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    delivered = 0
    for delivery in deliveries:
        event = await session.get(TaskEventModel, delivery.event_id)
        if event is None:
            raise RuntimeError("task event delivery exists without task event")
        try:
            message_id = await redis.xadd(
                delivery.stream_name,
                {
                    "event_id": event.event_id,
                    "task_run_id": event.task_run_id,
                    "parent_run_id": event.parent_run_id or "",
                    "seq": str(event.seq),
                    "event_type": event.event_type,
                    "producer": event.producer,
                    "base_context_revision": str(event.base_context_revision),
                    "payload_ref": event.payload_ref,
                    "idempotency_key": event.idempotency_key,
                    "emitted_at": event.emitted_at.isoformat(),
                },
            )
        except Exception as exc:
            delivery.attempts += 1
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:4000]
            continue
        delivery.status = "delivered"
        delivery.attempts += 1
        delivery.redis_message_id = _message_id_text(message_id)
        delivery.delivered_at = instant
        delivery.last_error = None
        delivered += 1
    return delivered


async def ensure_task_event_consumer_group(
    redis: Redis,
    *,
    stream_name: str,
    group_name: str,
) -> None:
    try:
        await redis.xgroup_create(stream_name, group_name, id="0-0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def read_task_event_messages(
    redis: Redis,
    *,
    stream_name: str,
    group_name: str,
    consumer_name: str,
    limit: int = 100,
    claim_idle_ms: int = 30_000,
    block_ms: int | None = 1,
) -> list[TaskStreamMessage]:
    if limit < 1:
        raise ValueError("task event consumer limit must be >= 1")
    if claim_idle_ms < 0:
        raise ValueError("task event claim_idle_ms must be >= 0")
    await ensure_task_event_consumer_group(
        redis,
        stream_name=stream_name,
        group_name=group_name,
    )

    claimed_response = await redis.xautoclaim(
        stream_name,
        group_name,
        consumer_name,
        claim_idle_ms,
        "0-0",
        count=limit,
    )
    claimed = _claimed_messages(claimed_response)
    messages = _normalize_messages(claimed)
    if len(messages) < limit:
        fresh_response = await redis.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: ">"},
            count=limit - len(messages),
            block=block_ms,
        )
        messages.extend(_stream_messages(fresh_response))

    deduped: dict[str, TaskStreamMessage] = {}
    for message in messages:
        deduped.setdefault(message.message_id, message)
    return list(deduped.values())


async def ack_task_event_message(
    redis: Redis,
    *,
    stream_name: str,
    group_name: str,
    message_id: str,
) -> int:
    return int(await redis.xack(stream_name, group_name, message_id))


def _message_id_text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _claimed_messages(response: object) -> list[object]:
    if not isinstance(response, (list, tuple)) or len(response) < 2:
        return []
    messages = response[1]
    return list(messages) if isinstance(messages, (list, tuple)) else []


def _stream_messages(response: object) -> list[TaskStreamMessage]:
    if not isinstance(response, (list, tuple)):
        return []
    flattened: list[object] = []
    for stream_entry in response:
        if not isinstance(stream_entry, (list, tuple)) or len(stream_entry) < 2:
            continue
        entries = stream_entry[1]
        if isinstance(entries, (list, tuple)):
            flattened.extend(entries)
    return _normalize_messages(flattened)


def _normalize_messages(entries: list[object]) -> list[TaskStreamMessage]:
    result: list[TaskStreamMessage] = []
    for entry in entries:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        message_id = _text(entry[0])
        fields = entry[1]
        if not isinstance(fields, dict):
            continue
        event_value = fields.get("event_id", fields.get(b"event_id"))
        event_id = _text(event_value)
        if message_id and event_id:
            result.append(TaskStreamMessage(message_id=message_id, event_id=event_id))
    return result


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return value if isinstance(value, str) else ""
