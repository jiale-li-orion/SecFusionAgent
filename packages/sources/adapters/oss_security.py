from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urljoin

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

_MESSAGE_HREF_RE = re.compile(r"^(\d{2})/(\d+)$")


class OssSecurityAdapter:
    """Openwall oss-security mailing-list archive adapter."""

    DEFAULT_ROOT = "https://www.openwall.com/lists/oss-security/"
    USER_AGENT = "SecFusionAgent/0.1 oss-security-source-adapter"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._now = now or (lambda: datetime.now(UTC))

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        root = str(source.discovery_method.get("root_url") or self.DEFAULT_ROOT)
        lookback_months = _positive_int(source.discovery_method.get("lookback_months"), 2)
        max_items = _positive_int(source.discovery_method.get("max_items"), 100)
        months = _recent_months(self._now(), lookback_months)

        previous = state.cursor.get("item_revisions")
        previous_revisions = previous if isinstance(previous, dict) else {}
        next_revisions: dict[str, JsonValue] = {}
        items: list[DiscoveredRef] = []

        for year, month in months:
            month_url = urljoin(root, f"{year:04d}/{month:02d}/")
            response = await self._get(month_url)
            tree = HTMLParser(response.text)
            for link in tree.css("a[href]"):
                href = link.attributes.get("href") or ""
                match = _MESSAGE_HREF_RE.fullmatch(href)
                if match is None:
                    continue
                day, ordinal = match.groups()
                title = " ".join(link.text(separator=" ", strip=True).split())
                if not title:
                    continue
                canonical_url = urljoin(str(response.url), href)
                external_id = f"{year:04d}/{month:02d}/{day}/{ordinal}"
                revision = hashlib.sha256(title.encode()).hexdigest()
                next_revisions[external_id] = revision
                if previous_revisions.get(external_id) != revision:
                    items.append(
                        DiscoveredRef(
                            external_object_id=external_id,
                            canonical_url=canonical_url,
                            external_revision=revision,
                            locator={
                                "month_url": str(response.url),
                                "subject": title,
                            },
                        )
                    )
                if len(items) >= max_items:
                    break
            if len(items) >= max_items:
                break

        # Keep the union for the active lookback window so replay remains stable
        # while old months naturally fall out of the cursor.
        for external_id, previous_revision in previous_revisions.items():
            if (
                isinstance(external_id, str)
                and isinstance(previous_revision, str)
                and _in_recent_months(external_id, months)
                and external_id not in next_revisions
            ):
                next_revisions[external_id] = previous_revision

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
        if ref.canonical_url is None:
            raise SourceSchemaChanged("oss-security ref has no canonical URL")
        response = await self._get(ref.canonical_url)
        content_type = response.headers.get("content-type", "text/html").split(";", 1)[0]
        return IngestEnvelope.for_binary_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            body=response.content,
            media_type=content_type or "text/html",
            canonical_url=str(response.url),
            published_at=None,
            updated_at=None,
            external_revision=response.headers.get("etag")
            or response.headers.get("last-modified")
            or ref.external_revision,
            request_metadata={
                "provider": "openwall-oss-security",
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
        message_id = spec.filters.get("message_id")
        if not isinstance(message_id, str) or not re.fullmatch(
            r"\d{4}/\d{2}/\d{2}/\d+", message_id
        ):
            raise ValueError("oss-security query requires filters.message_id=YYYY/MM/DD/N")
        root = str(source.discovery_method.get("root_url") or self.DEFAULT_ROOT)
        ref = DiscoveredRef(
            external_object_id=message_id,
            canonical_url=urljoin(root, message_id),
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
                headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"oss-security request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("oss-security rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"oss-security returned HTTP {response.status_code}")
        return response


def _positive_int(value: JsonValue | None, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _recent_months(now: datetime, count: int) -> list[tuple[int, int]]:
    year = now.year
    month = now.month
    result: list[tuple[int, int]] = []
    for _ in range(count):
        result.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return result


def _in_recent_months(external_id: str, months: list[tuple[int, int]]) -> bool:
    parts = external_id.split("/")
    if len(parts) != 4:
        return False
    try:
        key = (int(parts[0]), int(parts[1]))
    except ValueError:
        return False
    return key in months
