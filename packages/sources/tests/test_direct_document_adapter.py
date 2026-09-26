from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from packages.sources.adapters.direct_document import DirectDocumentAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    QuerySpec,
    RetentionMode,
    SourceDefinition,
    SourceRole,
    SourceState,
)

SOURCE = SourceDefinition(
    source_id="normative-direct",
    adapter_type="direct_document",
    source_class="normative_knowledge",
    authority_scope=["regulation_text"],
    source_role=SourceRole.AUTHORITY,
    source_family="official",
    access_mode="direct_documents",
    update_semantics="authoritative_document_revision",
    discovery_method={
        "allowed_hosts": ["official.example.test"],
        "documents": [
            {
                "document_id": "rule-1",
                "title": "Rule One",
                "document_type": "regulation",
                "url": "https://official.example.test/rule-1",
            }
        ],
    },
    retention_mode=RetentionMode.DURABLE_MANAGED,
)


@pytest.mark.asyncio
async def test_direct_document_discovery_fetch_and_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "official.example.test"
        return httpx.Response(
            200,
            content=b"<html><main>official rule</main></html>",
            headers={"content-type": "text/html", "etag": '"v2"'},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = DirectDocumentAdapter(client)
        batch = await adapter.discover(SOURCE, SourceState())
        assert [item.external_object_id for item in batch.items] == ["rule-1"]
        envelope = await adapter.fetch(
            SOURCE,
            batch.items[0],
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.external_revision == '"v2"'
        assert envelope.request_metadata["title"] == "Rule One"
        queried = await adapter.query(
            SOURCE,
            QuerySpec(filters={"document_id": "rule-1"}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
        assert queried[0].external_object_id == "rule-1"


@pytest.mark.asyncio
async def test_direct_document_rejects_untrusted_configured_host() -> None:
    source = SOURCE.model_copy(
        update={
            "discovery_method": {
                **SOURCE.discovery_method,
                "documents": [
                    {
                        "document_id": "evil",
                        "url": "https://evil.example.test/rule",
                    }
                ],
            }
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    ) as client:
        with pytest.raises(ValueError, match="allowed_hosts"):
            await DirectDocumentAdapter(client).discover(source, SourceState())
