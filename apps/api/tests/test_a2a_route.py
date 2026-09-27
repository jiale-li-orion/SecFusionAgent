from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.routes.a2a import database_session, router
from apps.runtime_models import register_runtime_models
from packages.shared.db import Base
from packages.task_runtime.contracts.models import (
    ContextManifest,
    DelegationCeiling,
    EffectCeiling,
    TaskContract,
    TaskKind,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run


async def _database():
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_task(factory: async_sessionmaker[AsyncSession]) -> str:
    run_id = "a2a-route-run"
    contract = TaskContract(
        task_contract_id="a2a-route-contract",
        contract_revision=1,
        principal="user:test",
        task_kind=TaskKind.VERIFY_VERSION_FIX,
        target_resources=["object:vuln-1"],
        desired_state={"predicate": "fix_boundary_resolved"},
        evidence_contract={},
        output_contract={"result_type": "decision"},
        temporal_contract={"scope": "current"},
        effect_ceiling=EffectCeiling.READ_ONLY,
        delegation_ceiling=DelegationCeiling(),
        completion_predicate={"type": "test"},
        policy_revision="policy-v1",
    )
    manifest = ContextManifest(
        context_id="internal-context-a2a-route",
        context_revision=1,
        task_contract_ref="a2a-route-contract@1",
        role_ref="InvestigationRole@1",
        knowledge_revision=1,
        object_refs=["vuln-1"],
        policy_context_ref="policy-context:policy-v1",
        capability_envelope_ref="capability:verify:v1",
        budget_ref=f"budget:{run_id}",
    )
    async with factory() as session, session.begin():
        await create_task_run(
            session,
            contract=contract,
            manifest=manifest,
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=f"execution:{run_id}",
            stream_name="secfusion:task-events:a2a-route-test",
            run_id=run_id,
        )
    return run_id


@pytest.mark.asyncio
async def test_a2a_get_task_exposes_opaque_external_context_and_protocol_media_type() -> None:
    engine, factory = await _database()
    run_id = await _seed_task(factory)
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                f"/api/v1/a2a/tasks/{run_id}",
                headers={"A2A-Version": "1.0.1"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/a2a+json")
            assert response.headers["A2A-Version"] == "1.0"
            payload = response.json()
            assert payload["id"] == run_id
            assert payload["contextId"] != "internal-context-a2a-route"
            assert payload["metadata"]["secfusion"]["contextManifestRef"] == (
                "internal-context-a2a-route@1"
            )

            unsupported = await client.get(
                f"/api/v1/a2a/tasks/{run_id}",
                headers={"A2A-Version": "0.3"},
            )
            assert unsupported.status_code == 400
            assert unsupported.json()["detail"] == "unsupported A2A protocol version"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a2a_get_task_returns_404_without_leaking_internal_lookup_detail() -> None:
    engine, factory = await _database()
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/a2a/tasks/missing")
        assert response.status_code == 404
        assert response.json() == {"detail": "task not found"}
    finally:
        await engine.dispose()
