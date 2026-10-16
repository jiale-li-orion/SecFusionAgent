"""Deterministic HTML presentation of a validated, immutable Decision.

Model output is text and a bounded composition, never executable HTML. The same
renderer serves account-owned investigations and explicitly published intelligence.
"""

import json
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from packages.reasoning.citation import DecisionCitation
from packages.reasoning.decision import DecisionConclusion, DecisionReportParagraph
from packages.reasoning.report_layout import ReportLayout

RENDERER_VERSION = "report-html-v4"


class ReportSource(BaseModel):
    evidence_ref: str
    label: str
    url: str | None = None
    detail: str | None = None
    revision_id: str | None = None


class ReportDocument(BaseModel):
    decision_id: str
    case_revision: int
    created_at: datetime
    conclusions: list[DecisionConclusion] = Field(default_factory=list)
    citations: list[DecisionCitation] = Field(default_factory=list)
    report_summary: DecisionReportParagraph | None = None
    report_paragraphs: list[DecisionReportParagraph] = Field(default_factory=list)
    report_layout: ReportLayout | None = None
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    stop_reason: str


def safe_source_url(value: str | None) -> str | None:
    if not value or any(ord(char) < 32 for char in value) or "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return None


def render_report_html(
    report: ReportDocument,
    *,
    sources: list[ReportSource] | None = None,
    title: str | None = None,
    public: bool = False,
) -> str:
    layout = report.report_layout
    heading = title or (layout.title if layout else "研究报告")
    source_map = {source.evidence_ref: source for source in sources or []}
    refs = list(dict.fromkeys(citation.evidence_ref for citation in report.citations))
    groups: dict[tuple[str, str], list[str]] = {}
    for ref in refs:
        source = source_map.get(ref)
        key = (
            (source.url or "", source.revision_id) if source and source.revision_id else (ref, ref)
        )
        groups.setdefault(key, []).append(ref)
    positions = {ref: index + 1 for index, group in enumerate(groups.values()) for ref in group}

    def notes(evidence_refs: list[str]) -> str:
        referenced: dict[int, list[str]] = {}
        for ref in dict.fromkeys(evidence_refs):
            if ref in positions:
                referenced.setdefault(positions[ref], []).append(ref)
        links = [
            f'<a href="#source-{position}" aria-label="来源 {position}" '
            f'data-evidence-refs="{escape(json.dumps(exact_refs), quote=True)}">'
            f"{position:02d}</a>"
            for position, exact_refs in referenced.items()
        ]
        return '<span class="notes">' + "".join(links) + "</span>" if links else ""

    def paragraph(index: int) -> str:
        item = report.report_paragraphs[index]
        return f"<p>{escape(item.text)}{notes(item.evidence_refs)}</p>"

    content: list[str] = []
    if report.report_summary:
        summary = report.report_summary
        content.append(
            f'<div class="report-summary"><p>{escape(summary.text)}'
            f'{notes(summary.evidence_refs)}</p></div>'
        )
    if report.report_paragraphs:
        if layout and layout.sections and layout.covers(len(report.report_paragraphs)):
            for section in layout.sections:
                content.append(f"<section><h2>{escape(section.heading)}</h2>")
                content.extend(paragraph(index) for index in section.paragraph_indices)
                content.append("</section>")
        else:
            content.extend(paragraph(index) for index in range(len(report.report_paragraphs)))
    else:
        labels = {"fact": "事实", "inference": "分析", "recommendation": "建议"}
        for item in report.conclusions:
            content.append(
                f"<section><h2>{labels[item.type.value]}</h2>"
                f"<p>{escape(item.statement)}{notes(item.evidence_refs)}</p></section>"
            )
    if not content:
        content.append("<p>目前尚无可交付的研究结论。</p>")

    for label, items in (
        ("来源分歧", report.conflicts),
        ("尚待确认", report.unknowns),
        ("判断前提", report.assumptions),
    ):
        if items:
            content.append(f'<section class="boundary"><h2>{label}</h2>')
            content.extend(f"<p>{escape(item)}</p>" for item in items)
            content.append("</section>")

    source_html = []
    for group in groups.values():
        ref = group[0]
        citation = next(item for item in report.citations if item.evidence_ref == ref)
        source = source_map.get(ref)
        url = safe_source_url(source.url if source else citation.source_ref)
        label = (
            source.label if source else (urlsplit(url).hostname if url else None)
        ) or "留存证据"
        label_html = escape(label or "留存证据")
        if url:
            label_html = (
                f'<a href="{escape(url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{label_html}</a>'
            )
        detail = source.detail if source else citation.locator.get("section")
        detail_html = f"<p>{escape(str(detail))}</p>" if detail else ""
        retained = "".join(
            f'<p data-evidence-ref="{escape(item, quote=True)}">'
            f"{escape(source_map[item].detail or '证据片段') if item in source_map else '证据片段'}"
            f" · {escape(item)}</p>"
            for item in group
        )
        retained = "<details><summary>留存证据坐标</summary>" + retained + "</details>"
        source_html.append(
            f'<div class="source" id="source-{positions[ref]}">'
            f"<span>{positions[ref]:02d}</span><div>{label_html}{detail_html}{retained}</div></div>"
        )
    if source_html:
        content.append(
            '<section class="sources"><h2>来源与依据</h2>' + "".join(source_html) + "</section>"
        )
    if report.report_paragraphs and report.conclusions:
        content.append('<details class="audit"><summary>核对原始结论</summary>')
        for item in report.conclusions:
            label = {"fact": "事实", "inference": "推断", "recommendation": "建议"}[item.type]
            content.append(
                f"<p><strong>{label}</strong> {escape(item.statement)}"
                f"{notes(item.evidence_refs)}</p>"
            )
        content.append("</details>")
    style = layout.style if layout else "editorial"
    scope = "公开情报" if public else "研究报告"
    created_at = report.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    timestamp = created_at.isoformat(timespec="minutes")
    display_time = created_at.astimezone(timezone(timedelta(hours=8))).strftime(
        "%Y年%m月%d日 %H:%M"
    )
    identity = escape(report.decision_id)
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        f"<title>{escape(heading)} · SecFusion</title><style>{REPORT_CSS}</style></head>"
        f'<body class="{style}"><main><header><a class="brand" href="/">SecFusion</a>'
        f'<span class="edition">{scope}</span><h1>{escape(heading)}</h1>'
        f'<p class="dateline">报告生成于 <time datetime="{timestamp}">{display_time}</time>'
        " · 北京时间"
        " · 事件日期以正文及来源为准</p></header><article>"
        + "".join(content)
        + "</article><footer><span>SecFusion · 证据与研判</span>"
        f"<details><summary>版本记录</summary><p>{identity}</p>"
        f"<p>研究版本 {report.case_revision} · {RENDERER_VERSION}</p></details>"
        "</footer></main></body></html>"
    )


def report_etag(html: str) -> str:
    return '"' + sha256(html.encode()).hexdigest() + '"'


REPORT_CSS = """
.report-summary{font-size:1.2em;line-height:1.85;color:#284e52;margin:0 0 2.8rem;padding:0 0 1.8rem;
border-bottom:1px solid #cbd6d1}
@font-face{font-family:ReportSans;src:url('/api/v1/reports/fonts/regular.woff2') format('woff2');
font-weight:400;font-display:swap}
@font-face{font-family:ReportSans;src:url('/api/v1/reports/fonts/bold.woff2') format('woff2');
font-weight:700;font-display:swap}
:root{color-scheme:light;--paper:#f6f3ed;--ink:#243b3a;--muted:#626f69;--accent:#356b59}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;color:var(--ink);background:var(--paper);font:400 17px/1.95 ReportSans,sans-serif;
overflow-wrap:anywhere}body:before{content:'';position:absolute;inset:0 0 auto;height:5px;
background:linear-gradient(90deg,#244f45 0 38%,#aebbaa 38% 78%,#d7c7ad 78%)}
main{max-width:1080px;margin:auto;padding:60px 7vw 32px}header{position:relative;
padding:0 0 38px;border-bottom:1px solid #c6cec5;margin-bottom:42px}
.brand{font-size:21px;font-weight:700;letter-spacing:-.05em;text-decoration:none;color:var(--ink)}
.edition{float:right;color:var(--accent);font-size:14px;letter-spacing:.12em}
h1{max-width:860px;font-size:clamp(30px,4.2vw,52px);line-height:1.4;letter-spacing:-.035em;
font-weight:700;margin:46px 0 24px;text-wrap:balance}
.dateline{font-size:13px;color:var(--muted);line-height:1.8;margin:0}
article{max-width:780px;margin:auto}article>p:first-child{font-size:20px;line-height:1.9}
p{margin:0 0 25px;white-space:pre-line}h2{font-size:20px;line-height:1.6;
font-weight:700;margin:42px 0 18px;color:var(--accent)}section{break-inside:auto}
.notes{display:inline-flex;gap:6px;margin-left:8px;vertical-align:super;font-size:11px;
line-height:1.8}.notes a{padding:1px 5px;text-decoration:none;border-bottom:1px solid #98b3a1}
a{color:var(--accent);text-underline-offset:5px}a:hover{text-decoration-thickness:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:5px}
.boundary{padding-left:22px;border-left:2px solid #a5b59f;margin:36px 0}
.boundary h2{font-size:16px;margin:0 0 12px}.boundary p{font-size:16px;margin-bottom:12px}
.sources{margin-top:52px;padding-top:2px;border-top:1px solid #c6cec5}
.source{display:grid;grid-template-columns:36px 1fr;gap:12px;margin:22px 0;font-size:15px}
.source>span{font-size:12px;color:var(--muted);padding-top:4px}.source p{font-size:13px;
color:var(--muted);margin:4px 0;line-height:1.7}summary{cursor:pointer;padding:12px 0;
font-size:14px;color:var(--muted)}.audit{margin-top:32px}.audit p{font-size:15px}
.audit strong{color:var(--accent);font-size:13px;margin-right:6px}
footer{margin-top:64px;padding-top:24px;border-top:1px solid #c6cec5;color:var(--muted);
display:flex;justify-content:space-between;align-items:flex-start;gap:24px;font-size:12px}
footer details{max-width:60%}footer summary{font-size:12px;padding:0}footer p{margin:12px 0 0}
.briefing article>section:not(.boundary):not(.sources){counter-increment:story}
.briefing article>section:not(.boundary):not(.sources)>h2:before{
content:counter(story,decimal-leading-zero);
font-size:12px;margin-right:16px;color:var(--muted)}
@media(max-width:600px){main{padding:34px 24px 24px}h1{margin-top:36px}
header{margin-bottom:28px}body{font-size:16px}article>p:first-child{font-size:18px}
.dateline{font-size:12px}.boundary{padding-left:16px}footer{display:block}
footer details{max-width:100%}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{body{background:white;color:#20302b;font-size:11pt}main{max-width:none;padding:0}
header{padding-bottom:18px;margin-bottom:24px}h1{font-size:28pt;margin-top:26px}
h2{break-after:avoid}p{orphans:3;widows:3}a{color:inherit}.sources{break-before:auto}
footer{margin-top:28px}.audit{display:none}.notes{font-size:8pt}}
"""
