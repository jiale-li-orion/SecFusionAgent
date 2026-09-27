from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps import evaluation_runtime
from apps.runtime_models import register_runtime_models
from packages.evaluation.benchmark import BenchmarkStore, DeploymentRevision
from packages.shared.config import Settings
from packages.shared.db import Base


def _deployment(identity: str) -> DeploymentRevision:
    return DeploymentRevision(
        deployment_revision_id=identity,
        git_commit="abc+dirty.123",
        schema_revision="20260927_0025",
        source_inventory_hash="a" * 64,
        vocabulary_revision="enrichment-v1",
        policy_revision="policy-v1",
        capability_registry_revision="unbound",
        skill_registry_revision="seed-skills:test",
        model_provider_revision="unconfigured",
        configuration_digest="b" * 64,
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_pinned_deployment_fails_closed_when_current_coordinate_drifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    drifted = _deployment("deployment:drifted")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return drifted

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            with pytest.raises(RuntimeError, match="no longer matches"):
                await evaluation_runtime.ensure_benchmark_deployment_revision(
                    session,
                    Settings(),
                    deployment_revision_id=pinned.deployment_revision_id,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pinned_deployment_accepts_same_current_coordinate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = await _database()
    pinned = _deployment("deployment:pinned")
    try:
        async with factory() as session, session.begin():
            await BenchmarkStore().register_deployment(session, pinned)

        async def fake_capture(*args, **kwargs):
            del args, kwargs
            return pinned

        monkeypatch.setattr(
            evaluation_runtime,
            "capture_current_deployment_revision",
            fake_capture,
        )
        async with factory() as session:
            resolved = await evaluation_runtime.ensure_benchmark_deployment_revision(
                session,
                Settings(),
                deployment_revision_id=pinned.deployment_revision_id,
            )
            assert resolved == pinned.deployment_revision_id
    finally:
        await engine.dispose()
