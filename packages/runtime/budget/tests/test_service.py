from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.budget import BudgetExceeded, BudgetGovernor, BudgetLimits
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 7, 0, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_reserve_commit_release_and_replay_preserve_consumed_budget() -> None:
    engine, factory = await _database()
    governor = BudgetGovernor(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            await governor.create_account(
                session,
                account_id="budget:root",
                limits=BudgetLimits(
                    quantities={
                        "tool_calls": Decimal("5"),
                        "external_cost": Decimal("10"),
                    }
                ),
            )
            reserved = await governor.reserve(
                session,
                account_id="budget:root",
                reservation_group_id="action:1",
                quantities={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("4"),
                },
            )
            assert reserved.replay is False
            replay = await governor.reserve(
                session,
                account_id="budget:root",
                reservation_group_id="action:1",
                quantities={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("4"),
                },
            )
            assert replay.replay is True
            await governor.commit(
                session,
                account_id="budget:root",
                reservation_group_id="action:1",
                consumed={
                    "tool_calls": Decimal("1"),
                    "external_cost": Decimal("2.5"),
                },
            )
            snapshot = await governor.snapshot(session, "budget:root")
            assert snapshot.committed == {
                "external_cost": Decimal("2.500000"),
                "tool_calls": Decimal("1.000000"),
            }
            assert snapshot.remaining["external_cost"] == Decimal("7.500000")
            assert snapshot.remaining["tool_calls"] == Decimal("4.000000")

            await governor.reserve(
                session,
                account_id="budget:root",
                reservation_group_id="action:2",
                quantities={"external_cost": Decimal("3")},
            )
            await governor.release(
                session,
                account_id="budget:root",
                reservation_group_id="action:2",
            )
            snapshot = await governor.snapshot(session, "budget:root")
            assert snapshot.remaining["external_cost"] == Decimal("7.500000")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_child_budget_allocations_cannot_overbook_parent_and_unused_allocation_returns() -> (
    None
):
    engine, factory = await _database()
    governor = BudgetGovernor(now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            await governor.create_account(
                session,
                account_id="budget:parent",
                limits=BudgetLimits(quantities={"tool_calls": Decimal("5")}),
            )
            await governor.create_account(
                session,
                account_id="budget:child-a",
                parent_account_id="budget:parent",
                limits=BudgetLimits(quantities={"tool_calls": Decimal("3")}),
            )
            with pytest.raises(BudgetExceeded, match="child budget exceeds parent remaining"):
                await governor.create_account(
                    session,
                    account_id="budget:child-b",
                    parent_account_id="budget:parent",
                    limits=BudgetLimits(quantities={"tool_calls": Decimal("3")}),
                )
            await governor.reserve(
                session,
                account_id="budget:child-a",
                reservation_group_id="child-action",
                quantities={"tool_calls": Decimal("2")},
            )
            await governor.commit(
                session,
                account_id="budget:child-a",
                reservation_group_id="child-action",
                consumed={"tool_calls": Decimal("2")},
            )
            await governor.close_child_account(session, "budget:child-a")
            parent = await governor.snapshot(session, "budget:parent")
            assert parent.committed["tool_calls"] == Decimal("2.000000")
            assert parent.remaining["tool_calls"] == Decimal("3.000000")
            await governor.create_account(
                session,
                account_id="budget:child-b",
                parent_account_id="budget:parent",
                limits=BudgetLimits(quantities={"tool_calls": Decimal("3")}),
            )
    finally:
        await engine.dispose()
