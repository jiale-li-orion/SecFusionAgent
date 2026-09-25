from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from pydantic import JsonValue

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

ATOM = {"atom": "http://www.w3.org/2005/Atom"}
_VERSION_RE = re.compile(r"^(?P<base>.+?)(?P<version>v\d+)?$")


class ArxivAdapter:
    DEFAULT_API_URL = "https://export.arxiv.org/api/query"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        search_query = source.discovery_method.get("search_query")
        if not isinstance(search_query, str) or not search_query:
            raise ValueError("arXiv source requires discovery_method.search_query")
        api_url = str(source.discovery_method.get("base_url") or self.DEFAULT_API_URL)
        page_size = _int_setting(source.discovery_method.get("page_size"), default=50)
        initial_limit = _int_setting(
            source.discovery_method.get("initial_limit"),
            default=page_size,
        )
        cursor_value = state.cursor.get("latest_updated")
        cursor = _parse_datetime(cursor_value) if isinstance(cursor_value, str) else None

        collected: list[DiscoveredRef] = []
        start = 0
        newest: datetime | None = cursor
        reached_cursor = False
        while True:
            payload = await self._get_text(
                api_url,
                params={
                    "search_query": search_query,
                    "start": start,
                    "max_results": page_size,
                    "sortBy": "lastUpdatedDate",
                    "sortOrder": "descending",
                },
            )
            entries = _parse_entries(payload)
            if not entries:
                break
            for ref in entries:
                if ref.updated_at is not None:
                    newest = max(newest, ref.updated_at) if newest is not None else ref.updated_at
                if cursor is not None and ref.updated_at is not None and ref.updated_at <= cursor:
                    reached_cursor = True
                    break
                collected.append(ref)
                if cursor is None and len(collected) >= initial_limit:
                    reached_cursor = True
                    break
            if reached_cursor or len(entries) < page_size:
                break
            start += len(entries)

        next_cursor = dict(state.cursor)
        if newest is not None:
            next_cursor["latest_updated"] = newest.isoformat()
        return DiscoveryBatch(items=collected, next_cursor=next_cursor)

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        pdf_url = ref.locator.get("pdf_url")
        if not isinstance(pdf_url, str) or not pdf_url:
            raise SourceSchemaChanged("arXiv discovered record has no PDF URL")
        try:
            response = await self._client.get(pdf_url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"arXiv PDF request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("arXiv rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"arXiv PDF returned HTTP {response.status_code}")
        metadata = {key: value for key, value in ref.locator.items() if key != "pdf_url"}
        metadata["provider"] = "arxiv"
        return IngestEnvelope.for_binary_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            body=response.content,
            media_type="application/pdf",
            canonical_url=ref.canonical_url,
            published_at=ref.published_at,
            updated_at=ref.updated_at,
            external_revision=ref.external_revision,
            request_metadata=metadata,
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        arxiv_id = spec.filters.get("arxiv_id")
        if not isinstance(arxiv_id, str) or not arxiv_id:
            raise ValueError("arXiv query requires filters.arxiv_id")
        ref = DiscoveredRef(
            external_object_id=_base_id(arxiv_id),
            canonical_url=f"https://arxiv.org/abs/{arxiv_id}",
            external_revision=arxiv_id,
            locator={"pdf_url": f"https://arxiv.org/pdf/{arxiv_id}"},
        )
        return [
            await self.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
        ]

    async def _get_text(self, url: str, *, params: dict[str, str | int]) -> str:
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"arXiv API request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("arXiv rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"arXiv API returned HTTP {response.status_code}")
        return response.text


def _parse_entries(payload: str) -> list[DiscoveredRef]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SourceSchemaChanged("arXiv API returned invalid Atom XML") from exc
    entries: list[DiscoveredRef] = []
    for entry in root.findall("atom:entry", ATOM):
        entry_url = _required_text(entry, "atom:id")
        versioned_id = entry_url.rstrip("/").split("/")[-1]
        external_id = _base_id(versioned_id)
        published = _parse_datetime(_required_text(entry, "atom:published"))
        updated = _parse_datetime(_required_text(entry, "atom:updated"))
        title = _normalize_ws(_required_text(entry, "atom:title"))
        summary = _normalize_ws(_required_text(entry, "atom:summary"))
        authors: list[JsonValue] = [
            _normalize_ws(name.text or "")
            for name in entry.findall("atom:author/atom:name", ATOM)
            if (name.text or "").strip()
        ]
        category_values = sorted(
            {
                term
                for category in entry.findall("atom:category", ATOM)
                if isinstance((term := category.attrib.get("term")), str) and term
            }
        )
        categories: list[JsonValue] = [value for value in category_values]
        pdf_url = None
        for link in entry.findall("atom:link", ATOM):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{versioned_id}"
        entries.append(
            DiscoveredRef(
                external_object_id=external_id,
                canonical_url=f"https://arxiv.org/abs/{versioned_id}",
                published_at=published,
                updated_at=updated,
                external_revision=versioned_id,
                locator={
                    "pdf_url": pdf_url,
                    "title": title,
                    "summary": summary,
                    "authors": authors,
                    "categories": categories,
                    "versioned_id": versioned_id,
                },
            )
        )
    return entries


def _required_text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ATOM)
    if node is None or not (node.text or "").strip():
        raise SourceSchemaChanged(f"arXiv entry missing {path}")
    return (node.text or "").strip()


def _base_id(versioned_id: str) -> str:
    match = _VERSION_RE.match(versioned_id)
    if match is None:
        return versioned_id
    return match.group("base")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def _int_setting(value: JsonValue | None, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return default
