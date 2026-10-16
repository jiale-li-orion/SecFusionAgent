from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.dependencies import SessionDep
from apps.api.routes.reports import html_report_response
from apps.application.public_briefings import visible_brief
from apps.application.queries.reports import report_sources
from packages.reasoning.briefing_store import IntelligenceBriefModel
from packages.reasoning.report_html import ReportDocument, render_report_html
from packages.reasoning.storage import DecisionResultStore

router = APIRouter(prefix="/api/v1/intelligence/briefs", tags=["intelligence"])


class PublicBriefView(BaseModel):
    brief_id: str
    title: str
    topic: str
    summary: str | None = None
    excerpt: str
    created_at: datetime
    window_start: datetime | None = None
    window_end: datetime | None = None
    source_count: int
    report_url: str


@router.get("", response_model=list[PublicBriefView])
async def list_public_briefs(session: SessionDep, limit: int = Query(6, ge=1, le=12)):
    items: list[PublicBriefView] = []
    editions: set[tuple[object, ...]] = set()
    # Scan bounded pages, not just limit*3 rows: old editions must not crowd
    # other topics out of the first page. Rights/revision checks remain read-time.
    batch_size = max(12, limit * 3)
    scan_cap = 120
    for offset in range(0, scan_cap, batch_size):
        take = min(batch_size, scan_cap - offset)
        rows = list(
            await session.scalars(
                select(IntelligenceBriefModel)
                .where(IntelligenceBriefModel.status == "published")
                .order_by(
                    IntelligenceBriefModel.created_at.desc(), IntelligenceBriefModel.brief_id.desc()
                )
                .offset(offset)
                .limit(take)
            )
        )
        for row in rows:
            edition = (
                row.topic,
                tuple(sorted(str(item["document_id"]) for item in row.material_manifest)),
                row.window_start,
                row.window_end,
            )
            if edition in editions or await visible_brief(session, row.brief_id) is None:
                continue
            decision = await DecisionResultStore().get_optional(session, row.decision_id)
            if decision is None:
                continue
            editions.add(edition)
            items.append(
                PublicBriefView(
                    brief_id=row.brief_id,
                    title=row.title,
                    topic=row.topic,
                    summary=decision.report_summary.text if decision.report_summary else None,
                    excerpt=decision.report_summary.text
                    if decision.report_summary
                    else (decision.report_paragraphs[0].text if decision.report_paragraphs else ""),
                    created_at=row.created_at,
                    window_start=row.window_start,
                    window_end=row.window_end,
                    source_count=len({item["source_id"] for item in row.material_manifest}),
                    report_url=f"/api/v1/intelligence/briefs/{row.brief_id}/report.html",
                )
            )
            if len(items) == limit:
                return items
        if len(rows) < take:
            break
    return items


@router.get("/{brief_id}/report.html", response_class=HTMLResponse)
async def public_brief_report(brief_id: str, session: SessionDep) -> HTMLResponse:
    row = await visible_brief(session, brief_id)
    if row is None:
        raise HTTPException(status_code=404, detail="report unavailable or awaiting source review")
    decision = await DecisionResultStore().get(session, row.decision_id)
    report = ReportDocument.model_validate(decision.model_dump())
    sources = await report_sources(session, report.citations)
    return html_report_response(
        render_report_html(report, sources=sources, title=row.title, public=True)
    )
