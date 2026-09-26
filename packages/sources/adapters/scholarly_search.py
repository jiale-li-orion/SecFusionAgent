from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from packages.sources.contracts import (
    AcquisitionTrigger,
    DiscoveredRef,
    DiscoveryBatch,
    IngestEnvelope,
    QuerySpec,
    SourceDefinition,
    SourceState,
)
from packages.sources.errors import SourceFetchFailed, SourceRateLimited, SourceSchemaChanged


class ScholarlySearchAdapter:
    """On-demand scholarly discovery for Crossref and OpenAlex."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        semantic_scholar_api_key: str | None = None,
    ) -> None:
        self._client = client
        self._semantic_scholar_api_key = semantic_scholar_api_key

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("scholarly search sources are on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("scholarly search source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        query = spec.filters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("scholarly search requires filters.query")
        limit = spec.filters.get("limit", 10)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0 or limit > 50:
            raise ValueError("scholarly search limit must be an integer in [1, 50]")
        provider = source.discovery_method.get("provider")
        if provider == "crossref":
            records = await self._crossref(source, query, limit)
        elif provider == "openalex":
            records = await self._openalex(source, query, limit)
        elif provider == "openreview":
            records = await self._openreview(source, query, limit)
        elif provider == "semantic_scholar":
            records = await self._semantic_scholar(source, query, limit)
        else:
            raise ValueError(f"unsupported scholarly provider={provider!r}")
        return [
            _to_envelope(
                source,
                record,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                query=query,
            )
            for record in records
        ]

    async def _crossref(
        self, source: SourceDefinition, query: str, limit: int
    ) -> list[dict[str, Any]]:
        base = str(source.discovery_method.get("base_url") or "https://api.crossref.org/works")
        payload = await self._get_json(
            base,
            params={
                "query.bibliographic": query,
                "rows": limit,
                "select": "DOI,title,author,published,URL,type,container-title,subject,link",
            },
        )
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("items"), list):
            raise SourceSchemaChanged("Crossref response has no message.items")
        return [item for item in message["items"] if isinstance(item, dict)]

    async def _openalex(
        self, source: SourceDefinition, query: str, limit: int
    ) -> list[dict[str, Any]]:
        base = str(source.discovery_method.get("base_url") or "https://api.openalex.org/works")
        payload = await self._get_json(base, params={"search": query, "per-page": limit})
        results = payload.get("results")
        if not isinstance(results, list):
            raise SourceSchemaChanged("OpenAlex response has no results")
        return [item for item in results if isinstance(item, dict)]

    async def _openreview(
        self, source: SourceDefinition, query: str, limit: int
    ) -> list[dict[str, Any]]:
        base = str(
            source.discovery_method.get("base_url") or "https://api2.openreview.net/notes/search"
        )
        payload = await self._get_json(
            base,
            params={
                "term": query,
                "content": "all",
                "source": "forum",
                "limit": limit,
            },
        )
        notes = payload.get("notes")
        if not isinstance(notes, list):
            raise SourceSchemaChanged("OpenReview response has no notes")
        return [item for item in notes if isinstance(item, dict)]

    async def _semantic_scholar(
        self, source: SourceDefinition, query: str, limit: int
    ) -> list[dict[str, Any]]:
        base = str(
            source.discovery_method.get("base_url")
            or "https://api.semanticscholar.org/graph/v1/paper/search"
        )
        headers = {}
        if self._semantic_scholar_api_key:
            headers["x-api-key"] = self._semantic_scholar_api_key
        payload = await self._get_json(
            base,
            params={
                "query": query,
                "limit": limit,
                "fields": (
                    "title,url,abstract,authors,year,publicationDate,externalIds,"
                    "openAccessPdf,venue,citationCount"
                ),
            },
            headers=headers,
        )
        records = payload.get("data")
        if not isinstance(records, list):
            raise SourceSchemaChanged("Semantic Scholar response has no data")
        return [item for item in records if isinstance(item, dict)]

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.get(
                url, params=params, headers=headers, follow_redirects=True
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"scholarly search request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("scholarly search rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"scholarly search returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("scholarly search returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("scholarly search response root must be an object")
        return payload


def _to_envelope(
    source: SourceDefinition,
    record: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
    query: str,
) -> IngestEnvelope:
    provider = source.discovery_method.get("provider")
    if provider == "crossref":
        identifier = record.get("DOI")
        if not isinstance(identifier, str) or not identifier:
            raise SourceSchemaChanged("Crossref record has no DOI")
        external_id = f"doi:{identifier.lower()}"
        canonical_url = (
            record.get("URL")
            if isinstance(record.get("URL"), str)
            else f"https://doi.org/{quote(identifier)}"
        )
        published = _crossref_date(record.get("published"))
    elif provider == "openalex":
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise SourceSchemaChanged("OpenAlex record has no id")
        external_id = identifier
        canonical_url = identifier if identifier.startswith("http") else None
        published = _openalex_date(record.get("publication_date"))
    elif provider == "openreview":
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise SourceSchemaChanged("OpenReview note has no id")
        external_id = f"openreview:{identifier}"
        canonical_url = f"https://openreview.net/forum?id={quote(identifier)}"
        cdate = record.get("cdate")
        published = (
            datetime.fromtimestamp(cdate / 1000, tz=UTC)
            if isinstance(cdate, (int, float)) and not isinstance(cdate, bool)
            else None
        )
    elif provider == "semantic_scholar":
        identifier = record.get("paperId")
        if not isinstance(identifier, str) or not identifier:
            raise SourceSchemaChanged("Semantic Scholar record has no paperId")
        external_id = f"s2:{identifier}"
        url = record.get("url")
        canonical_url = url if isinstance(url, str) else None
        published = _openalex_date(record.get("publicationDate"))
    else:
        raise SourceSchemaChanged(f"unsupported scholarly provider={provider!r}")
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=external_id,
        payload=record,
        canonical_url=canonical_url,
        published_at=published,
        updated_at=None,
        external_revision=None,
        request_metadata={"provider": str(provider), "query": query},
    )


def _crossref_date(value: Any) -> datetime | None:
    if not isinstance(value, dict):
        return None
    parts = value.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    date = parts[0]
    if not date or not isinstance(date[0], int):
        return None
    year = date[0]
    month = date[1] if len(date) > 1 and isinstance(date[1], int) else 1
    day = date[2] if len(date) > 2 and isinstance(date[2], int) else 1
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _openalex_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
