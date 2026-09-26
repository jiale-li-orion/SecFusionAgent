from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from packages.intelligence.incident.contracts import GenericNewsSignalExtractor
from packages.sources.adapters.html_incident import HTMLIncidentAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    RetentionMode,
    SourceDefinition,
    SourceRole,
    SourceState,
)

SOURCE = SourceDefinition(
    source_id="blockbeats-test",
    adapter_type="html_incident",
    source_class="incident_news",
    authority_scope=["breaking_signal"],
    source_role=SourceRole.SIGNAL,
    source_family="blockbeats",
    access_mode="html_index",
    update_semantics="list_item_revision",
    discovery_method={
        "index_url": "https://www.theblockbeats.info/newsflash/",
        "link_selector": "a[href^='/flash/']",
        "title_strip_regex": r"^\d{2}:\d{2}\s+",
        "allowed_hosts": ["www.theblockbeats.info"],
        "max_items": 10,
    },
    retention_mode=RetentionMode.INCIDENT_SIGNAL,
)

PAGE = """
<html><body>
  <a href="/flash/1">00:57 Protocol hit by CVE-2026-42424,
  funds moved to 0x1111111111111111111111111111111111111111</a>
  <a href="/flash/2">00:45 Market update</a>
  <a href="https://evil.example/x">00:30 external</a>
</body></html>
"""


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/newsflash/":
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html"})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_html_incident_discovery_and_m2_anchor_extraction() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HTMLIncidentAdapter(client)
        first = await adapter.discover(SOURCE, SourceState())
        assert len(first.items) == 2
        assert first.items[0].inline_payload is not None
        assert first.items[0].inline_payload["title"].startswith("Protocol hit by")
        assert not first.items[0].inline_payload["title"].startswith("00:57")

        replay = await adapter.discover(SOURCE, SourceState(cursor=first.next_cursor))
        assert replay.items == []

        envelope = await adapter.fetch(
            SOURCE,
            first.items[0],
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        signal = GenericNewsSignalExtractor().extract(SOURCE, envelope)
        assert signal.anchors["cve"] == ["CVE-2026-42424"]
        assert signal.anchors["address"] == ["0x1111111111111111111111111111111111111111"]
        assert signal.source_family == "blockbeats"
