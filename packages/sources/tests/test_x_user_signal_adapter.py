from __future__ import annotations

import httpx
import pytest

from packages.intelligence.incident.contracts import GenericNewsSignalExtractor
from packages.sources.adapters.x_user_signal import XUserSignalAdapter
from packages.sources.contracts import AcquisitionTrigger, SourceDefinition, SourceState
from packages.sources.errors import SourceAuthFailed

SOURCE = SourceDefinition.model_validate(
    {
        "source_id": "lookonchain-test",
        "adapter_type": "x_user_signal",
        "source_class": "incident_telemetry",
        "authority_scope": ["onchain_observation"],
        "source_role": "telemetry",
        "source_family": "lookonchain",
        "access_mode": "x_api_v2",
        "update_semantics": "append_only_posts",
        "discovery_method": {"username": "lookonchain", "max_results": 10},
        "retention_mode": "incident_signal",
    }
)


@pytest.mark.asyncio
async def test_x_user_signal_discovers_posts_and_preserves_source_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        if request.url.path.endswith("/users/by/username/lookonchain"):
            return httpx.Response(
                200,
                json={"data": {"id": "42", "username": "lookonchain"}},
                request=request,
            )
        if request.url.path.endswith("/users/42/tweets"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "2100000000000000000",
                            "text": "Funds moved to 0x1111111111111111111111111111111111111111",
                            "created_at": "2026-09-25T12:00:00Z",
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = XUserSignalAdapter(client, bearer_token="secret")
        batch = await adapter.discover(SOURCE, SourceState())
        assert batch.next_cursor["since_id"] == "2100000000000000000"
        envelope = await adapter.fetch(
            SOURCE,
            batch.items[0],
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.SCHEDULED,
        )
        signal = GenericNewsSignalExtractor().extract(SOURCE, envelope)
        assert signal.upstream_source == "x.com/lookonchain"
        assert signal.anchors["address"] == ["0x1111111111111111111111111111111111111111"]


@pytest.mark.asyncio
async def test_x_user_signal_requires_bearer_token() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceAuthFailed, match="required"):
            await XUserSignalAdapter(client, bearer_token=None).discover(SOURCE, SourceState())
