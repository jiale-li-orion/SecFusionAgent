from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

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

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,8}\b", re.IGNORECASE)
GHSA_RE = re.compile(
    r"\bGHSA-[23456789cfghjmpqrvwx]{4}-"
    r"[23456789cfghjmpqrvwx]{4}-[23456789cfghjmpqrvwx]{4}\b",
    re.IGNORECASE,
)
ETH_TX_RE = re.compile(r"\b0x[a-fA-F0-9]{64}\b")
ETH_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")


class RSSIncidentAdapter:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        feed_url = source.discovery_method.get("feed_url")
        if not isinstance(feed_url, str) or not feed_url:
            raise ValueError("RSS incident source requires discovery_method.feed_url")
        headers = {
            "User-Agent": "SecFusionAgent/0.1 (+security-intelligence-research)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        }
        try:
            response = await self._client.get(feed_url, headers=headers, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"RSS request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("RSS source rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"RSS source returned HTTP {response.status_code}")

        items = _parse_feed(response.text)
        previous = state.cursor.get("item_revisions")
        previous_revisions = previous if isinstance(previous, dict) else {}
        next_revisions: dict[str, JsonValue] = {}
        discovered: list[DiscoveredRef] = []
        for item in items:
            item_id = item["external_object_id"]
            revision = item["revision"]
            next_revisions[item_id] = revision
            if previous_revisions.get(item_id) != revision:
                discovered.append(
                    DiscoveredRef(
                        external_object_id=item_id,
                        canonical_url=item["link"],
                        published_at=item["published_at"],
                        updated_at=item["published_at"],
                        external_revision=revision,
                        locator={},
                        inline_payload=item["payload"],
                    )
                )
        return DiscoveryBatch(
            items=discovered,
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
            raise SourceSchemaChanged("RSS discovered item has no inline payload")
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
            request_metadata={"provider": source.source_family, "transport": "rss"},
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
        raise ValueError("RSS incident source supports scheduled discovery only")


def _parse_feed(payload: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SourceSchemaChanged("RSS source returned invalid XML") from exc
    local_root = _local_name(root.tag)
    if local_root == "rss":
        return [_rss_item(item) for item in root.findall("./channel/item")]
    if local_root == "feed":
        return [_atom_entry(entry) for entry in list(root) if _local_name(entry.tag) == "entry"]
    raise SourceSchemaChanged(f"unsupported feed root: {local_root}")


def _rss_item(item: ET.Element) -> dict[str, Any]:
    title = _child_text(item, "title", required=True)
    link = _child_text(item, "link", required=True)
    assert title is not None
    assert link is not None
    guid = _child_text(item, "guid") or link
    description = _clean_html(_child_text(item, "description") or "")
    published_at = _parse_feed_datetime(_child_text(item, "pubDate"))
    return _feed_item(
        external_object_id=guid,
        title=title,
        link=link,
        summary=description,
        published_at=published_at,
    )


def _atom_entry(entry: ET.Element) -> dict[str, Any]:
    children = {_local_name(child.tag): child for child in list(entry)}
    title = _element_text(children.get("title"), required=True)
    external_id = _element_text(children.get("id"), required=True)
    assert title is not None
    assert external_id is not None
    summary = _clean_html(
        _element_text(children.get("summary")) or _element_text(children.get("content")) or ""
    )
    link = external_id
    for child in list(entry):
        if _local_name(child.tag) != "link":
            continue
        if child.attrib.get("rel", "alternate") == "alternate" and child.attrib.get("href"):
            link = child.attrib["href"]
            break
    published = _element_text(children.get("published")) or _element_text(children.get("updated"))
    return _feed_item(
        external_object_id=external_id,
        title=title,
        link=link,
        summary=summary,
        published_at=_parse_feed_datetime(published),
    )


def _feed_item(
    *,
    external_object_id: str,
    title: str,
    link: str,
    summary: str,
    published_at: datetime | None,
) -> dict[str, Any]:
    text = f"{title}\n{summary}"
    anchors = _extract_anchors(text)
    normalized = {
        "title": title,
        "summary": summary,
        "incident_type": "security-incident",
        "entity_hints": {},
        "anchors": anchors,
        "unresolved_questions": ["impact", "root cause", "primary confirmation"],
        "event_type": "reported",
    }
    revision_material = f"{title}\n{summary}\n{published_at.isoformat() if published_at else ''}"
    return {
        "external_object_id": external_object_id,
        "link": link,
        "published_at": published_at,
        "revision": hashlib.sha256(revision_material.encode()).hexdigest(),
        "payload": normalized,
    }


def _extract_anchors(text: str) -> dict[str, list[str]]:
    anchors: dict[str, list[str]] = {}
    cves = sorted({match.upper() for match in CVE_RE.findall(text)})
    ghsas = sorted({match.upper() for match in GHSA_RE.findall(text)})
    tx_hashes = sorted(set(ETH_TX_RE.findall(text)))
    addresses = sorted(set(ETH_ADDRESS_RE.findall(text)) - set(tx_hashes))
    if cves:
        anchors["cve"] = cves
    if ghsas:
        anchors["ghsa"] = ghsas
    if tx_hashes:
        anchors["tx_hash"] = tx_hashes
    if addresses:
        anchors["address"] = addresses
    return anchors


def _child_text(parent: ET.Element, name: str, *, required: bool = False) -> str | None:
    for child in list(parent):
        if _local_name(child.tag) == name:
            return _element_text(child, required=required)
    if required:
        raise SourceSchemaChanged(f"feed item missing {name}")
    return None


def _element_text(element: ET.Element | None, *, required: bool = False) -> str | None:
    value = "" if element is None else "".join(element.itertext()).strip()
    if required and not value:
        raise SourceSchemaChanged("feed item missing required text")
    return value or None


def _parse_feed_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SourceSchemaChanged(f"invalid feed timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _clean_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(html.unescape(value))
    return " ".join(" ".join(parser.parts).split())
