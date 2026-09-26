from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from packages.sources.adapters.cvelist_v5 import CVEListV5Adapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceDefinition, SourceState

SOURCE = SourceDefinition.model_validate(
    json.loads(open("config/sources/cve-program-cvelist-v5.json").read())
)

DELTA = [
    {
        "fetchTime": "2026-09-26T01:00:00Z",
        "numberOfChanges": 1,
        "new": [
            {
                "cveId": "CVE-2026-12345",
                "cveOrgLink": "https://www.cve.org/CVERecord?id=CVE-2026-12345",
                "githubLink": "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/12xxx/CVE-2026-12345.json",
                "dateUpdated": "2026-09-26T00:58:00Z",
            }
        ],
        "updated": [],
        "error": [],
    },
    {
        "fetchTime": "2026-09-26T01:15:00Z",
        "numberOfChanges": 1,
        "new": [],
        "updated": [
            {
                "cveId": "CVE-2026-12345",
                "cveOrgLink": "https://www.cve.org/CVERecord?id=CVE-2026-12345",
                "githubLink": "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/12xxx/CVE-2026-12345.json",
                "dateUpdated": "2026-09-26T01:14:00Z",
            }
        ],
        "error": [],
    },
]
RECORD = {
    "dataType": "CVE_RECORD",
    "dataVersion": "5.2",
    "cveMetadata": {
        "cveId": "CVE-2026-12345",
        "state": "PUBLISHED",
        "assignerShortName": "example",
        "datePublished": "2026-09-25T10:00:00Z",
        "dateUpdated": "2026-09-26T01:14:00Z",
    },
    "containers": {
        "cna": {
            "title": "Example issue",
            "descriptions": [{"lang": "en", "value": "Example vulnerability"}],
            "affected": [{"vendor": "Example", "product": "Server"}],
            "references": [{"url": "https://example.invalid/advisory"}],
        }
    },
}


@pytest.mark.asyncio
async def test_cvelist_delta_log_deduplicates_to_latest_revision() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("deltaLog.json"):
            return httpx.Response(200, json=DELTA, request=request)
        return httpx.Response(200, json=RECORD, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = CVEListV5Adapter(client)
        batch = await adapter.discover(SOURCE, SourceState())
        assert len(batch.items) == 1
        assert batch.items[0].external_object_id == "CVE-2026-12345"
        assert batch.items[0].external_revision == "2026-09-26T01:14:00+00:00"
        assert batch.next_cursor["last_fetch_time"] == "2026-09-26T01:15:00+00:00"
        envelope = await adapter.fetch(
            SOURCE,
            batch.items[0],
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        assert envelope.external_object_id == "CVE-2026-12345"
        assert envelope.updated_at == datetime(2026, 9, 26, 1, 14, tzinfo=UTC)


@pytest.mark.asyncio
async def test_cvelist_query_constructs_raw_record_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/cves/2026/12xxx/CVE-2026-12345.json")
        return httpx.Response(200, json=RECORD, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CVEListV5Adapter(client).query(
            SOURCE,
            QuerySpec(filters={"cve_id": "CVE-2026-12345"}),
            acquisition_run_id="00000000-0000-0000-0000-000000000002",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
    assert result[0].external_object_id == "CVE-2026-12345"
