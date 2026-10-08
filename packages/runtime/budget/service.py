from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.runtime.budget.contracts import (
    BudgetLimits,
    BudgetReservation,
    BudgetReservationStatus,
)
from packages.runtime.storage.models import BudgetAccountModel, BudgetReservationModel


class BudgetExceeded(RuntimeError):
    pass


class BudgetAccountView(BaseModel):
    account_id: str
    parent_account_id: str | None = None
    task_run_id: str | None = None
    limits: BudgetLimits
    status: str


class BudgetSnapshot(BaseModel):
    account_id: str
    limits: dict[str, Decimal]
    reserved: dict[str, Decimal]
    committed: dict[str, Decimal]
    remaining: dict[str, Decimal]


class BudgetReservationGroup(BaseModel):
    reservation_group_id: str
    account_id: str
    reservations: list[BudgetReservation]
    replay: bool = False


class BudgetGovernor:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))

    async def create_account(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        limits: BudgetLimits,
        task_run_id: str | None = None,
        parent_account_id: str | None = None,
    ) -> BudgetAccountView:
        existing = await session.get(BudgetAccountModel, account_id)
        if existing is not None:
            expected = _serialize_limits(limits)
            if (
                existing.limits != expected
                or existing.task_run_id != task_run_id
                or existing.parent_account_id != parent_account_id
            ):
                raise ValueError("budget account identity is immutable")
            return _account_view(existing)

        if parent_account_id is not None:
            parent = await session.scalar(
                select(BudgetAccountModel)
                .where(BudgetAccountModel.account_id == parent_account_id)
                .with_for_update()
            )
            if parent is None:
                raise LookupError(f"parent budget account not found: {parent_account_id}")
            if parent.status != "active":
                raise ValueError("parent budget account is not active")
            snapshot = await self.snapshot(session, parent_account_id, lock_held=True)
            for resource, amount in limits.quantities.items():
                if amount > snapshot.remaining.get(resource, Decimal("0")):
                    raise BudgetExceeded(
                        f"child budget exceeds parent remaining {resource}: "
                        "requested="
                        f"{amount} remaining={snapshot.remaining.get(resource, Decimal('0'))}"
                    )

        now = self._now()
        model = BudgetAccountModel(
            account_id=account_id,
            parent_account_id=parent_account_id,
            task_run_id=task_run_id,
            limits=_serialize_limits(limits),
            status="active",
            created_at=now,
        )
        session.add(model)
        await session.flush()

        if parent_account_id is not None and limits.quantities:
            await self.reserve(
                session,
                account_id=parent_account_id,
                reservation_group_id=f"child-allocation:{account_id}",
                quantities=limits.quantities,
                child_account_id=account_id,
            )
        return _account_view(model)

    async def reserve(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        reservation_group_id: str,
        quantities: dict[str, Decimal],
        child_account_id: str | None = None,
    ) -> BudgetReservationGroup:
        if not quantities:
            raise ValueError("budget reservation requires quantities")
        if any(amount <= 0 for amount in quantities.values()):
            raise ValueError("budget reservation quantities must be positive")
        account = await session.scalar(
            select(BudgetAccountModel)
            .where(BudgetAccountModel.account_id == account_id)
            .with_for_update()
        )
        if account is None:
            raise LookupError(f"budget account not found: {account_id}")
        if account.status != "active":
            raise ValueError("budget account is not active")

        existing = list(
            await session.scalars(
                select(BudgetReservationModel).where(
                    BudgetReservationModel.account_id == account_id,
                    BudgetReservationModel.reservation_group_id == reservation_group_id,
                )
            )
        )
        if existing:
            actual = {item.resource_type: item.amount_reserved for item in existing}
            if actual != quantities or {item.child_account_id for item in existing} != {
                child_account_id
            }:
                raise ValueError("budget reservation group identity is immutable")
            return BudgetReservationGroup(
                reservation_group_id=reservation_group_id,
                account_id=account_id,
                reservations=[_reservation_view(item) for item in existing],
                replay=True,
            )

        snapshot = await self.snapshot(session, account_id, lock_held=True)
        for resource, amount in quantities.items():
            remaining = snapshot.remaining.get(resource, Decimal("0"))
            if amount > remaining:
                raise BudgetExceeded(
                    f"budget exhausted for {resource}: requested={amount} remaining={remaining}"
                )

        now = self._now()
        models: list[BudgetReservationModel] = []
        for resource, amount in sorted(quantities.items()):
            model = BudgetReservationModel(
                reservation_id=_stable_id(
                    f"budget-reservation:{account_id}:{reservation_group_id}:{resource}"
                ),
                reservation_group_id=reservation_group_id,
                account_id=account_id,
                child_account_id=child_account_id,
                resource_type=resource,
                amount_reserved=amount,
                amount_committed=Decimal("0"),
                status=BudgetReservationStatus.RESERVED.value,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            models.append(model)
        await session.flush()
        return BudgetReservationGroup(
            reservation_group_id=reservation_group_id,
            account_id=account_id,
            reservations=[_reservation_view(item) for item in models],
        )

    async def commit(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        reservation_group_id: str,
        consumed: dict[str, Decimal],
        allow_overrun: bool = False,
    ) -> BudgetReservationGroup:
        # Provider-reported usage can exceed a pre-call estimate. Keep the exact
        # spend in the ledger; future reserves still see zero remaining.
        models = await self._lock_group(session, account_id, reservation_group_id)
        now = self._now()
        expected_resources = {item.resource_type for item in models}
        if not set(consumed) <= expected_resources:
            raise ValueError("commit contains resource not present in reservation")
        for model in models:
            if model.status != BudgetReservationStatus.RESERVED.value:
                prior = {item.resource_type: item.amount_committed for item in models}
                if all(
                    item.status == BudgetReservationStatus.COMMITTED.value for item in models
                ) and all(
                    prior.get(resource, Decimal("0")) == amount
                    for resource, amount in consumed.items()
                ):
                    return BudgetReservationGroup(
                        reservation_group_id=reservation_group_id,
                        account_id=account_id,
                        reservations=[_reservation_view(item) for item in models],
                        replay=True,
                    )
                raise ValueError("budget reservation group is no longer reservable")
            amount = consumed.get(model.resource_type, Decimal("0"))
            if amount < 0 or (amount > model.amount_reserved and not allow_overrun):
                raise ValueError(
                    f"committed amount exceeds reservation for {model.resource_type}: {amount}"
                )
            model.amount_committed = amount
            model.status = BudgetReservationStatus.COMMITTED.value
            model.updated_at = now
        await session.flush()
        return BudgetReservationGroup(
            reservation_group_id=reservation_group_id,
            account_id=account_id,
            reservations=[_reservation_view(item) for item in models],
        )

    async def release(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        reservation_group_id: str,
    ) -> BudgetReservationGroup:
        models = await self._lock_group(session, account_id, reservation_group_id)
        now = self._now()
        if all(item.status == BudgetReservationStatus.RELEASED.value for item in models):
            return BudgetReservationGroup(
                reservation_group_id=reservation_group_id,
                account_id=account_id,
                reservations=[_reservation_view(item) for item in models],
                replay=True,
            )
        if any(item.status == BudgetReservationStatus.COMMITTED.value for item in models):
            raise ValueError("committed reservation cannot be released")
        for model in models:
            model.status = BudgetReservationStatus.RELEASED.value
            model.updated_at = now
        await session.flush()
        return BudgetReservationGroup(
            reservation_group_id=reservation_group_id,
            account_id=account_id,
            reservations=[_reservation_view(item) for item in models],
        )

    async def close_child_account(
        self, session: AsyncSession, account_id: str
    ) -> BudgetAccountView:
        child = await session.scalar(
            select(BudgetAccountModel)
            .where(BudgetAccountModel.account_id == account_id)
            .with_for_update()
        )
        if child is None:
            raise LookupError(f"budget account not found: {account_id}")
        if child.parent_account_id is None:
            raise ValueError("close_child_account requires a child budget account")
        if child.status == "closed":
            return _account_view(child)

        child_snapshot = await self.snapshot(session, account_id, lock_held=True)
        consumed = child_snapshot.committed
        await self.commit(
            session,
            account_id=child.parent_account_id,
            reservation_group_id=f"child-allocation:{account_id}",
            consumed=consumed,
            allow_overrun=True,
        )
        child.status = "closed"
        child.closed_at = self._now()
        await session.flush()
        return _account_view(child)

    async def snapshot(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        lock_held: bool = False,
    ) -> BudgetSnapshot:
        query = select(BudgetAccountModel).where(BudgetAccountModel.account_id == account_id)
        if not lock_held:
            query = query.with_for_update()
        account = await session.scalar(query)
        if account is None:
            raise LookupError(f"budget account not found: {account_id}")
        limits = {key: Decimal(value) for key, value in account.limits.items()}
        rows = list(
            await session.scalars(
                select(BudgetReservationModel).where(
                    BudgetReservationModel.account_id == account_id
                )
            )
        )
        reserved: dict[str, Decimal] = {}
        committed: dict[str, Decimal] = {}
        for row in rows:
            if row.status == BudgetReservationStatus.RESERVED.value:
                reserved[row.resource_type] = reserved.get(
                    row.resource_type, Decimal("0")
                ) + Decimal(row.amount_reserved)
            elif row.status == BudgetReservationStatus.COMMITTED.value:
                committed[row.resource_type] = committed.get(
                    row.resource_type, Decimal("0")
                ) + Decimal(row.amount_committed)
        remaining = {
            resource: max(
                Decimal("0"),
                limit
                - reserved.get(resource, Decimal("0"))
                - committed.get(resource, Decimal("0")),
            )
            for resource, limit in limits.items()
        }
        return BudgetSnapshot(
            account_id=account_id,
            limits=limits,
            reserved=reserved,
            committed=committed,
            remaining=remaining,
        )

    async def _lock_group(
        self,
        session: AsyncSession,
        account_id: str,
        reservation_group_id: str,
    ) -> list[BudgetReservationModel]:
        rows = list(
            await session.scalars(
                select(BudgetReservationModel)
                .where(
                    BudgetReservationModel.account_id == account_id,
                    BudgetReservationModel.reservation_group_id == reservation_group_id,
                )
                .order_by(BudgetReservationModel.resource_type)
                .with_for_update()
            )
        )
        if not rows:
            raise LookupError(f"budget reservation group not found: {reservation_group_id}")
        return rows


def _serialize_limits(limits: BudgetLimits) -> dict[str, str]:
    return {key: str(value) for key, value in sorted(limits.quantities.items())}


def _account_view(model: BudgetAccountModel) -> BudgetAccountView:
    return BudgetAccountView(
        account_id=model.account_id,
        parent_account_id=model.parent_account_id,
        task_run_id=model.task_run_id,
        limits=BudgetLimits(
            quantities={key: Decimal(value) for key, value in model.limits.items()}
        ),
        status=model.status,
    )


def _reservation_view(model: BudgetReservationModel) -> BudgetReservation:
    return BudgetReservation(
        reservation_id=model.reservation_id,
        account_id=model.account_id,
        resource_type=model.resource_type,
        amount_reserved=Decimal(model.amount_reserved),
        amount_committed=Decimal(model.amount_committed),
        status=BudgetReservationStatus(model.status),
    )


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"secfusion:{value}"))
