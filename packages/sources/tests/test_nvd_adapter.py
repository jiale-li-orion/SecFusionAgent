import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.nvd import NVDAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceState
from packages.sources.registry.loader import load_source_definitions

FIXTURE = Path("tests/fixtures/nvd_cve_page.json")
PAYLOAD = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_discover_and_fetch_reuse_inline_nvd_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=PAYLOAD)

    transport = httpx.MockTransport(handler)
    source = load_source_definitions(Path("config/sources"))[0]
    now = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = NVDAdapter(client, now=lambda: now)
        batch = await adapter.discover(source, SourceState())
        assert len(batch.items) == 1
        ref = batch.items[0]
        assert ref.external_object_id == "CVE-2026-42424"
        envelope = await adapter.fetch(
            source,
            ref,
            acquisition_run_id="run-1",
            trigger=AcquisitionTrigger.SCHEDULED,
        )

    assert len(requests) == 1
    assert envelope.source_id == source.source_id
    assert envelope.external_object_id == "CVE-2026-42424"
    assert envelope.external_revision == "2026-09-25T01:45:00+00:00"
    assert envelope.idempotency_key
    assert batch.next_cursor == {"last_modified": now.isoformat()}


def test_source_registry_loads_nvd_contract() -> None:
    definitions = load_source_definitions(Path("config/sources"))
    assert [item.source_id for item in definitions] == ["nvd-cves-2"]
    assert definitions[0].retention_mode.value == "hot_window"


@pytest.mark.asyncio
async def test_discover_reads_all_nvd_pages_before_returning_cursor() -> None:
    pages = [
        {
            "totalResults": 2,
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2026-40001",
                        "published": "2026-09-25T00:00:00.000",
                        "lastModified": "2026-09-25T01:00:00.000",
                    }
                }
            ],
        },
        {
            "totalResults": 2,
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2026-40002",
                        "published": "2026-09-25T00:30:00.000",
                        "lastModified": "2026-09-25T01:30:00.000",
                    }
                }
            ],
        },
    ]
    seen_start_indices: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start_index = request.url.params.get("startIndex", "0")
        seen_start_indices.append(start_index)
        return httpx.Response(200, json=pages[int(start_index)])

    source = load_source_definitions(Path("config/sources"))[0]
    source = source.model_copy(
        update={"discovery_method": {**source.discovery_method, "results_per_page": 1}}
    )
    now = datetime(2026, 9, 25, 2, 0, tzinfo=UTC)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await NVDAdapter(client, now=lambda: now).discover(source, SourceState())

    assert [item.external_object_id for item in batch.items] == [
        "CVE-2026-40001",
        "CVE-2026-40002",
    ]
    assert seen_start_indices == ["0", "1"]
    assert batch.next_cursor == {"last_modified": now.isoformat()}
