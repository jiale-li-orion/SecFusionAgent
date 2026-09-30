from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.retrieval import (
    RetrievalDisposition,
    RetrievalInvocationService,
    RetrievalRequestCoordinate,
)
from packages.shared.db import Base


@pytest.mark.asyncio
async def test_reuse_requires_exact_request_digest_and_world_coordinate() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = RetrievalInvocationService()
    request = RetrievalRequestCoordinate.lexical(
        query="find the same evidence",
        knowledge_revision=10,
        limit=8,
    )
    try:
        async with factory() as session, session.begin():
            first = await service.record(
                session,
                request_owner_ref="product-request:first",
                product_session_id="session-1",
                product_turn_index=1,
                request=request,
                result_refs=["document-chunk:a@r1"],
                disposition=RetrievalDisposition.EXECUTED,
                started_at=datetime(2026, 9, 30, tzinfo=UTC),
                finished_at=datetime(2026, 9, 30, 0, 0, 1, tzinfo=UTC),
            )

        async with factory() as session:
            reusable = await service.find_reusable(
                session,
                product_session_id="session-1",
                before_turn_index=2,
                request=request,
            )
            assert reusable is not None
            assert reusable.invocation_id == first.invocation_id

            world_changed = RetrievalRequestCoordinate.lexical(
                query="find the same evidence",
                knowledge_revision=11,
                limit=8,
            )
            assert (
                await service.find_reusable(
                    session,
                    product_session_id="session-1",
                    before_turn_index=2,
                    request=world_changed,
                )
                is None
            )

            limit_changed = RetrievalRequestCoordinate.lexical(
                query="find the same evidence",
                knowledge_revision=10,
                limit=4,
            )
            assert (
                await service.find_reusable(
                    session,
                    product_session_id="session-1",
                    before_turn_index=2,
                    request=limit_changed,
                )
                is None
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reused_invocation_requires_parent_identity() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = RetrievalInvocationService()
    request = RetrievalRequestCoordinate.lexical(
        query="same",
        knowledge_revision=1,
        limit=8,
    )
    try:
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="requires reuse_of_invocation_id"):
                await service.record(
                    session,
                    request_owner_ref="product-request:bad",
                    product_session_id="session-1",
                    product_turn_index=2,
                    request=request,
                    result_refs=[],
                    disposition=RetrievalDisposition.REUSED,
                )
    finally:
        await engine.dispose()
