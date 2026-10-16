"""Read-only runtime coordinates exposed to domain orchestration.

Return values, never ORM rows; mutation remains with budget/model owners.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.model.storage import ModelRequestModel
from packages.runtime.storage.models import BudgetAccountModel


async def budget_limits(session: AsyncSession, account_id: str) -> dict[str, str] | None:
    account = await session.get(BudgetAccountModel, account_id)
    return dict(account.limits) if account is not None else None


async def model_request_count(session: AsyncSession, *, task_run_id: str, purpose: str) -> int:
    return int(
        await session.scalar(
            select(func.count(ModelRequestModel.model_request_id)).where(
                ModelRequestModel.task_run_id == task_run_id,
                ModelRequestModel.purpose == purpose,
            )
        )
        or 0
    )
