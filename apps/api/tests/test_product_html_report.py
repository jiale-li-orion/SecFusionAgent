from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import database_session
from apps.api.main import create_app
from apps.api.tests.account_fixtures import account_headers
from apps.api.tests.test_product_questions import NOW, _database
from apps.application.question_sessions import QuestionSessionModel, QuestionSessionTurnModel
from packages.reasoning.decision import DecisionReportParagraph, DecisionResult
from packages.reasoning.storage import DecisionResultStore


async def test_html_report_uses_existing_account_boundary_and_security_headers():
    engine, factory = await _database()
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[database_session] = override_session
    try:
        async with factory() as session, session.begin():
            session.add(
                QuestionSessionModel(
                    session_id="report-session",
                    principal="user:test",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await session.flush()
            session.add(
                QuestionSessionTurnModel(
                    turn_id="report-turn",
                    session_id="report-session",
                    turn_index=1,
                    request_id="report-request",
                    question="private analysis",
                    task_kind="retrieve",
                    target_object_ids=[],
                    decision_ref="report-decision",
                    created_at=NOW,
                )
            )
            await DecisionResultStore().persist(
                session,
                DecisionResult(
                    decision_id="report-decision",
                    case_id="ephemeral-case",
                    case_revision=0,
                    report_paragraphs=[DecisionReportParagraph(text="仅账户可见的研究结果。")],
                    unknowns=["尚未获得外部确认。"],
                    stop_reason="partial_evidence",
                    model_prompt_revision="test-report",
                ),
            )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            path = "/api/v1/decisions/report-decision/report.html"
            response = await client.get(path, headers=account_headers())
            assert response.status_code == 200, response.text
            assert "text/html" in response.headers["content-type"]
            assert "仅账户可见" in response.text and "尚未获得外部确认" in response.text
            assert "script-src 'none'" in response.headers["content-security-policy"]
            assert "no-store" in response.headers["cache-control"]
            assert response.headers["x-content-type-options"] == "nosniff"
            assert (await client.get(path, headers=account_headers("other"))).status_code == 404
            client.cookies.clear()
            assert (await client.get(path)).status_code == 401
    finally:
        await engine.dispose()
