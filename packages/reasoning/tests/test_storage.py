from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.reasoning.decision import DecisionResult
from packages.reasoning.storage import DecisionResultStore
from packages.shared.db import Base

NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_decision_result_store_is_immutable_and_replay_safe() -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = DecisionResultStore(now=lambda: NOW)
    decision = DecisionResult(
        decision_id="decision:stored-1",
        case_id="question:req-1",
        case_revision=0,
        answer_payload={"answer": "ok"},
        stop_reason="complete",
        model_prompt_revision="decision-model-v1",
    )
    try:
        async with factory() as session, session.begin():
            first = await store.persist(session, decision)
            replay = await store.persist(session, decision)
            assert replay == first
            assert first.created_at == NOW

        async with factory() as session:
            loaded = await store.get(session, decision.decision_id)
            assert loaded.answer_payload == {"answer": "ok"}
            assert loaded.created_at == NOW

        changed = decision.model_copy(update={"answer_payload": {"answer": "changed"}})
        async with factory() as session, session.begin():
            with pytest.raises(ValueError, match="identity is immutable"):
                await store.persist(session, changed)
    finally:
        await engine.dispose()
