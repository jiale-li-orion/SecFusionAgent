from __future__ import annotations

import httpx
import pytest

from packages.sources.adapters.oscs import OSCSAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceDefinition

SOURCE = SourceDefinition.model_validate(
    {
        "source_id": "oscs-test",
        "adapter_type": "oscs",
        "source_class": "independent_security_research",
        "authority_scope": ["community_project_security"],
        "source_role": "reference",
        "source_family": "oscs",
        "access_mode": "public_json_api",
        "update_semantics": "on_demand_observation",
        "discovery_method": {"base_url": "https://www.oscs1024.com"},
        "retention_mode": "time_bounded",
    }
)


@pytest.mark.asyncio
async def test_oscs_project_search_maps_public_api_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oscs_api/v2/project/search"
        assert request.url.params["keyword"] == "vllm"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "project_name": "vllm-project/vllm",
                        "project_id": "0",
                        "desc": "inference engine",
                    }
                ],
                "success": True,
                "code": 200,
                "info": "success",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OSCSAdapter(client).query(
            SOURCE,
            QuerySpec(filters={"keyword": "vllm"}),
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
    assert result[0].external_object_id == "repo:vllm-project/vllm"
    assert result[0].request_metadata["keyword"] == "vllm"
