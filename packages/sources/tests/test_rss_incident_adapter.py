from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.rss_incident import RSSIncidentAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceState
from packages.sources.registry.loader import load_source_definitions

FEED = Path("tests/fixtures/incident_rss.xml").read_text()
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "bleepingcomputer-news"
).model_copy(update={"discovery_method": {"feed_url": "https://feed.example.test/rss"}})


@pytest.mark.asyncio
async def test_rss_incident_discovery_extracts_verifiable_anchors() -> None:
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        return httpx.Response(200, text=FEED, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RSSIncidentAdapter(client)
        batch = await adapter.discover(SOURCE, SourceState())
        assert len(batch.items) == 2
        by_id = {item.external_object_id: item for item in batch.items}
        cve = by_id["news-42424"]
        chain = by_id["news-chain-1"]
        assert cve.inline_payload is not None
        assert cve.inline_payload["anchors"] == {"cve": ["CVE-2026-42424"]}
        assert chain.inline_payload is not None
        assert chain.inline_payload["anchors"] == {"tx_hash": ["0x" + "a" * 64]}
        assert "SecFusionAgent" in seen_headers[0]["user-agent"]

        envelope = await adapter.fetch(
            SOURCE,
            cve,
            acquisition_run_id="rss-run",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.json_payload["event_type"] == "reported"
        assert envelope.external_revision == cve.external_revision

        replay = await adapter.discover(SOURCE, SourceState(cursor=batch.next_cursor))
        assert replay.items == []
