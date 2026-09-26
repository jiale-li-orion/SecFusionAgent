from __future__ import annotations

import httpx
import pytest

from packages.intelligence.incident.contracts import GenericNewsSignalExtractor
from packages.sources.adapters.slowmist_hacked import SlowMistHackedAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceDefinition, SourceState

SOURCE = SourceDefinition.model_validate(
    {
        "source_id": "slowmist-test",
        "adapter_type": "slowmist_hacked",
        "source_class": "incident_forensic_signal",
        "authority_scope": ["incident_target"],
        "source_role": "forensic",
        "source_family": "slowmist-hacked",
        "access_mode": "html_event_database",
        "update_semantics": "mutable_incident_card",
        "discovery_method": {"index_url": "https://hacked.slowmist.io/", "max_items": 20},
        "retention_mode": "incident_signal",
    }
)
PAGE = """
<html><body><div class="case-content"><ul>
<li>
<span class="time">2026-09-24</span>
<h3><em>Hacked target: </em>Bitget</h3>
<p><em>Description of the event: </em>Unauthorized transfers moved funds to
0x1111111111111111111111111111111111111111.</p>
<p><span><em>Amount of loss: </em>$ 387,500,000</span>
<span><em>Attack method: </em>Internal System Compromise</span></p>
<p class="link-reference"><a href="https://www.theblock.co/news/bitget">
View Reference Sources</a></p>
</li>
</ul></div></body></html>
"""


@pytest.mark.asyncio
async def test_slowmist_hacked_emits_forensic_signal_with_upstream_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PAGE, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = SlowMistHackedAdapter(client)
        batch = await adapter.discover(SOURCE, SourceState())
        assert len(batch.items) == 1
        ref = batch.items[0]
        envelope = await adapter.fetch(
            SOURCE,
            ref,
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        signal = GenericNewsSignalExtractor().extract(SOURCE, envelope)
        assert signal.entity_hints["project"] == ["Bitget"]
        assert signal.anchors["address"] == ["0x1111111111111111111111111111111111111111"]
        assert signal.upstream_source == "www.theblock.co/news"
        assert "Internal System Compromise" in (signal.summary or "")
        assert envelope.json_payload["loss_amount_usd_text"] == "387,500,000"

        replay = await adapter.discover(SOURCE, SourceState(cursor=batch.next_cursor))
        assert replay.items == []
