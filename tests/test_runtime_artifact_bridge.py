from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.runtime_artifacts import RuntimeArtifactSandboxBridge
from apps.runtime_models import register_runtime_models
from packages.runtime.artifacts import MemoryRuntimeBlobStore, RuntimeArtifactService
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.db import Base

NOW = datetime(2026, 9, 27, 10, 45, tzinfo=UTC)


@pytest.mark.asyncio
async def test_sandbox_bridge_scopes_runtime_artifacts_to_execution(tmp_path) -> None:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    service = RuntimeArtifactService(MemoryRuntimeBlobStore(), now=lambda: NOW)
    try:
        async with factory() as session, session.begin():
            for execution_id in ("execution:a", "execution:b"):
                session.add(
                    ExecutionRunModel(
                        execution_id=execution_id,
                        parent_execution_id=None,
                        task_run_id=f"run:{execution_id}",
                        envelope_json={},
                        status="running",
                        stop_reason=None,
                        created_at=NOW,
                        started_at=NOW,
                        finished_at=None,
                    )
                )
            await session.flush()
            own = await service.write(
                session,
                execution_id="execution:a",
                producer_kind="capability",
                producer_ref="capability:repo-snapshot",
                logical_name="repo.tar",
                media_type="application/x-tar",
                body=b"repo-a",
            )
            foreign = await service.write(
                session,
                execution_id="execution:b",
                producer_kind="capability",
                producer_ref="capability:repo-snapshot",
                logical_name="repo.tar",
                media_type="application/x-tar",
                body=b"repo-b",
            )

        bridge = RuntimeArtifactSandboxBridge(
            factory,
            service,
            execution_id="execution:a",
        )
        own_path = await bridge.materialize(own.artifact_ref, destination_dir=tmp_path / "own")
        assert own_path.read_bytes() == b"repo-a"
        with pytest.raises(PermissionError, match="outside sandbox execution scope"):
            await bridge.materialize(
                foreign.artifact_ref,
                destination_dir=tmp_path / "foreign",
            )

        allowed = RuntimeArtifactSandboxBridge(
            factory,
            service,
            execution_id="execution:a",
            allowed_external_refs={foreign.artifact_ref},
        )
        foreign_path = await allowed.materialize(
            foreign.artifact_ref,
            destination_dir=tmp_path / "allowed",
        )
        assert foreign_path.read_bytes() == b"repo-b"
        output_ref = await bridge.ingest_bytes(
            b"stdout",
            media_type="text/plain",
            logical_name="op.stdout",
        )
        async with factory() as session:
            output = await service.get(session, output_ref)
            assert output.execution_id == "execution:a"
            assert output.producer_kind == "sandbox"
    finally:
        await engine.dispose()
