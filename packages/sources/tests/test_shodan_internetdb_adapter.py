from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from packages.sources.adapters.shodan_internetdb import ShodanInternetDBAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.registry.loader import load_source_definitions

NOW = datetime(2026, 9, 26, 16, 24, 22, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "shodan-internetdb-assets"
)


@pytest.mark.asyncio
async def test_internetdb_returns_one_time_bounded_observation_per_port() -> None:
    payload = {
        "ip": "18.165.98.58",
        "ports": [80, 443],
        "hostnames": ["server-18-165-98-58.iad55.r.cloudfront.net"],
        "cpes": ["cpe:/a:amazon:amazon_cloudfront"],
        "tags": ["cloud", "cdn"],
        "vulns": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/18.165.98.58"
        return httpx.Response(200, json=payload, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ShodanInternetDBAdapter(client, now=lambda: NOW)
        results = await adapter.query(
            SOURCE,
            QuerySpec(
                filters={
                    "ip": "18.165.98.58",
                    "discovery_context": {
                        "hostname": "datasets-server.huggingface.co",
                        "shared_edge": True,
                    },
                    "relation_context": {
                        "type": "public-service-asset-observation",
                        "strength": "context-only",
                    },
                }
            ),
            acquisition_run_id="00000000-0000-0000-0000-000000000900",
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert [item.external_object_id for item in results] == [
        "18.165.98.58:80/tcp",
        "18.165.98.58:443/tcp",
    ]
    assert results[0].request_metadata["provider"] == "shodan-internetdb"
    assert results[0].request_metadata["passive_observation"] is True
    assert results[0].request_metadata["relation_context"] == {
        "type": "public-service-asset-observation",
        "strength": "context-only",
    }
    assert results[0].json_payload["product"] is None
    assert results[0].json_payload["cpe"] == ["cpe:/a:amazon:amazon_cloudfront"]


@pytest.mark.asyncio
async def test_internetdb_404_is_no_observation() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404, request=request))
    ) as client:
        adapter = ShodanInternetDBAdapter(client, now=lambda: NOW)
        results = await adapter.query(
            SOURCE,
            QuerySpec(filters={"ip": "203.0.113.10"}),
            acquisition_run_id="00000000-0000-0000-0000-000000000901",
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert results == []


@pytest.mark.asyncio
async def test_internetdb_preserves_explicit_vulnerability_associations() -> None:
    payload = {
        "ip": "44.238.29.244",
        "ports": [80],
        "hostnames": ["ec2-44-238-29-244.us-west-2.compute.amazonaws.com"],
        "cpes": ["cpe:/a:microsoft:internet_information_services:8.5"],
        "tags": [],
        "vulns": ["CVE-2014-4078"],
    }

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload, request=request)
        )
    ) as client:
        results = await ShodanInternetDBAdapter(client, now=lambda: NOW).query(
            SOURCE,
            QuerySpec(filters={"ip": "44.238.29.244"}),
            acquisition_run_id="00000000-0000-0000-0000-000000000902",
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert len(results) == 1
    assert results[0].json_payload["vulns"] == ["CVE-2014-4078"]
