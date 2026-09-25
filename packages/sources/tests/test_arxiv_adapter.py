from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.arxiv import ArxivAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceState
from packages.sources.registry.loader import load_source_definitions

FEED = Path("tests/fixtures/arxiv_feed.xml").read_text()
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "arxiv-ai-security"
)


@pytest.mark.asyncio
async def test_arxiv_discovery_tracks_version_and_fetches_pdf_bytes() -> None:
    pdf = b"%PDF-1.4\nsynthetic-fixture\n%%EOF\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/query"):
            return httpx.Response(
                200,
                text=FEED,
                headers={"content-type": "application/atom+xml"},
                request=request,
            )
        return httpx.Response(
            200,
            content=pdf,
            headers={"content-type": "application/pdf"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ArxivAdapter(client)
        batch = await adapter.discover(SOURCE, SourceState())
        assert len(batch.items) == 1
        ref = batch.items[0]
        assert ref.external_object_id == "2609.12345"
        assert ref.external_revision == "2609.12345v2"
        assert ref.locator["authors"] == ["Alice Example", "Bob Example"]
        assert batch.next_cursor == {"latest_updated": "2026-09-25T08:30:00+00:00"}

        envelope = await adapter.fetch(
            SOURCE,
            ref,
            acquisition_run_id="arxiv-run",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.media_type == "application/pdf"
        assert envelope.body == pdf
        assert envelope.payload is None
        assert envelope.external_object_id == "2609.12345"
        assert (
            envelope.request_metadata["title"] == "Agent Security Under Indirect Prompt Injection"
        )


@pytest.mark.asyncio
async def test_arxiv_discovery_stops_at_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FEED, request=request)

    state = SourceState(cursor={"latest_updated": "2026-09-25T08:30:00+00:00"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await ArxivAdapter(client).discover(SOURCE, state)
    assert batch.items == []
    assert batch.next_cursor == {"latest_updated": "2026-09-25T08:30:00+00:00"}
