import json
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.cisa_kev import CISAKEVAdapter
from packages.sources.adapters.github_advisory import GitHubGlobalAdvisoryAdapter
from packages.sources.adapters.osv import OSVAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.registry.loader import load_source_definitions

FIXTURES = Path("tests/fixtures")
SOURCES = {item.source_id: item for item in load_source_definitions(Path("config/sources"))}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_id", "adapter_factory", "fixture", "expected_id"),
    [
        (
            "osv-vulnerabilities",
            lambda client: OSVAdapter(client),
            "osv_cve.json",
            "CVE-2026-42424",
        ),
        (
            "github-global-advisories",
            lambda client: GitHubGlobalAdvisoryAdapter(client),
            "github_advisory.json",
            "GHSA-aaaa-bbbb-cccc",
        ),
        (
            "cisa-kev",
            lambda client: CISAKEVAdapter(client),
            "cisa_kev.json",
            "CVE-2026-42424",
        ),
    ],
)
async def test_provider_query_adapters_return_ingest_envelopes(
    source_id: str,
    adapter_factory: object,
    fixture: str,
    expected_id: str,
) -> None:
    payload = json.loads((FIXTURES / fixture).read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = adapter_factory(client)  # type: ignore[operator]
        results = await adapter.query(
            SOURCES[source_id],
            QuerySpec(filters={"cve_id": "CVE-2026-42424"}),
            acquisition_run_id="query-run",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
    assert len(results) == 1
    assert results[0].external_object_id == expected_id
    assert results[0].content_hash
