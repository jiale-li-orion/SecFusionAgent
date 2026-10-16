from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from apps.api.dependencies import RequestContextDep, SessionDep
from apps.api.errors import ProblemDetail
from apps.api.routes.reports import html_report_response
from apps.application.queries.decisions import DecisionQueries
from apps.application.queries.reports import report_sources
from apps.application.views.investigations import DecisionView
from packages.reasoning.report_html import ReportDocument, render_report_html

router = APIRouter(prefix="/api/v1/decisions", tags=["questions"])


@router.get(
    "/{decision_id}",
    response_model=DecisionView,
    responses={404: {"model": ProblemDetail}},
)
async def get_decision(
    decision_id: str, session: SessionDep, context: RequestContextDep
) -> DecisionView:
    return await DecisionQueries().get(session, decision_id, principal=context.principal)


@router.get("/{decision_id}/report.html", response_class=HTMLResponse)
async def get_decision_report(
    decision_id: str,
    session: SessionDep,
    context: RequestContextDep,
) -> HTMLResponse:
    decision = await DecisionQueries().get(session, decision_id, principal=context.principal)
    report = ReportDocument.model_validate(decision.model_dump())
    sources = await report_sources(session, report.citations)
    return html_report_response(render_report_html(report, sources=sources))
