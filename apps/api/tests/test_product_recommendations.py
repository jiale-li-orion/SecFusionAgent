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


@pytest.mark.asyncio
async def test_recommendation_preview_and_totals_use_all_evidence(recommendation_client):
    client, factory = recommendation_client
    published = datetime(2025, 1, 1, tzinfo=UTC)
    observed = datetime(2026, 1, 1, tzinfo=UTC)
    async with factory() as session, session.begin():
        observation = await session.get(ObservationModel, "recommendation-observation")
        observation.published_at = published
        observation.observed_at = observed
        session.add(
            SourceModel(
                source_id="second-preview-source",
                adapter_type="test",
                source_class="vendor",
                source_role="primary",
                source_family="fixture",
                access_mode="public",
                update_semantics="snapshot",
                retention_mode="durable_managed",
                schema_version="1",
                definition_hash="second",
                updated_at=observed,
            )
        )
        await session.flush()
        session.add(
            ObservationModel(
                observation_id="second-preview-observation",
                source_id="second-preview-source",
                external_object_id="second",
                acquisition_trigger="scheduled",
                published_at=datetime(2026, 9, 1, tzinfo=UTC),
                observed_at=datetime(2026, 9, 2, tzinfo=UTC),
                content_hash="second",
                idempotency_key="second",
                created_at=observed,
            )
        )
        await session.flush()
        for index in range(8):
            session.add(
                EvidenceLinkModel(
                    evidence_link_id=f"extra-{index}",
                    target_kind="claim",
                    target_id="claim-a",
                    observation_id=(
                        "second-preview-observation" if index == 7 else observation.observation_id
                    ),
                    locator={"index": index},
                    locator_hash=f"extra-{index}",
                )
            )
    await client.put("/api/v1/intelligence/preferences", json={"keywords": ["Ray"]})
    items = (await client.get("/api/v1/intelligence/recommendations")).json()["items"]
    item = next(row for row in items if row["object_id"] == "vulnerability-a")
    assert item["title"] == "Ray issue A"
    assert item["title_origin"] == "canonical_property"
    assert item["summary"] == "Ray issue"
    assert item["preview_origin"] == "accepted_claim"
    assert item["evidence_count"] == 9
    assert item["source_count"] == 2
    assert len(item["evidence"]) == 6
    assert len({row["source_id"] for row in item["evidence"]}) == 1
    assert item["timestamp_evidence_ref"] == item["preview_evidence_refs"][0]
    assert set(item["preview_evidence_refs"]) <= {e["evidence_ref"] for e in item["evidence"]}
    assert item["published_at"].startswith("2025-01-01")
    assert item["observed_at"].startswith("2026-01-01")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retained_text, expected",
    [
        ("Retained source passage about Ray.", "Retained source passage about Ray."),
        (
            "CATEGORY Insights Sort by: Recent Author last name Our Authors Eyal Rafian "
            "Read more from Eyal Rafian Unit 42 Read more from Unit 42",
            None,
        ),
    ],
)
async def test_recommendation_retained_excerpt_respects_public_access(
    recommendation_client,
    retained_text,
    expected,
):
    from packages.intelligence.storage.document_models import (
        DocumentChunkModel,
        DocumentModel,
        DocumentRevisionModel,
    )

    client, factory = recommendation_client
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        source = await session.get(SourceModel, "source:recommendation-fixture")
        source.access_rights = {"classification": "public"}
        claim = await session.get(ClaimModel, "claim-a")
        claim.predicate = "severity"
        claim.value = "high"
        session.add(
            DocumentModel(
                document_id="preview-document",
                object_id="vulnerability-a",
                source_id=source.source_id,
                external_object_id="fixture-advisory",
                created_at=now,
            )
        )
        await session.flush()
        session.add(
            DocumentRevisionModel(
                document_revision_id="preview-revision",
                document_id="preview-document",
                observation_id="recommendation-observation",
                title="Retained title",
                content_hash="preview",
                parser_name="fixture",
                parser_version="1",
                created_at=now,
            )
        )
        await session.flush()
        session.add(
            DocumentChunkModel(
                chunk_id="preview-chunk",
                document_revision_id="preview-revision",
                ordinal=0,
                text=retained_text,
                locator={"paragraph": 1},
                content_hash="preview",
                chunker_version="1",
            )
        )
    await client.put("/api/v1/intelligence/preferences", json={"keywords": ["Ray"]})

    async def read_item():
        items = (await client.get("/api/v1/intelligence/recommendations")).json()["items"]
        return next(row for row in items if row["object_id"] == "vulnerability-a")

    item = await read_item()
    assert item["summary"] == expected
    assert item["preview_origin"] == ("retained_excerpt" if expected else None)
    assert item["preview_evidence_refs"] == (["evidence:link-a"] if expected else [])
    assert item["preview_chunk_ref"] == (
        "document-chunk:preview-chunk@preview-revision" if expected else None
    )
    async with factory() as session, session.begin():
        source = await session.get(SourceModel, "source:recommendation-fixture")
        source.access_rights = {"classification": "restricted"}
    item = await read_item()
    assert item["summary"] is None
    assert item["preview_origin"] is None


@pytest.mark.asyncio
async def test_formation_groups_exact_commits_and_reports_missing_results(recommendation_client):
    from apps.application.queries.world_formation import read_world_formation
    from packages.intelligence.storage.knowledge_models import KnowledgeChangeModel
    from packages.intelligence.storage.models import ProcessingRunModel

    _client, factory = recommendation_client
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        for run_id, status in (
            ("committed", "running"),
            ("empty", "succeeded"),
            ("pending", "running"),
            ("missing", "succeeded"),
        ):
            session.add(
                ProcessingRunModel(
                    run_id=run_id,
                    processor_type="enrichment",
                    processor_name="fixture",
                    processor_version="1",
                    status=status,
                    started_at=now,
                )
            )
        for revision, run_id in (
            (2, "committed"),
            (3, "committed"),
            (4, "missing"),
            (5, "unrelated-run"),
        ):
            session.add(
                KnowledgeRevisionModel(
                    revision=revision, cause_processing_run_id=run_id, committed_at=now
                )
            )
        await session.flush()
        for revision in (2, 3, 5):
            session.add(
                KnowledgeChangeModel(
                    change_id=f"change-{revision}",
                    revision=revision,
                    changed_ids={
                        "objects": [],
                        "claims": ["claim-a"],
                        "relations": ["relation-affects"],
                    },
                    committed_at=now,
                )
            )
    async with factory() as session:
        result = await read_world_formation(session)
    items = {item.run_id: item.model_dump() for item in result.processing}
    item = items["committed"]
    assert item["commit_count"] == 2
    assert item["change_count"] == 2
    assert item["revision"] == 3
    assert item["commit_status"] == "committed"
    assert item["claim_count"] == 1
    assert item["relation_count"] == 1
    assert item["object_count"] == 0
    assert {obj["object_id"] for obj in item["affected_objects"]} == {
        "vulnerability-a",
        "product-ray",
    }
    assert item["results_complete"] is True
    assert items["empty"]["commit_status"] == "no_commit"
    assert items["empty"]["commit_count"] == 0
    assert items["pending"]["commit_status"] == "pending"
    assert items["pending"]["results_complete"] is False
    assert items["missing"]["results_complete"] is False
    assert items["missing"]["commit_count"] == 1


@pytest.mark.parametrize(
    ("properties", "title", "expected"),
    [
        (
            {
                "display_name": "One breach please and make no mistakes",
                "title": "Intelligence Center",
            },
            True,
            "One breach please and make no mistakes",
        ),
        ({"title": "Insights"}, True, None),
        (
            {
                "description": "CATEGORY Insights Sort by: Recent Author last name Our Authors "
                "Eyal Rafian Read more from Eyal Rafian Unit 42 Read more from Unit 42"
            },
            False,
            None,
        ),
    ],
)
def test_preview_rejects_navigation_and_preserves_specific_label(properties, title, expected):
    from apps.application.queries.recommendation_previews import canonical_preview

    obj = ObjectModel(
        object_id="preview",
        object_type="Report",
        canonical_key="report:preview",
        properties=properties,
        created_revision=1,
    )
    preview = canonical_preview(obj, [], {}, title=title)
    assert preview.text == expected


def test_preview_truncates_on_word_boundary():
    from apps.application.queries.recommendation_previews import canonical_preview

    description = "Security researchers documented " * 20
    obj = ObjectModel(
        object_id="preview",
        object_type="Report",
        canonical_key="report:preview",
        properties={"description": description},
        created_revision=1,
    )
    preview = canonical_preview(obj, [], {}, title=False)
    assert preview.text is not None
    assert len(preview.text) <= 320
    assert preview.text.endswith("…")
    assert description[len(preview.text.removesuffix("…"))] == " "


def test_preview_removes_repeated_heading_and_publication_metadata():
    from apps.application.queries.recommendation_previews import canonical_preview

    headline = "Building on our commitment to American scientific discovery"
    obj = ObjectModel(
        object_id="preview",
        object_type="Report",
        canonical_key="report:preview",
        properties={
            "title": f"Oct 8, 2026 Announcements {headline}",
            "summary": f"Announcements {headline} Oct 8, 2026 "
            "Anthropic is deepening its scientific research partnerships.",
        },
        created_revision=1,
    )
    assert canonical_preview(obj, [], {}, title=True).text == headline
    assert canonical_preview(obj, [], {}, title=False).text == (
        "Anthropic is deepening its scientific research partnerships."
    )


@pytest.mark.asyncio
async def test_dynamic_feed_modes_cursor_and_item_feedback(recommendation_client):
    client, _factory = recommendation_client
    base = "/api/v1/intelligence"
    await client.put(
        f"{base}/preferences", json={"keywords": ["Ray"], "target_object_ids": ["product-ray"]}
    )
    following = await client.get(f"{base}/feed?mode=following&limit=1")
    assert following.status_code == 200, following.text
    first = following.json()
    assert first["items"][0]["object_id"] in {"vulnerability-a", "vulnerability-c"}
    assert first["next_cursor"]
    second = (
        await client.get(f"{base}/feed?mode=following&limit=1&cursor={first['next_cursor']}")
    ).json()
    assert second["items"][0]["activity_id"] != first["items"][0]["activity_id"]
    item = first["items"][0]
    assert (
        await client.put(
            f"{base}/feed/{item['activity_id']}/feedback", json={"feedback": "ignored"}
        )
    ).status_code == 200
    assert item["activity_id"] not in {
        row["activity_id"] for row in (await client.get(f"{base}/feed")).json()["items"]
    }
    assert (await client.get(f"{base}/preferences")).json()["target_object_ids"] == ["product-ray"]
    assert "vulnerability-a" in {
        row["object_id"] for row in (await client.get(f"{base}/recommendations")).json()["items"]
    }
    assert (await client.get(f"{base}/feed?cursor=broken")).status_code == 422


@pytest.mark.asyncio
async def test_follow_resolution_uses_identity_and_keeps_ambiguity(recommendation_client):
    client, factory = recommendation_client
    base = "/api/v1/intelligence/follow-resolution"
    response = await client.get(base, params={"q": "Ray"})
    assert response.status_code == 200, response.text
    assert response.json()["exact_match"]["object_id"] == "product-ray"
    async with factory() as session, session.begin():
        session.add(
            ObjectModel(
                object_id="repo-ray",
                object_type="Repo",
                canonical_key="github:other/ray",
                properties={"name": "Ray"},
                created_revision=1,
            )
        )
    ambiguous = (await client.get(base, params={"q": "Ray"})).json()
    assert ambiguous["exact_match"] is None
    assert len(ambiguous["candidates"]) >= 2
    assert (await client.get(base, params={"q": "unknown topic"})).json()["candidates"] == []


@pytest.mark.asyncio
async def test_feed_ignores_metadata_and_repository_identity(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        obj = await session.get(ObjectModel, "vulnerability-c")
        obj.properties = {"title": "Unrelated vulnerability", "collector_debug": "secret-topic"}
    base = "/api/v1/intelligence"
    await client.put(
        f"{base}/preferences",
        json={"keywords": ["secret-topic"], "target_object_ids": ["product-ray"]},
    )
    following = await client.get(f"{base}/feed?mode=following")
    assert following.status_code == 200, following.text
    assert {row["object_id"] for row in following.json()["items"]} == {"vulnerability-a"}
    recommended = (await client.get(f"{base}/feed?mode=recommended")).json()
    assert "product-ray" not in {row["object_id"] for row in recommended["items"]}
    assert "vulnerability-c" in {row["object_id"] for row in recommended["items"]}


@pytest.mark.asyncio
async def test_feed_window_replay_and_feedback_principal_isolation(recommendation_client):
    client, factory = recommendation_client
    base = "/api/v1/intelligence"
    first = (await client.get(f"{base}/feed")).json()["items"][0]
    async with factory() as session, session.begin():
        obj = await session.get(ObjectModel, first["object_id"])
        obj.properties = {**obj.properties, "collector_attempts": 50}
    replay = (await client.get(f"{base}/feed")).json()["items"][0]
    assert replay["activity_id"] == first["activity_id"]
    await client.put(f"{base}/feed/{first['activity_id']}/feedback", json={"feedback": "ignored"})
    foreign = await client.get(f"{base}/feed", headers=account_headers("other"))
    assert first["activity_id"] in {item["activity_id"] for item in foreign.json()["items"]}
    async with factory() as session, session.begin():
        obs = await session.get(ObservationModel, "recommendation-observation")
        obs.published_at = datetime(2020, 1, 1, tzinfo=UTC)
    assert (await client.get(f"{base}/feed")).json()["items"] == []
    assert (await client.get(f"{base}/feed?window=all")).json()["items"]


@pytest.mark.asyncio
async def test_security_pr_requires_real_backed_vulnerability_relation(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        session.add(
            ObjectModel(
                object_id="security-pr",
                object_type="PullRequest",
                canonical_key="github:ray/ray:pr:1",
                properties={"title": "Fix CVE-2026-10001"},
                created_revision=1,
            )
        )
        session.add(
            ClaimModel(
                claim_id="pr-title",
                subject_id="security-pr",
                predicate="title",
                value="Fix CVE-2026-10001",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="pr-title-link",
                target_kind="claim",
                target_id="pr-title",
                observation_id="recommendation-observation",
                locator={"field": "title"},
                locator_hash="pr-title",
            )
        )
        session.add(
            RelationModel(
                relation_id="pr-reference",
                source_object_id="vulnerability-a",
                target_object_id="security-pr",
                relation_type="references-development-object",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
    path = "/api/v1/intelligence/feed"
    assert "security-pr" not in {
        item["object_id"] for item in (await client.get(path)).json()["items"]
    }
    async with factory() as session, session.begin():
        session.add(
            EvidenceLinkModel(
                evidence_link_id="pr-reference-link",
                target_kind="relation",
                target_id="pr-reference",
                observation_id="recommendation-observation",
                locator={"field": "references"},
                locator_hash="pr-reference",
            )
        )
    assert "security-pr" in {item["object_id"] for item in (await client.get(path)).json()["items"]}


@pytest.mark.asyncio
async def test_feed_recent_fix_of_old_cve_keeps_distinct_activity_time(recommendation_client):
    client, factory = recommendation_client
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        obs = await session.get(ObservationModel, "recommendation-observation")
        obs.published_at = datetime(2020, 1, 1, tzinfo=UTC)
        obs.observed_at = datetime(2020, 1, 2, tzinfo=UTC)
    assert (await client.get("/api/v1/intelligence/feed")).json()["items"] == []
    async with factory() as session, session.begin():
        session.add(
            ObservationModel(
                observation_id="current-fix",
                source_id="source:recommendation-fixture",
                external_object_id="new-fix",
                acquisition_trigger="scheduled",
                observed_at=now,
                published_at=datetime(2020, 1, 1, tzinfo=UTC),
                updated_at=now,
                content_hash="new-fix",
                idempotency_key="new-fix",
                created_at=now,
            )
        )
        session.add(
            RelationModel(
                relation_id="new-fix-relation",
                source_object_id="vulnerability-a",
                target_object_id="product-ray",
                relation_type="fixed-by",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="new-fix-link",
                target_kind="relation",
                target_id="new-fix-relation",
                observation_id="current-fix",
                locator={"field": "patch"},
                locator_hash="new-fix",
            )
        )
    rows = (await client.get("/api/v1/intelligence/feed")).json()["items"]
    row = next(item for item in rows if item["object_id"] == "vulnerability-a")
    assert row["published_at"].startswith("2020-01-01")
    assert row["activity_at"].startswith(now.strftime("%Y-%m-%d"))
    assert row["activity_evidence_ref"] == "evidence:new-fix-link"


@pytest.mark.asyncio
async def test_pr_does_not_borrow_advisory_excerpt_as_its_own_content(recommendation_client):
    from packages.intelligence.storage.document_models import (
        DocumentChunkModel,
        DocumentModel,
        DocumentRevisionModel,
    )

    client, factory = recommendation_client
    async with factory() as session, session.begin():
        session.add(
            ObjectModel(
                object_id="mundane-pr",
                object_type="PullRequest",
                canonical_key="github:ray/ray:pr:2",
                properties={"title": "Refactor parser"},
                created_revision=1,
            )
        )
        session.add(
            RelationModel(
                relation_id="mundane-pr-reference",
                source_object_id="vulnerability-a",
                target_object_id="mundane-pr",
                relation_type="references-development-object",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="mundane-pr-reference-link",
                target_kind="relation",
                target_id="mundane-pr-reference",
                observation_id="recommendation-observation",
                locator={"field": "references"},
                locator_hash="mundane-pr-reference",
            )
        )
    async with factory() as session, session.begin():
        source = await session.get(SourceModel, "source:recommendation-fixture")
        source.access_rights = {"classification": "public"}
        now = datetime.now(UTC)
        session.add(
            DocumentModel(
                document_id="advisory-doc",
                object_id="vulnerability-a",
                source_id=source.source_id,
                external_object_id="fixture-advisory",
                created_at=now,
            )
        )
        await session.flush()
        session.add(
            DocumentRevisionModel(
                document_revision_id="advisory-revision",
                document_id="advisory-doc",
                observation_id="recommendation-observation",
                title="Critical security vulnerability",
                content_hash="advisory",
                parser_name="fixture",
                parser_version="1",
                created_at=now,
            )
        )
        await session.flush()
        session.add(
            DocumentChunkModel(
                chunk_id="advisory-chunk",
                document_revision_id="advisory-revision",
                ordinal=0,
                text="This security advisory describes authentication bypass and CVE-2026-10001.",
                locator={"paragraph": 1},
                content_hash="advisory",
                chunker_version="1",
            )
        )
    rows = (await client.get("/api/v1/intelligence/feed")).json()["items"]
    assert "mundane-pr" not in {row["object_id"] for row in rows}


@pytest.mark.asyncio
async def test_native_release_name_and_legacy_ignore_compatibility(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        session.add(
            ObjectModel(
                object_id="security-release",
                object_type="Release",
                canonical_key="github:ray/ray:release:1",
                properties={"repo_full_name": "ray/ray", "tag_name": "v2.0.1"},
                created_revision=1,
            )
        )
        session.add(
            ClaimModel(
                claim_id="release-name",
                subject_id="security-release",
                predicate="github_release_name",
                value="Security release fixes authentication bypass",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="release-name-link",
                target_kind="claim",
                target_id="release-name",
                observation_id="recommendation-observation",
                locator={"field": "name"},
                locator_hash="release-name",
            )
        )
    rows = (await client.get("/api/v1/intelligence/feed")).json()["items"]
    release = next(row for row in rows if row["object_id"] == "security-release")
    assert release["title"] == "Security release fixes authentication bypass"
    assert release["title_evidence_refs"] == ["evidence:release-name-link"]
    await client.put(
        "/api/v1/intelligence/recommendations/security-release/feedback",
        json={"feedback": "ignored"},
    )
    assert "security-release" not in {
        row["object_id"] for row in (await client.get("/api/v1/intelligence/feed")).json()["items"]
    }


@pytest.mark.asyncio
async def test_topic_reason_cites_matching_body_not_unrelated_summary(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        obj = await session.get(ObjectModel, "vulnerability-c")
        obj.properties = {"title": "Unrelated title"}
        claim = await session.get(ClaimModel, "claim-c")
        claim.value = "Unrelated summary"
        session.add(
            ClaimModel(
                claim_id="matched-body",
                subject_id="vulnerability-c",
                predicate="body",
                value="Ray security issue",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="matched-body-link",
                target_kind="claim",
                target_id="matched-body",
                observation_id="recommendation-observation",
                locator={"field": "body"},
                locator_hash="matched-body",
            )
        )
    await client.put("/api/v1/intelligence/preferences", json={"keywords": ["Ray"]})
    rows = (await client.get("/api/v1/intelligence/feed?mode=following")).json()["items"]
    row = next(row for row in rows if row["object_id"] == "vulnerability-c")
    reason = next(reason for reason in row["reasons"] if reason["kind"] == "keyword")
    assert reason["evidence_refs"] == ["evidence:matched-body-link"]


@pytest.mark.asyncio
async def test_body_change_beyond_preview_creates_new_activity(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        claim = await session.get(ClaimModel, "claim-a")
        claim.value = "Security details. " * 50 + "Original finding."
    before = next(
        row
        for row in (await client.get("/api/v1/intelligence/feed")).json()["items"]
        if row["object_id"] == "vulnerability-a"
    )
    await client.put(
        f"/api/v1/intelligence/feed/{before['activity_id']}/feedback", json={"feedback": "ignored"}
    )
    async with factory() as session, session.begin():
        claim = await session.get(ClaimModel, "claim-a")
        claim.value = "Security details. " * 50 + "New material finding and mitigation."
    after = next(
        row
        for row in (await client.get("/api/v1/intelligence/feed")).json()["items"]
        if row["object_id"] == "vulnerability-a"
    )
    assert before["summary"] == after["summary"]
    assert before["activity_id"] != after["activity_id"]


@pytest.mark.asyncio
async def test_recollected_unchanged_fact_does_not_refresh_old_activity(recommendation_client):
    client, factory = recommendation_client
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        original = await session.get(ObservationModel, "recommendation-observation")
        original.published_at = datetime(2020, 1, 1, tzinfo=UTC)
        original.observed_at = datetime(2020, 1, 2, tzinfo=UTC)
        session.add(
            ObservationModel(
                observation_id="metadata-recollection",
                source_id="source:recommendation-fixture",
                external_object_id="fixture-advisory",
                acquisition_trigger="scheduled",
                observed_at=now,
                updated_at=now,
                content_hash="metadata-only",
                idempotency_key="metadata-only",
                created_at=now,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="recollected-claim",
                target_kind="claim",
                target_id="claim-a",
                observation_id="metadata-recollection",
                locator={"field": "description"},
                locator_hash="recollected",
            )
        )
    assert (await client.get("/api/v1/intelligence/feed")).json()["items"] == []


@pytest.mark.asyncio
async def test_duplicate_content_keeps_followed_representative_and_all_citations(
    recommendation_client,
):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        for suffix in ("a", "b"):
            session.add(
                ObjectModel(
                    object_id=f"duplicate-{suffix}",
                    object_type="Document",
                    canonical_key=f"document:{suffix}",
                    properties={"title": "Security report on isolation"},
                    created_revision=1,
                )
            )
            session.add(
                ClaimModel(
                    claim_id=f"duplicate-description-{suffix}",
                    subject_id=f"duplicate-{suffix}",
                    predicate="description",
                    value="A security report documenting an isolation vulnerability.",
                    origin="source_asserted",
                    lifecycle="accepted",
                    created_revision=1,
                )
            )
            session.add(
                EvidenceLinkModel(
                    evidence_link_id=f"duplicate-evidence-{suffix}",
                    target_kind="claim",
                    target_id=f"duplicate-description-{suffix}",
                    observation_id="recommendation-observation",
                    locator={"field": "description"},
                    locator_hash=f"duplicate-{suffix}",
                )
            )
    await client.put(
        "/api/v1/intelligence/preferences", json={"target_object_ids": ["duplicate-b"]}
    )
    rows = (await client.get("/api/v1/intelligence/feed?mode=recommended")).json()["items"]
    duplicates = [row for row in rows if row["title"] == "Security report on isolation"]
    assert len(duplicates) == 1
    row = duplicates[0]
    assert row["object_id"] == "duplicate-b"
    assert row["reasons"][0]["kind"] == "followed_object"
    assert row["reasons"][0]["value"] == "duplicate-b"
    assert row["score"] == 10
    assert {"evidence:duplicate-evidence-a", "evidence:duplicate-evidence-b"} <= {
        ref["evidence_ref"] for ref in row["evidence"]
    }
    assert rows[0]["object_id"] == "duplicate-b"


@pytest.mark.asyncio
async def test_security_landing_identity_is_not_a_feed_update(recommendation_client):
    client, factory = recommendation_client
    async with factory() as session, session.begin():
        session.add(
            ObjectModel(
                object_id="security-homepage",
                object_type="Document",
                canonical_key="document:homepage",
                properties={
                    "title": "Application and API security",
                    "url": "https://vendor.example/",
                },
                created_revision=1,
            )
        )
        session.add(
            ClaimModel(
                claim_id="homepage-description",
                subject_id="security-homepage",
                predicate="description",
                value="A security platform dashboard with product resources.",
                origin="source_asserted",
                lifecycle="accepted",
                created_revision=1,
            )
        )
        session.add(
            EvidenceLinkModel(
                evidence_link_id="homepage-evidence",
                target_kind="claim",
                target_id="homepage-description",
                observation_id="recommendation-observation",
                locator={"field": "description"},
                locator_hash="homepage",
            )
        )
    rows = (await client.get("/api/v1/intelligence/feed")).json()["items"]
    assert "security-homepage" not in {row["object_id"] for row in rows}
