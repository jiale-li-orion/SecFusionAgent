from httpx import ASGITransport, AsyncClient

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.application.public_briefings import publish_briefing
from apps.application.tests.test_public_briefings import BoundProvider
from apps.application.tests.test_public_briefings import briefing_db as briefing_db
from packages.reasoning.briefing import BriefingGenerator


async def test_public_report_is_anonymous_and_cannot_expose_arbitrary_decisions(briefing_db):
    factory, doc_id, _ = briefing_db
    report = await publish_briefing(
        factory, BriefingGenerator(BoundProvider()), topic="Agent safety", document_ids=[doc_id]
    )
    app = create_app()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/v1/intelligence/briefs")
        assert listing.status_code == 200
        assert listing.json()[0]["brief_id"] == report.brief_id
        assert listing.json()[0]["summary"] == "厂商在模拟环境进行了 12 项 Agent 测试。"
        assert listing.json()[0]["excerpt"] == listing.json()[0]["summary"]
        html = await client.get(listing.json()[0]["report_url"])
        assert html.status_code == 200
        assert "公开情报" in html.text and "模拟环境" in html.text
        assert "https://example.org/report" in html.text
        assert (
            await client.get(f"/api/v1/intelligence/briefs/{report.decision_id}/report.html")
        ).status_code == 404
        assert (await client.get("/api/v1/reports/fonts/regular.woff2")).status_code == 200


async def test_public_list_shows_latest_edition_for_same_topic_and_documents(briefing_db):
    factory, doc_id, _ = briefing_db
    first = await publish_briefing(
        factory, BriefingGenerator(BoundProvider()), topic="Safety", document_ids=[doc_id]
    )
    revised = BoundProvider()
    revised.version = "new-policy-model"
    latest = await publish_briefing(
        factory, BriefingGenerator(revised), topic="Safety", document_ids=[doc_id]
    )
    app = create_app()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = (await client.get("/api/v1/intelligence/briefs")).json()
        assert [item["brief_id"] for item in listing] == [latest.brief_id]
        assert (
            await client.get(f"/api/v1/intelligence/briefs/{first.brief_id}/report.html")
        ).status_code == 200


async def test_report_editions_do_not_crowd_out_other_topics(briefing_db):
    factory, doc_id, _ = briefing_db
    other = await publish_briefing(
        factory, BriefingGenerator(BoundProvider()), topic="Other topic", document_ids=[doc_id]
    )
    for version in range(14):
        provider = BoundProvider()
        provider.version = str(version)
        await publish_briefing(
            factory, BriefingGenerator(provider), topic="Repeated topic", document_ids=[doc_id]
        )
    app = create_app()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        items = (await client.get("/api/v1/intelligence/briefs?limit=2")).json()
        assert len(items) == 2
        assert items[1]["brief_id"] == other.brief_id
