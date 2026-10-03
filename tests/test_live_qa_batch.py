from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from scripts.run_live_qa_batch import _next_suite_revision


@pytest.mark.asyncio
async def test_formal_revision_allocation_advances_past_global_qa_case_revision() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[None, 9])

    revision = await _next_suite_revision(
        session,
        "m6-real-product-qa",
        ["qa-case-a", "qa-case-b"],
    )

    assert revision == 10
    assert session.scalar.await_count == 2


@pytest.mark.asyncio
async def test_formal_revision_allocation_keeps_suite_revision_monotonic() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[11, 9])

    revision = await _next_suite_revision(
        session,
        "m6-real-product-qa",
        ["qa-case-a"],
    )

    assert revision == 12
