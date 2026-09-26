from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from packages.sources.adapters.scholarly_search import ScholarlySearchAdapter
from packages.sources.contracts import (
    AcquisitionTrigger,
    QuerySpec,
    RetentionMode,
    SourceDefinition,
    SourceRole,
)


def _source(provider: str) -> SourceDefinition:
    return SourceDefinition(
        source_id=f"{provider}-search",
        adapter_type="scholarly_search",
        source_class="academic_search",
        authority_scope=["candidate_discovery"],
        source_role=SourceRole.REFERENCE,
        source_family=provider,
        access_mode="https_api",
        update_semantics="on_demand_search",
        discovery_method={"provider": provider, "base_url": f"https://api.example.test/{provider}"},
        retention_mode=RetentionMode.TIME_BOUNDED,
        schedule_policy={"enabled": False},
    )


@pytest.mark.asyncio
async def test_crossref_query_preserves_doi_and_query_provenance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query.bibliographic"] == "agent security"
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/example",
                            "title": ["Agent Security"],
                            "URL": "https://doi.org/10.1000/example",
                            "published": {"date-parts": [[2026, 8, 1]]},
                        }
                    ]
                }
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ScholarlySearchAdapter(client).query(
            _source("crossref"),
            QuerySpec(filters={"query": "agent security", "limit": 3}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert result[0].external_object_id == "doi:10.1000/example"
    assert result[0].request_metadata["query"] == "agent security"


@pytest.mark.asyncio
async def test_openalex_query_preserves_work_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "prompt injection"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W123",
                        "display_name": "Prompt Injection",
                        "publication_date": "2026-05-03",
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ScholarlySearchAdapter(client).query(
            _source("openalex"),
            QuerySpec(filters={"query": "prompt injection", "limit": 2}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert result[0].external_object_id == "https://openalex.org/W123"
    assert result[0].canonical_url == "https://openalex.org/W123"


@pytest.mark.asyncio
async def test_openreview_query_filters_to_forum_notes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["term"] == "agent security"
        assert request.url.params["source"] == "forum"
        return httpx.Response(
            200,
            json={
                "notes": [
                    {
                        "id": "paper123",
                        "cdate": 1780000000000,
                        "content": {
                            "title": {"value": "Architecture Matters for Multi-Agent Security"}
                        },
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ScholarlySearchAdapter(client).query(
            _source("openreview"),
            QuerySpec(filters={"query": "agent security", "limit": 3}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert result[0].external_object_id == "openreview:paper123"
    assert result[0].canonical_url == "https://openreview.net/forum?id=paper123"


@pytest.mark.asyncio
async def test_semantic_scholar_query_sends_optional_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "paperId": "abc123",
                        "title": "Agent Security",
                        "url": "https://www.semanticscholar.org/paper/abc123",
                        "publicationDate": "2026-07-01",
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ScholarlySearchAdapter(client, semantic_scholar_api_key="secret").query(
            _source("semantic_scholar"),
            QuerySpec(filters={"query": "agent security", "limit": 3}),
            acquisition_run_id=str(uuid4()),
            trigger=AcquisitionTrigger.INVESTIGATION,
        )
    assert result[0].external_object_id == "s2:abc123"
