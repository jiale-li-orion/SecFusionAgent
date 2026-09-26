from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.enrichment.assets.service import AssetObservationService
from packages.intelligence.ingestion.evidence import EvidenceIngress
from packages.intelligence.storage.artifacts import MemoryArtifactStore
from packages.intelligence.storage.evidence_models import ObservationModel
from packages.monitoring.acquisition.service import AcquisitionService
from packages.monitoring.storage.models import AcquisitionRunModel
from packages.shared.db import Base
from packages.sources.adapters.shodan import ShodanAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec
from packages.sources.errors import SourceAuthFailed
from packages.sources.registry.loader import load_source_definitions
from packages.sources.registry.service import sync_source_definitions

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)
SOURCE = next(
    item
    for item in load_source_definitions(Path("config/sources"))
    if item.source_id == "shodan-assets"
)

PAYLOAD = {
    "total": 1,
    "matches": [
        {
            "ip_str": "203.0.113.10",
            "port": 8000,
            "transport": "tcp",
            "product": "vLLM",
            "version": "0.10.1",
            "org": "Example Cloud",
            "isp": "Example ISP",
            "asn": "AS64500",
            "hostnames": ["llm.example.test"],
            "domains": ["example.test"],
            "cpe": ["cpe:/a:vllm-project:vllm:0.10.1"],
            "location": {"country_code": "SG"},
            "timestamp": "2026-09-26T07:59:00Z",
        }
    ],
}


@pytest.mark.asyncio
async def test_shodan_query_is_transient_until_promoted() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/shodan/host/search"
        assert request.url.params["query"] == 'product:"vLLM"'
        assert request.url.params["key"] == "secret"
        return httpx.Response(200, json=PAYLOAD, request=request)

    try:
        async with factory() as session, session.begin():
            await sync_source_definitions(session, [SOURCE])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = ShodanAdapter(client, api_key="secret", now=lambda: NOW)
            service = AssetObservationService(
                AcquisitionService(factory, now=lambda: NOW),
                EvidenceIngress(MemoryArtifactStore(), now=lambda: NOW),
            )
            results = await service.query(
                SOURCE,
                adapter,
                QuerySpec(filters={"query": 'product:"vLLM"'}),
                parent_run_id=None,
            )
            assert len(results) == 1
            observation = results[0].observation
            assert observation.ip == "203.0.113.10"
            assert observation.port == 8000
            assert observation.product == "vLLM"
            assert observation.version == "0.10.1"
            assert observation.query == 'product:"vLLM"'
            assert observation.observed_at == NOW

            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 0
                run = await session.get(AcquisitionRunModel, observation.acquisition_run_id)
                assert run is not None
                assert run.status == "success"
                assert run.query_spec == {"filters": {"query": 'product:"vLLM"'}}

            async with factory() as session, session.begin():
                promoted = await service.promote(session, SOURCE, results[0])
                assert promoted.replay is False
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(ObservationModel)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_shodan_requires_explicit_api_key() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    ) as client:
        adapter = ShodanAdapter(client, api_key=None, now=lambda: NOW)
        with pytest.raises(SourceAuthFailed, match="required"):
            await adapter.query(
                SOURCE,
                QuerySpec(filters={"query": "vllm"}),
                acquisition_run_id="00000000-0000-0000-0000-000000000001",
                trigger=AcquisitionTrigger.INVESTIGATION,
            )


def test_asset_observation_accepts_provider_neutral_normalized_payload() -> None:
    from packages.enrichment.assets.service import _map_asset_observation
    from packages.sources.contracts import IngestEnvelope

    envelope = IngestEnvelope.for_json_payload(
        acquisition_run_id="00000000-0000-0000-0000-000000000099",
        trigger=AcquisitionTrigger.INVESTIGATION,
        source_id="censys-assets",
        external_object_id="198.51.100.20:443/tcp",
        payload={
            "ip": "198.51.100.20",
            "port": 443,
            "transport": "tcp",
            "product": "vLLM",
            "version": "0.10.2",
            "org": "Example ASN",
            "asn": "64501",
            "hostnames": ["api.example.test"],
            "domains": ["example.test"],
            "location": {"country": "SG"},
        },
        canonical_url=None,
        published_at=None,
        updated_at=NOW,
        external_revision=NOW.isoformat(),
        request_metadata={"provider": "censys", "query": "vllm"},
        observed_at=NOW,
    )
    observation = _map_asset_observation(envelope)
    assert observation.provider == "censys"
    assert observation.ip == "198.51.100.20"
    assert observation.port == 443
    assert observation.product == "vLLM"
    assert observation.version == "0.10.2"
    assert observation.organization == "Example ASN"
