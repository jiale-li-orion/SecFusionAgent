from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_models import register_runtime_models
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 10, 30, tzinfo=UTC)


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_execution(session, execution_id: str) -> None:
    session.add(
        ExecutionRunModel(
            execution_id=execution_id,
            parent_execution_id=None,
            task_run_id="run-test",
            envelope_json={"execution_id": execution_id},
            status="running",
            stop_reason=None,
            created_at=NOW,
            started_at=NOW,
            finished_at=None,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_runtime_artifact_write_replay_and_hash_verified_read() -> None:
    engine, factory = await _database()
    blob = MemoryRuntimeBlobStore()
    service = RuntimeArtifactService(blob, now=lambda: NOW)
    execution_id = "execution:test"
    try:
        async with factory() as session, session.begin():
            await _seed_execution(session, execution_id)
            first = await service.write(
                session,
                execution_id=execution_id,
                producer_kind="sandbox",
                producer_ref="sandbox-exec:1",
                logical_name="verify.stdout",
                media_type="text/plain",
                body=b"verified\n",
            )
            replay = await service.write(
                session,
                execution_id=execution_id,
                producer_kind="sandbox",
                producer_ref="sandbox-exec:1",
                logical_name="verify.stdout",
                media_type="text/plain",
                body=b"verified\n",
            )
            assert replay.artifact_ref == first.artifact_ref

        async with factory() as session:
            assert await service.read(session, first.artifact_ref) == b"verified\n"
            loaded = await service.get(session, first.artifact_ref)
            assert loaded.execution_id == execution_id
            assert loaded.trust_class == "execution_untrusted"

        blob.objects[first.storage_uri] = b"tampered"
        async with factory() as session:
            with pytest.raises(RuntimeError, match="content hash mismatch"):
                await service.read(session, first.artifact_ref)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_artifact_replay_cannot_change_metadata() -> None:
    engine, factory = await _database()
    service = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    execution_id = "execution:test-metadata"
    try:
        async with factory() as session, session.begin():
            await _seed_execution(session, execution_id)
            await service.write(
                session,
                execution_id=execution_id,
                producer_kind="sandbox",
                producer_ref="sandbox-exec:1",
                logical_name="result.json",
                media_type="application/json",
                body=b"{}",
            )
            with pytest.raises(ValueError, match="replay identity changed metadata"):
                await service.write(
                    session,
                    execution_id=execution_id,
                    producer_kind="capability",
                    producer_ref="capability:1",
                    logical_name="result.json",
                    media_type="application/json",
                    body=b"{}",
                )
    finally:
        await engine.dispose()
