from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import JsonValue
from selectolax.parser import HTMLParser, Node

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


class HTMLIndexAdapter:
    """Discover bounded article windows from public HTML index pages.

    Site-specific CSS selectors live in SourceDefinition. Article-body parsing
    belongs to the managed-document parser, not to this provider adapter.
    """

    USER_AGENT = "SecFusionAgent/0.1 security-intelligence-source-adapter"
    DEFAULT_REVALIDATE_SECONDS = 24 * 60 * 60

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._now = now or (lambda: datetime.now(UTC))

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        index_url = _required_setting(source, "index_url")
        item_selector = _optional_setting(source, "item_selector")
        link_selector = _optional_setting(source, "link_selector") or "a[href]"
        title_selector = _optional_setting(source, "title_selector")
        max_items = _positive_int(source.discovery_method.get("max_items"), default=50)
        allowed_hosts = _allowed_hosts(source, index_url)

        response = await self._get(index_url)
        tree = HTMLParser(response.text)
        containers: list[Node]
        if item_selector:
            containers = tree.css(item_selector)
        else:
            root = tree.body
            containers = [root] if root is not None else []
        if not containers:
            raise SourceSchemaChanged("HTML index selector returned no containers")

        refs: list[DiscoveredRef] = []
        seen_urls: set[str] = set()
        for container in containers:
            link_nodes = container.css(link_selector) if not item_selector else []
            link = container.css_first(link_selector) if item_selector else None
            candidates = [link] if link is not None else link_nodes
            for node in candidates:
                if node is None:
                    continue
                href = node.attributes.get("href")
                if not href:
                    continue
                canonical_url = urljoin(str(response.url), href)
                if not _is_allowed_url(canonical_url, allowed_hosts):
                    continue
                if canonical_url in seen_urls:
                    continue
                title = _title_for(container, node, title_selector)
                refs.append(
                    DiscoveredRef(
                        external_object_id=_url_identity(canonical_url),
                        canonical_url=canonical_url,
                        locator={
                            "title": title,
                            "index_url": str(response.url),
                        },
                    )
                )
                seen_urls.add(canonical_url)
                if len(refs) >= max_items:
                    break
            if len(refs) >= max_items:
                break

        if not refs:
            raise SourceSchemaChanged("HTML index produced no allowed article links")
        index_hash = _index_hash(refs)
        previous_hash = state.cursor.get("index_hash")
        now = self._now()
        previous_revalidated_at = _cursor_datetime(state.cursor.get("last_revalidated_at"))
        revalidate_seconds = _revalidate_interval_seconds(source)
        revalidation_due = (
            previous_revalidated_at is None
            or now >= previous_revalidated_at + timedelta(seconds=revalidate_seconds)
        )
        should_fetch_window = previous_hash != index_hash or revalidation_due
        items = refs if should_fetch_window else []
        revalidated_at = now if should_fetch_window else previous_revalidated_at
        next_cursor: dict[str, JsonValue] = {
            "index_hash": index_hash,
            "window_size": len(refs),
        }
        if revalidated_at is not None:
            next_cursor["last_revalidated_at"] = revalidated_at.isoformat()
        return DiscoveryBatch(
            items=items,
            next_cursor=next_cursor,
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if not ref.canonical_url:
            raise SourceSchemaChanged("HTML discovered ref has no canonical URL")
        allowed_hosts = _allowed_hosts(source, _required_setting(source, "index_url"))
        if not _is_allowed_url(ref.canonical_url, allowed_hosts):
            raise ValueError("HTML source URL is outside configured allowed_hosts")
        response = await self._get(ref.canonical_url)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        allowed_media_types = _allowed_media_types(source)
        effective_media_type = content_type or "text/html"
        if effective_media_type not in allowed_media_types:
            raise SourceSchemaChanged(
                "HTML-index document returned unexpected content type "
                f"{effective_media_type!r}; allowed={sorted(allowed_media_types)!r}"
            )
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")
        updated_at = None
        if last_modified:
            try:
                updated_at = parsedate_to_datetime(last_modified)
            except (TypeError, ValueError):
                updated_at = None
        revision = etag or last_modified or ref.external_revision
        metadata: dict[str, JsonValue] = dict(ref.locator)
        if etag:
            metadata["etag"] = etag
        if last_modified:
            metadata["last_modified"] = last_modified
        metadata["provider"] = source.source_family
        return IngestEnvelope.for_binary_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            body=response.content,
            media_type=effective_media_type,
            canonical_url=str(response.url),
            published_at=ref.published_at,
            updated_at=updated_at or ref.updated_at,
            external_revision=revision,
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
        url = spec.filters.get("url")
        if not isinstance(url, str) or not url:
            raise ValueError("HTML index query requires filters.url")
        allowed_hosts = _allowed_hosts(source, _required_setting(source, "index_url"))
        if not _is_allowed_url(url, allowed_hosts):
            raise ValueError("HTML source query URL is outside configured allowed_hosts")
        ref = DiscoveredRef(
            external_object_id=_url_identity(url),
            canonical_url=url,
        )
        return [
            await self.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
        ]

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
                f"HTML source request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("HTML source rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"HTML source returned HTTP {response.status_code}")
        return response


def _required_setting(source: SourceDefinition, key: str) -> str:
    value = source.discovery_method.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"HTML source requires discovery_method.{key}")
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


def _revalidate_interval_seconds(source: SourceDefinition) -> int:
    configured = source.discovery_method.get("revalidate_interval_seconds")
    if configured is not None:
        return _positive_int(configured, default=HTMLIndexAdapter.DEFAULT_REVALIDATE_SECONDS)
    schedule_seconds = _positive_int(
        source.schedule_policy.get("interval_seconds"),
        default=HTMLIndexAdapter.DEFAULT_REVALIDATE_SECONDS,
    )
    return max(schedule_seconds, HTMLIndexAdapter.DEFAULT_REVALIDATE_SECONDS)


def _cursor_datetime(value: JsonValue | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _allowed_media_types(source: SourceDefinition) -> set[str]:
    configured = source.discovery_method.get("allowed_media_types")
    if configured is None:
        return {"text/html", "application/xhtml+xml"}
    if not isinstance(configured, list):
        raise ValueError("HTML source discovery_method.allowed_media_types must be a list")
    media_types = {
        item.strip().lower() for item in configured if isinstance(item, str) and item.strip()
    }
    if not media_types:
        raise ValueError("HTML source allowed_media_types cannot be empty")
    return media_types


def _allowed_hosts(source: SourceDefinition, index_url: str) -> set[str]:
    configured = source.discovery_method.get("allowed_hosts")
    hosts = (
        {item.lower() for item in configured if isinstance(item, str) and item}
        if isinstance(configured, list)
        else set()
    )
    index_host = urlparse(index_url).hostname
    if index_host:
        hosts.add(index_host.lower())
    return hosts


def _is_allowed_url(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    return parsed.scheme in {"http", "https"} and host is not None and host.lower() in allowed_hosts


def _title_for(container: Node, link: Node, title_selector: str | None) -> str:
    if title_selector:
        title_node = container.css_first(title_selector)
        if title_node is not None:
            value = " ".join(title_node.text(separator=" ", strip=True).split())
            if value:
                return value
    return " ".join(link.text(separator=" ", strip=True).split())


def _url_identity(url: str) -> str:
    return f"url:{sha256(url.encode()).hexdigest()}"


def _index_hash(refs: list[DiscoveredRef]) -> str:
    material = "\n".join(f"{ref.canonical_url}\t{ref.locator.get('title', '')}" for ref in refs)
    return sha256(material.encode()).hexdigest()
