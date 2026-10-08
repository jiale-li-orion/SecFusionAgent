from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.account_fixtures import account_headers
from apps.api.tests.test_product_investigations import _database
from apps.enrichment_runtime import create_configured_enrichment_runtime
from packages.enrichment.runtime.role import EnrichmentRoleRuntime
from packages.enrichment.runtime.state_models import EnrichmentAttemptModel
from packages.intelligence.knowledge.read import get_object_by_id
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.knowledge_models import ObjectModel
from packages.runtime.storage.models import ExecutionRunModel
from packages.shared.config import Settings
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions
from packages.task_runtime.contracts.models import TaskRunStatus
from packages.task_runtime.storage.models import TaskEventDeliveryModel, TaskRunModel


@pytest.mark.asyncio
async def test_product_enrichment_admits_idempotently_and_reports_real_blocked_task() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    url = "/api/v1/intelligence/objects/api-vuln-object/enrichment/runs"
    headers = {**account_headers("test"), "Idempotency-Key": "enrich-1"}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            first = await client.post(url, headers=headers, json={"dimensions": ["research_paper"]})
            assert first.status_code == 202, first.text
            body = first.json()
            assert body["status"] == "queued"
            assert body["role_id"] == "EnrichmentRole"
            assert body["execution_profile"] == "INVESTIGATE"
            assert first.headers["location"] == body["task_url"]
            replay = await client.post(
                url, headers=headers, json={"dimensions": ["research_paper"]}
            )
            assert replay.status_code == 202, replay.text
            assert replay.json()["task_run_id"] == body["task_run_id"]
            assert replay.json()["replayed"] is True
            conflict = await client.post(url, headers=headers, json={"dimensions": ["severity"]})
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "idempotency_conflict"
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(TaskRunModel)) == 1
                execution = await session.get(ExecutionRunModel, f"execution:{body['task_run_id']}")
                assert execution.envelope_json["trace_context"]["surface"] == "product-enrichment"
                assert (
                    await session.scalar(select(func.count()).select_from(TaskEventDeliveryModel))
                    == 2
                )

            class NoNetworkExecutor:
                async def execute(self, *args, **kwargs):
                    raise AssertionError("research has no eligible operator; never call network")

            outcome = await EnrichmentRoleRuntime(factory, NoNetworkExecutor()).run(
                body["task_run_id"]
            )
            assert outcome.run_status is TaskRunStatus.BLOCKED
            task = await client.get(body["task_url"])
            assert task.json()["task"]["status"] == "blocked"
            page = await client.get(url, headers={**account_headers("test")})
            assert page.json()["items"][0]["status"] == "blocked"
            foreign = await client.get(url, headers={**account_headers("other")})
            assert foreign.json()["items"] == []
            state = await client.get(body["state_url"])
            assert (
                next(d for d in state.json()["dimensions"] if d["dimension"] == "research_paper")[
                    "status"
                ]
                == "missing"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dimension,host,operator",
    [
        ("exploit_likelihood", "api.first.org", "provider.first_epss"),
        ("version_applicability", "security.access.redhat.com", "provider.redhat_csaf_vex"),
    ],
)
async def test_product_enrichment_production_composition_binds_owned_providers(
    dimension: str, host: str, operator: str
) -> None:
    engine, factory = await _database()
    app = create_app()
    seen: list[str] = []

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session

    def source_response(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "api.first.org":
            return httpx.Response(
                200,
                json={
                    "version": "1.0",
                    "data": [
                        {
                            "cve": "CVE-2026-51515",
                            "epss": "0.01152",
                            "percentile": "0.65554",
                            "date": "2026-09-27",
                        }
                    ],
                },
            )
        if request.url.host == "api.github.com":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, load_source_definitions(Path("config/sources")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            response = await client.post(
                "/api/v1/intelligence/objects/api-vuln-object/enrichment/runs",
                headers={"Idempotency-Key": f"composition-{dimension}"},
                json={"dimensions": [dimension]},
            )
            assert response.status_code == 202, response.text
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(source_response)
        ) as source_client:
            outcome = await create_configured_enrichment_runtime(
                Settings(), factory, source_client, MemoryArtifactStore()
            ).run(response.json()["task_run_id"])
        assert host in seen
        assert operator in outcome.result.attempted_operators
        async with factory() as session:
            attempts = list(
                await session.scalars(
                    select(EnrichmentAttemptModel).where(
                        EnrichmentAttemptModel.task_run_id == response.json()["task_run_id"]
                    )
                )
            )
            assert attempts
            assert all(item.execution_status == "succeeded" for item in attempts)
            if dimension == "exploit_likelihood":
                assert outcome.run_status is TaskRunStatus.COMPLETED
                view = await get_object_by_id(session, "api-vuln-object")
                assert view is not None
                epss = next(claim for claim in view.claims if claim.predicate == "epss_probability")
                assert epss.value == 0.01152
                assert epss.evidence[0].source_id == "first-epss"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_product_enrichment_rejects_invalid_request_target_and_stale_revision() -> None:
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    url = "/api/v1/intelligence/objects/api-vuln-object/enrichment/runs"
    headers = {"Idempotency-Key": "invalid-test"}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            assert (
                await client.post(url, headers=headers, json={"dimensions": ["made_up"]})
            ).status_code == 422
            assert (await client.post(url, json={"dimensions": ["severity"]})).status_code == 422
            stale = await client.post(
                url,
                headers=headers,
                json={"dimensions": ["severity"], "expected_world_revision": 999},
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "revision_conflict"
            missing = await client.post(
                url.replace("api-vuln-object", "missing"),
                headers=headers,
                json={"dimensions": ["severity"]},
            )
            assert missing.status_code == 404
            denied = await client.post(
                url,
                headers={**headers, "Cookie": ""},
                json={"dimensions": ["severity"]},
            )
            assert denied.status_code == 401
            async with factory() as session, session.begin():
                await session.execute(
                    update(ObjectModel)
                    .where(ObjectModel.object_id == "api-vuln-object")
                    .values(object_type="ResearchWork")
                )
            wrong_target = await client.post(
                url, headers=headers, json={"dimensions": ["severity"]}
            )
            assert wrong_target.status_code == 422
    finally:
        await engine.dispose()
