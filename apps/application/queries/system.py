from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.views.system import SystemBacklogView
from packages.shared.storage.models import OutboxEventModel
from packages.task_runtime.storage.models import TaskEventDeliveryModel


async def get_delivery_backlogs(
    session: AsyncSession,
) -> tuple[SystemBacklogView, SystemBacklogView]:
    outbox_count, outbox_oldest = (
        await session.execute(
            select(func.count(), func.min(OutboxEventModel.available_at)).where(
                OutboxEventModel.status == "pending"
            )
        )
    ).one()
    task_count, task_oldest = (
        await session.execute(
            select(func.count(), func.min(TaskEventDeliveryModel.available_at)).where(
                TaskEventDeliveryModel.status == "pending"
            )
        )
    ).one()
    return (
        SystemBacklogView(
            pending_count=int(outbox_count or 0),
            oldest_pending_at=outbox_oldest,
        ),
        SystemBacklogView(
            pending_count=int(task_count or 0),
            oldest_pending_at=task_oldest,
        ),
    )
