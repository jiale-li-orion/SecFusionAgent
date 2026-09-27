from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from packages.task_runtime.events.redis_stream import (
    ack_task_event_message,
    read_task_event_messages,
)

STREAM = "secfusion:task-events:consumer-test"
GROUP = "task-scheduler-test"


@pytest.mark.asyncio
async def test_task_event_consumer_group_reads_and_acks_new_event() -> None:
    redis = FakeRedis(decode_responses=True)
    try:
        message_id = await redis.xadd(STREAM, {"event_id": "event-1"})
        messages = await read_task_event_messages(
            redis,
            stream_name=STREAM,
            group_name=GROUP,
            consumer_name="consumer-a",
            claim_idle_ms=0,
            block_ms=None,
        )
        assert [(item.message_id, item.event_id) for item in messages] == [(message_id, "event-1")]
        assert (
            await ack_task_event_message(
                redis,
                stream_name=STREAM,
                group_name=GROUP,
                message_id=message_id,
            )
            == 1
        )
        assert await redis.xpending(STREAM, GROUP) == {
            "pending": 0,
            "min": None,
            "max": None,
            "consumers": [],
        }
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_task_event_consumer_reclaims_unacked_message_after_consumer_loss() -> None:
    redis = FakeRedis(decode_responses=True)
    try:
        message_id = await redis.xadd(STREAM, {"event_id": "event-replay"})
        first = await read_task_event_messages(
            redis,
            stream_name=STREAM,
            group_name=GROUP,
            consumer_name="consumer-a",
            claim_idle_ms=0,
            block_ms=None,
        )
        assert [item.event_id for item in first] == ["event-replay"]

        replay = await read_task_event_messages(
            redis,
            stream_name=STREAM,
            group_name=GROUP,
            consumer_name="consumer-b",
            claim_idle_ms=0,
            block_ms=None,
        )
        assert [(item.message_id, item.event_id) for item in replay] == [
            (message_id, "event-replay")
        ]
    finally:
        await redis.aclose()
