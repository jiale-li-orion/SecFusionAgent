"""Replay-safe durable feedback for a single activity, never an object unfollow."""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.storage.feed_models import ActivityFeedbackModel


async def put_activity_feedback(
    session: AsyncSession,
    principal: str,
    activity_id: str,
    feedback: Literal["interested", "ignored", "neutral"],
) -> datetime:
    now = datetime.now(UTC)
    insert = postgresql_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(ActivityFeedbackModel).values(
        principal=principal, activity_id=activity_id, feedback=feedback, updated_at=now
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["principal", "activity_id"],
            set_={"feedback": feedback, "updated_at": now},
        )
    )
    await session.commit()
    return now
