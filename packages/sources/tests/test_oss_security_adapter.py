from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from packages.intelligence.documents.parsers import HTMLDocumentParser
from packages.sources.adapters.oss_security import OssSecurityAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceDefinition, SourceState

SOURCE = SourceDefinition.model_validate(
    {
        "source_id": "oss-security-test",
        "adapter_type": "oss_security",
        "source_class": "independent_security_research",
        "authority_scope": ["oss_disclosure"],
        "source_role": "forensic",
        "source_family": "openwall-oss-security",
        "access_mode": "mailing_list_archive",
        "update_semantics": "append_only_messages",
        "discovery_method": {
            "root_url": "https://www.openwall.com/lists/oss-security/",
            "lookback_months": 1,
            "max_items": 20,
        },
        "retention_mode": "durable_managed",
    }
)
MONTH_HTML = """
<html><body>
<a href="25/1">CVE-2026-11111: example issue</a>
<a href="25/2">Re: CVE-2026-11111: follow-up</a>
<a href="../08/">[prev month]</a>
</body></html>
"""
MESSAGE_HTML = """
<html><body><div>navigation noise</div><pre>
Message-ID: &lt;example@example.org&gt;
Date: Fri, 25 Sep 2026 20:17:00 +0000
Subject: CVE-2026-11111: example issue

Affected versions: 1.0
Description: This is a sufficiently long security disclosure body that explains the vulnerability,
impact, affected versions, and remediation. Upgrade to version 1.1 or later.
References: https://example.org/advisory
</pre><div>footer noise</div></body></html>
"""


@pytest.mark.asyncio
async def test_oss_security_discovers_current_month_and_preserves_message_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/2026/09/"):
            return httpx.Response(200, text=MONTH_HTML, request=request)
        if request.url.path.endswith("/2026/09/25/1"):
            return httpx.Response(
                200,
                text=MESSAGE_HTML,
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OssSecurityAdapter(
            client,
            now=lambda: datetime(2026, 9, 26, tzinfo=UTC),
        )
        batch = await adapter.discover(SOURCE, SourceState())
        assert [item.external_object_id for item in batch.items] == [
            "2026/09/25/1",
            "2026/09/25/2",
        ]
        replay = await adapter.discover(SOURCE, SourceState(cursor=batch.next_cursor))
        assert replay.items == []
        envelope = await adapter.fetch(
            SOURCE,
            batch.items[0],
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.media_type == "text/html"
        assert b"Message-ID" in envelope.content_bytes()

        sections = HTMLDocumentParser().parse(envelope.content_bytes())
        assert len(sections) == 1
        assert sections[0].source_locator["kind"] == "html_preformatted_document"
        assert "CVE-2026-11111" in sections[0].text
        assert "navigation noise" not in sections[0].text
