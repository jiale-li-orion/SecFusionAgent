from __future__ import annotations

import httpx
import pytest

from packages.sources.adapters.cnnvd import CNNVDAdapter
from packages.sources.contracts import AcquisitionTrigger, QuerySpec, SourceDefinition

SOURCE = SourceDefinition.model_validate(
    {
        "source_id": "cnnvd-test",
        "adapter_type": "cnnvd",
        "source_class": "canonical_bug_reference",
        "authority_scope": ["cnnvd_identity"],
        "source_role": "authority",
        "source_family": "cnnvd",
        "access_mode": "signed_public_frontend_api",
        "update_semantics": "on_demand_mutable_record",
        "discovery_method": {
            "origin": "https://www.cnnvd.org.cn",
            "base_path": "/cnnvdweb",
            "app_id": "public-app-id",
        },
        "retention_mode": "time_bounded",
    }
)


@pytest.mark.asyncio
async def test_cnnvd_query_uses_tourist_sign_then_searches() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["x-appid"] == "public-app-id"
        if request.url.path.endswith("/tourist/sign"):
            payload = request.content.decode()
            assert "POST/cnnvdweb/homePage/searchVul" in payload
            return httpx.Response(
                200,
                json={"code": 200, "success": True, "data": "signed-value"},
                request=request,
            )
        assert request.headers["x-sign"] == "signed-value"
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "records": [
                        {
                            "id": "internal-1",
                            "cnnvdId": "CNNVD-202604-1234",
                            "cveId": "CVE-2024-3094",
                            "vulName": "Example issue",
                            "publishDate": "2026-04-01",
                            "updateTime": "2026-04-02",
                        }
                    ]
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CNNVDAdapter(client).query(
            SOURCE,
            QuerySpec(filters={"cve_id": "CVE-2024-3094"}),
            acquisition_run_id="00000000-0000-0000-0000-000000000001",
            trigger=AcquisitionTrigger.ON_DEMAND,
        )
    assert calls == ["/cnnvdweb/tourist/sign", "/cnnvdweb/homePage/searchVul"]
    assert result[0].external_object_id == "CNNVD-202604-1234"
    assert result[0].json_payload["cveId"] == "CVE-2024-3094"
