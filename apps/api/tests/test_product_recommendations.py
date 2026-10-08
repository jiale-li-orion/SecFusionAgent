from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.account_fixtures import account_headers, seed_test_accounts
from apps.application.intelligence_preferences import (
    IntelligencePreferenceModel,
    RecommendationFeedbackModel,
)
from apps.runtime_models import register_runtime_models
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.intelligence.storage.knowledge_models import (
    ClaimModel,
    EvidenceLinkModel,
    KnowledgeRevisionModel,
    ObjectModel,
    RelationModel,
)
from packages.shared.db import Base
from packages.sources.storage.models import SourceModel


@pytest.fixture
async def recommendation_client() -> AsyncIterator[
    tuple[AsyncClient, async_sessionmaker[AsyncSession]]
]:
    register_runtime_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        session.add(
            SourceModel(
                source_id="source:recommendation-fixture",
                adapter_type="test",
                source_class="vendor",
                source_role="primary",
                source_family="fixture",
                access_mode="public",
                update_semantics="snapshot",
                retention_mode="durable_managed",
                schema_version="1",
                definition_hash="fixture",
                updated_at=now,
            )
        )
        session.add(
            ObservationModel(
                observation_id="recommendation-observation",
                source_id="source:recommendation-fixture",
                external_object_id="fixture-advisory",
                acquisition_trigger="scheduled",
                observed_at=now,
                content_hash="fixture",
                idempotency_key="fixture",
                created_at=now,
                canonical_url="https://example.invalid/advisory",
            )
        )
        session.add(KnowledgeRevisionModel(revision=1, committed_at=now))
        await session.flush()
        session.add_all(
            [
                ObjectModel(
                    object_id="product-ray",
                    object_type="Product",
                    canonical_key="product:ray",
                    properties={"name": "Ray"},
                    created_revision=1,
                ),
                ObjectModel(
                    object_id="vulnerability-a",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-10001",
                    properties={"title": "Ray issue A"},
                    created_revision=1,
                ),
                ObjectModel(
                    object_id="vulnerability-c",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-10002",
                    properties={"title": "Ray issue C"},
                    created_revision=1,
                ),
                ObjectModel(
                    object_id="unbacked-object",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-10003",
                    properties={"title": "Ray unverified"},
                    created_revision=1,
                ),
                ObjectModel(
                    object_id="superseded-object",
                    object_type="Vulnerability",
                    canonical_key="cve:CVE-2026-10004",
                    properties={"title": "Ray old"},
                    created_revision=1,
                    superseded_revision=1,
                ),
            ]
        )
        await session.flush()
        for suffix, object_id in (
            ("a", "vulnerability-a"),
            ("c", "vulnerability-c"),
            ("old", "superseded-object"),
        ):
            session.add(
                ClaimModel(
                    claim_id=f"claim-{suffix}",
                    subject_id=object_id,
                    predicate="description",
                    value="Ray issue",
                    origin="source_asserted",
                    lifecycle="accepted",
                    created_revision=1,
                )
            )
            session.add(
                EvidenceLinkModel(
                    evidence_link_id=f"link-{suffix}",
                    target_kind="claim",
                    target_id=f"claim-{suffix}",
                    observation_id="recommendation-observation",
                    locator={"field": "description"},
                    locator_hash=suffix,
                )
            )
        session.add(
            ClaimModel(
                claim_id="unsupported-claim",
                subject_id="unbacked-object",
                predicate="description",
                value="Ray unverified",
                origin="semantic",
                lifecycle="exploratory",
                created_revision=1,
            )
        )
        session.add(
            RelationModel(
                relation_id="relation-affects",
                source_object_id="vulnerability-a",
                target_object_id="product-ray",
                relation_type="affects",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="link-affects",
                target_kind="relation",
                target_id="relation-affects",
                observation_id="recommendation-observation",
                locator={"field": "affected"},
                locator_hash="affects",
            )
        )
    await seed_test_accounts(factory)
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers=account_headers()
        ) as client:
            yield client, factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_preferences_and_feedback_survive_reads_and_isolate_principals(
    recommendation_client,
) -> None:
    client, factory = recommendation_client
    owner = {**account_headers("owner")}
    other = {**account_headers("other")}
    path = "/api/v1/intelligence/preferences"
    body = {"keywords": [" Ray ", "ray"], "target_object_ids": ["product-ray"]}
    saved = await client.put(path, headers=owner, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["keywords"] == ["Ray"]
    assert saved.json()["target_objects"][0]["label"] == "Ray"
    replay = await client.put(path, headers=owner, json=body)
    assert replay.status_code == 200
    restored = await client.get(path, headers=owner)
    assert restored.json()["target_object_ids"] == ["product-ray"]
    assert (await client.get(path, headers=other)).json()["keywords"] == []
    feedback = "/api/v1/intelligence/recommendations/vulnerability-a/feedback"
    for _ in range(2):
        assert (
            await client.put(feedback, headers=owner, json={"feedback": "ignored"})
        ).status_code == 200
    recommendations = "/api/v1/intelligence/recommendations"
    page = await client.get(recommendations, headers=owner)
    assert "vulnerability-a" not in {item["object_id"] for item in page.json()["items"]}
    await client.put(path, headers=other, json={"keywords": ["Ray"]})
    foreign = await client.get(recommendations, headers=other)
    assert "vulnerability-a" in {item["object_id"] for item in foreign.json()["items"]}
    await client.put(feedback, headers=owner, json={"feedback": "neutral"})
    page = await client.get(recommendations, headers=owner)
    assert "vulnerability-a" in {item["object_id"] for item in page.json()["items"]}
    async with factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(IntelligencePreferenceModel)) == 2
        )
        assert (
            await session.scalar(select(func.count()).select_from(RecommendationFeedbackModel)) == 1
        )


@pytest.mark.asyncio
async def test_recommendations_explain_real_canonical_matches_with_evidence(recommendation_client):
    client, _factory = recommendation_client
    path = "/api/v1/intelligence"
    assert (await client.get(f"{path}/recommendations")).json()["items"] == []
    await client.put(
        f"{path}/preferences", json={"keywords": ["Ray"], "target_object_ids": ["product-ray"]}
    )
    page = await client.get(f"{path}/recommendations")
    assert page.status_code == 200, page.text
    payload = page.json()
    assert payload["knowledge_revision"] == 1
    items = {item["object_id"]: item for item in payload["items"]}
    assert "unbacked-object" not in items
    assert "superseded-object" not in items
    assert items["vulnerability-a"]["score"] > items["vulnerability-c"]["score"]
    reason = next(
        reason
        for reason in items["vulnerability-a"]["reasons"]
        if reason["kind"] == "related_object"
    )
    assert reason["value"] == "product-ray"
    assert reason["relation_id"] == "relation-affects"
    assert reason["evidence_refs"] == ["evidence:link-affects"]
    for item in items.values():
        refs = {row["evidence_ref"] for row in item["evidence"]}
        assert all(set(reason["evidence_refs"]) <= refs for reason in item["reasons"])
    await client.put(
        f"{path}/recommendations/vulnerability-c/feedback", json={"feedback": "interested"}
    )
    page = await client.get(f"{path}/recommendations")
    c = next(item for item in page.json()["items"] if item["object_id"] == "vulnerability-c")
    assert c["feedback"] == "interested"
    assert c["score"] == items["vulnerability-c"]["score"] + 20


@pytest.mark.asyncio
async def test_preference_and_feedback_validation_preserves_existing_profile(recommendation_client):
    client, _factory = recommendation_client
    path = "/api/v1/intelligence"
    await client.put(f"{path}/preferences", json={"keywords": ["Ray"]})
    missing = await client.put(f"{path}/preferences", json={"target_object_ids": ["missing"]})
    assert missing.status_code == 404
    assert (await client.get(f"{path}/preferences")).json()["keywords"] == ["Ray"]
    assert (await client.put(f"{path}/preferences", json={"keywords": ["  "]})).status_code == 422
    assert (
        await client.put(
            f"{path}/recommendations/missing/feedback", json={"feedback": "interested"}
        )
    ).status_code == 404
    assert (
        await client.put(
            f"{path}/recommendations/vulnerability-a/feedback", json={"feedback": "anything"}
        )
    ).status_code == 422
