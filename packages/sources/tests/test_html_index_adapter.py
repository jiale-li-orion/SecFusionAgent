from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from packages.sources.adapters.html_index import HTMLIndexAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    QuerySpec,
    RetentionMode,
    SourceDefinition,
    SourceRole,
    SourceState,
)

SOURCE = SourceDefinition(
    source_id="vendor-security-html",
    adapter_type="html_index",
    source_class="vendor_security_research",
    authority_scope=["security_advisory", "technical_analysis"],
    source_role=SourceRole.FORENSIC,
    source_family="example-security",
    access_mode="html_index",
    update_semantics="mutable_article",
    discovery_method={
        "index_url": "https://security.example.test/research",
        "item_selector": "article.card",
        "link_selector": "a.title",
        "title_selector": "h2",
        "allowed_hosts": ["security.example.test"],
        "max_items": 10,
    },
    retention_mode=RetentionMode.DURABLE_MANAGED,
)

INDEX = """
<html><body><main>
  <article class="card"><h2>Incident A</h2><a class="title" href="/research/a">read</a></article>
  <article class="card"><h2>Incident B</h2><a class="title" href="https://security.example.test/research/b">read</a></article>
  <article class="card"><h2>External</h2><a class="title" href="https://evil.example/x">read</a></article>
</main></body></html>
"""
ARTICLE = (
    b"<html><body><article><h1>Incident A</h1><p>Root cause details.</p></article></body></html>"
)


def _transport(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/research":
        return httpx.Response(200, text=INDEX, headers={"content-type": "text/html"})
    if request.url.path == "/research/a":
        return httpx.Response(
            200,
            content=ARTICLE,
            headers={
                "content-type": "text/html; charset=utf-8",
                "etag": '"article-a-v2"',
                "last-modified": "Fri, 26 Sep 2026 03:00:00 GMT",
            },
        )
    if request.url.path == "/research/b":
        return httpx.Response(200, content=ARTICLE, headers={"content-type": "text/html"})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_html_index_discovery_cursor_and_fetch() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        adapter = HTMLIndexAdapter(client)
        first = await adapter.discover(SOURCE, SourceState())
        assert len(first.items) == 2
        assert [item.locator["title"] for item in first.items] == ["Incident A", "Incident B"]
        assert all("evil.example" not in (item.canonical_url or "") for item in first.items)

        replay = await adapter.discover(SOURCE, SourceState(cursor=first.next_cursor))
        assert replay.items == []

        envelope = await adapter.fetch(
            SOURCE,
            first.items[0],
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.media_type == "text/html"
        assert envelope.body == ARTICLE
        assert envelope.external_revision == '"article-a-v2"'
        assert envelope.updated_at == datetime(2026, 9, 26, 3, 0, tzinfo=UTC)
        assert envelope.request_metadata["title"] == "Incident A"


@pytest.mark.asyncio
async def test_html_index_revalidates_unchanged_window_after_bounded_interval() -> None:
    current = [datetime(2026, 9, 26, 0, 0, tzinfo=UTC)]
    source = SOURCE.model_copy(
        update={"schedule_policy": {"enabled": True, "interval_seconds": 21600}}
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        adapter = HTMLIndexAdapter(client, now=lambda: current[0])
        first = await adapter.discover(source, SourceState())
        assert len(first.items) == 2
        assert first.next_cursor["last_revalidated_at"] == current[0].isoformat()

        current[0] += timedelta(hours=6)
        replay = await adapter.discover(source, SourceState(cursor=first.next_cursor))
        assert replay.items == []
        assert replay.next_cursor["last_revalidated_at"] == first.next_cursor["last_revalidated_at"]

        current[0] += timedelta(hours=18)
        revalidated = await adapter.discover(source, SourceState(cursor=replay.next_cursor))
        assert len(revalidated.items) == 2
        assert revalidated.next_cursor["last_revalidated_at"] == current[0].isoformat()


@pytest.mark.asyncio
async def test_html_index_query_enforces_allowed_host() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        adapter = HTMLIndexAdapter(client)
        result = await adapter.query(
            SOURCE,
            QuerySpec(filters={"url": "https://security.example.test/research/a"}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
        assert len(result) == 1
        with pytest.raises(ValueError, match="allowed_hosts"):
            await adapter.query(
                SOURCE,
                QuerySpec(filters={"url": "https://evil.example/x"}),
                acquisition_run_id=str(uuid4()),
                trigger=AcquisitionTrigger.INVESTIGATION,
            )


@pytest.mark.asyncio
async def test_html_index_can_fetch_configured_pdf_document() -> None:
    source = SOURCE.model_copy(
        update={
            "discovery_method": {
                **SOURCE.discovery_method,
                "allowed_media_types": ["text/html", "application/pdf"],
            }
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/research":
            return httpx.Response(
                200,
                text=(
                    '<article class="card"><h2>System card</h2>'
                    '<a class="title" href="/cards/model.pdf">read</a></article>'
                ),
                headers={"content-type": "text/html"},
                request=request,
            )
        if request.url.path == "/cards/model.pdf":
            return httpx.Response(
                200,
                content=b"%PDF-1.7 fixture",
                headers={"content-type": "application/pdf"},
                request=request,
            )
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HTMLIndexAdapter(client)
        batch = await adapter.discover(source, SourceState())
        envelope = await adapter.fetch(
            source,
            batch.items[0],
            acquisition_run_id="00000000-0000-0000-0000-000000000009",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
    assert envelope.media_type == "application/pdf"
    assert envelope.body == b"%PDF-1.7 fixture"
