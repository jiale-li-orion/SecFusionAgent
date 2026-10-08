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


@pytest.mark.asyncio
async def test_cvelist_hot_poll_prioritizes_new_deltas_without_losing_backlog() -> None:
    def entry(minute: int) -> dict[str, object]:
        cve_id = f"CVE-2026-{10000 + minute}"
        return {
            "fetchTime": f"2026-10-08T00:{minute:02d}:00Z",
            "new": [{
                "cveId": cve_id,
                "githubLink": f"https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2026/10xxx/{cve_id}.json",
                "dateUpdated": f"2026-10-08T00:{minute:02d}:00Z",
            }],
        }

    delta = [entry(3), entry(2), entry(1)]  # real upstream order: newest first

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=delta, request=request)

    source = SOURCE.model_copy(update={
        "discovery_method": {**SOURCE.discovery_method, "max_items": 1},
    })
    state = SourceState(cursor={"last_fetch_time": "2026-10-08T00:00:00+00:00"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = CVEListV5Adapter(client)
        first = await adapter.discover(source, state)
        assert [ref.external_object_id for ref in first.items] == ["CVE-2026-10003"]
        assert first.next_cursor["backfill_pending"] is True
        assert first.next_cursor["last_fetch_time"] == state.cursor["last_fetch_time"]

        second = await adapter.discover(
            source, SourceState(cursor=first.next_cursor),
        )
        assert [ref.external_object_id for ref in second.items] == ["CVE-2026-10002"]

        delta.insert(0, entry(4))
        third = await adapter.discover(
            source, SourceState(cursor=second.next_cursor),
        )
        assert [ref.external_object_id for ref in third.items] == ["CVE-2026-10004"]

        fourth = await adapter.discover(
            source, SourceState(cursor=third.next_cursor),
        )
        assert [ref.external_object_id for ref in fourth.items] == ["CVE-2026-10001"]
        assert fourth.next_cursor == {
            "last_fetch_time": "2026-10-08T00:04:00+00:00",
            "backfill_pending": False,
        }


@pytest.mark.asyncio
async def test_cvelist_bootstrap_uses_newest_entry_regardless_of_upstream_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=list(reversed(DELTA)), request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await CVEListV5Adapter(client).discover(SOURCE, SourceState())
    assert len(batch.items) == 1
    assert batch.items[0].external_revision == "2026-09-26T01:14:00+00:00"
    assert batch.next_cursor["last_fetch_time"] == "2026-09-26T01:15:00+00:00"


@pytest.mark.asyncio
async def test_cvelist_retries_one_transient_proxy_disconnect() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary proxy disconnect", request=request)
        return httpx.Response(200, json=DELTA, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await CVEListV5Adapter(client).discover(SOURCE, SourceState())
    assert attempts == 2
    assert len(batch.items) == 1
