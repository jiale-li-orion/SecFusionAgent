from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import JsonValue
from selectolax.parser import HTMLParser

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


class HTMLIncidentAdapter:
    """Discover breaking incident signals from public HTML list pages.

    The adapter owns transport and page-specific selectors. Security anchor
    extraction belongs to M2's incident signal extractor.
    """

    USER_AGENT = "SecFusionAgent/0.1 security-incident-source-adapter"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        index_url = _required_setting(source, "index_url")
        link_selector = _required_setting(source, "link_selector")
        max_items = _positive_int(source.discovery_method.get("max_items"), default=50)
        strip_pattern = _optional_setting(source, "title_strip_regex")
        title_strip = re.compile(strip_pattern) if strip_pattern else None
        allowed_hosts = _allowed_hosts(source, index_url)

        response = await self._get(index_url)
        tree = HTMLParser(response.text)
        links = tree.css(link_selector)
        if not links:
            raise SourceSchemaChanged("HTML incident selector returned no links")

        previous = state.cursor.get("item_revisions")
        previous_revisions = previous if isinstance(previous, dict) else {}
        next_revisions: dict[str, JsonValue] = {}
        items: list[DiscoveredRef] = []
        seen: set[str] = set()

        for link in links:
            href = link.attributes.get("href")
            if not href:
                continue
            canonical_url = urljoin(str(response.url), href)
            if canonical_url in seen or not _is_allowed_url(canonical_url, allowed_hosts):
                continue
            raw_title = " ".join(link.text(separator=" ", strip=True).split())
            title = title_strip.sub("", raw_title, count=1).strip() if title_strip else raw_title
            if not title:
                continue
            external_id = _url_identity(canonical_url)
            payload: dict[str, JsonValue] = {
                "title": title,
                "summary": None,
                "incident_type": "security-incident",
                "entity_hints": {},
                "anchors": {},
                "unresolved_questions": ["impact", "root cause", "primary confirmation"],
                "event_type": "reported",
            }
            revision = hashlib.sha256(title.encode()).hexdigest()
            next_revisions[external_id] = revision
            if previous_revisions.get(external_id) != revision:
                items.append(
                    DiscoveredRef(
                        external_object_id=external_id,
                        canonical_url=canonical_url,
                        external_revision=revision,
                        locator={"index_url": str(response.url), "raw_title": raw_title},
                        inline_payload=payload,
                    )
                )
            seen.add(canonical_url)
            if len(seen) >= max_items:
                break

        if not seen:
            raise SourceSchemaChanged("HTML incident page produced no allowed signals")
        return DiscoveryBatch(
            items=items,
            next_cursor={"item_revisions": next_revisions},
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if ref.inline_payload is None:
            raise SourceSchemaChanged("HTML incident discovered ref has no inline payload")
        return IngestEnvelope.for_json_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            payload=ref.inline_payload,
            canonical_url=ref.canonical_url,
            published_at=ref.published_at,
            updated_at=ref.updated_at,
            external_revision=ref.external_revision,
            request_metadata={
                "provider": source.source_family,
                "transport": "html_index",
                **ref.locator,
            },
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        del source, spec, acquisition_run_id, trigger
        raise ValueError("HTML incident source supports scheduled discovery only")

    async def _get(self, url: str) -> httpx.Response:
        try:
            response = await self._client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                },
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"HTML incident request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("HTML incident source rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"HTML incident source returned HTTP {response.status_code}")
        return response


def _required_setting(source: SourceDefinition, key: str) -> str:
    value = source.discovery_method.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"HTML incident source requires discovery_method.{key}")
    return value


def _optional_setting(source: SourceDefinition, key: str) -> str | None:
    value = source.discovery_method.get(key)
    return value if isinstance(value, str) and value else None


def _positive_int(value: JsonValue | None, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return default


def _allowed_hosts(source: SourceDefinition, index_url: str) -> set[str]:
    configured = source.discovery_method.get("allowed_hosts")
    hosts = (
        {item.lower() for item in configured if isinstance(item, str) and item}
        if isinstance(configured, list)
        else set()
    )
    host = urlparse(index_url).hostname
    if host:
        hosts.add(host.lower())
    return hosts


def _is_allowed_url(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.hostname.lower() in allowed_hosts
    )


def _url_identity(url: str) -> str:
    return f"url:{hashlib.sha256(url.encode()).hexdigest()}"
