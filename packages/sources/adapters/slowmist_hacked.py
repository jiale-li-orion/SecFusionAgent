from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

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

_LOSS_RE = re.compile(r"Amount of loss:\s*\$?\s*([\d,.]+)", re.IGNORECASE)
_METHOD_RE = re.compile(r"Attack method:\s*(.+)$", re.IGNORECASE)
_TARGET_PREFIX_RE = re.compile(r"^Hacked target:\s*", re.IGNORECASE)


class SlowMistHackedAdapter:
    DEFAULT_URL = "https://hacked.slowmist.io/"
    USER_AGENT = "SecFusionAgent/0.1 slowmist-hacked-source-adapter"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        index_url = str(source.discovery_method.get("index_url") or self.DEFAULT_URL)
        max_items = _positive_int(source.discovery_method.get("max_items"), 100)
        response = await self._get(index_url)
        tree = HTMLParser(response.text)
        cards = tree.css("div.case-content ul > li")
        if not cards:
            raise SourceSchemaChanged("SlowMist Hacked page produced no incident cards")

        previous = state.cursor.get("item_revisions")
        previous_revisions = previous if isinstance(previous, dict) else {}
        next_revisions: dict[str, JsonValue] = {}
        items: list[DiscoveredRef] = []

        for card in cards[:max_items]:
            parsed = _parse_card(card)
            external_id = _event_identity(parsed)
            revision = hashlib.sha256(
                json.dumps(parsed, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            next_revisions[external_id] = revision
            if previous_revisions.get(external_id) == revision:
                continue
            published_at = _date_to_datetime(parsed["event_date"])
            items.append(
                DiscoveredRef(
                    external_object_id=external_id,
                    canonical_url=str(response.url),
                    published_at=published_at,
                    updated_at=published_at,
                    external_revision=revision,
                    locator={
                        "target": parsed["target"],
                        "reference_url": parsed.get("reference_url"),
                    },
                    inline_payload=_signal_payload(parsed),
                )
            )

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
            raise SourceSchemaChanged("SlowMist Hacked ref has no inline payload")
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
                "transport": "slowmist_hacked_html",
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
        raise ValueError("SlowMist Hacked source supports scheduled discovery only")

    async def _get(self, url: str) -> httpx.Response:
        try:
            response = await self._client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"SlowMist Hacked request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 429:
            raise SourceRateLimited("SlowMist Hacked rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"SlowMist Hacked returned HTTP {response.status_code}")
        return response


def _parse_card(card) -> dict[str, str | None]:
    date_node = card.css_first("span.time")
    target_node = card.css_first("h3")
    if date_node is None or target_node is None:
        raise SourceSchemaChanged("SlowMist incident card is missing date/target")
    event_date = " ".join(date_node.text(separator=" ", strip=True).split())
    target_text = " ".join(target_node.text(separator=" ", strip=True).split())
    target = _TARGET_PREFIX_RE.sub("", target_text).strip()
    if not target:
        raise SourceSchemaChanged("SlowMist incident card has empty target")

    paragraphs = [
        node
        for node in card.css("p")
        if "link-reference" not in (node.attributes.get("class") or "")
    ]
    description = ""
    details = ""
    if paragraphs:
        description = " ".join(paragraphs[0].text(separator=" ", strip=True).split())
        description = re.sub(r"^Description of the event:\s*", "", description, flags=re.I)
    if len(paragraphs) > 1:
        details = " ".join(paragraphs[1].text(separator=" ", strip=True).split())
    loss_match = _LOSS_RE.search(details)
    method_match = _METHOD_RE.search(details)
    reference = card.css_first("p.link-reference a[href]")
    reference_url = reference.attributes.get("href") if reference is not None else None
    return {
        "event_date": event_date,
        "target": target,
        "description": description or None,
        "loss_amount_usd_text": loss_match.group(1) if loss_match else None,
        "attack_method": method_match.group(1).strip() if method_match else None,
        "reference_url": reference_url,
    }


def _signal_payload(parsed: dict[str, str | None]) -> dict[str, JsonValue]:
    target = parsed["target"]
    assert isinstance(target, str)
    summary_parts = [part for part in [parsed.get("description")] if isinstance(part, str)]
    attack_method = parsed.get("attack_method")
    loss = parsed.get("loss_amount_usd_text")
    if isinstance(attack_method, str):
        summary_parts.append(f"Attack method: {attack_method}")
    if isinstance(loss, str):
        summary_parts.append(f"Reported loss: USD {loss}")
    reference = parsed.get("reference_url")
    payload: dict[str, JsonValue] = {
        "title": f"{target} security incident",
        "summary": ". ".join(summary_parts) if summary_parts else None,
        "incident_type": "security-incident",
        "entity_hints": {"project": [target]},
        "anchors": {},
        "unresolved_questions": ["primary confirmation", "root cause", "affected scope"],
        "event_type": "reported",
        "event_date": parsed.get("event_date"),
        "loss_amount_usd_text": loss,
        "attack_method": attack_method,
        "reference_url": reference,
    }
    if isinstance(reference, str) and reference:
        payload["upstream_source"] = _upstream_identity(reference)
    return payload


def _event_identity(parsed: dict[str, str | None]) -> str:
    material = "|".join(
        str(parsed.get(key) or "") for key in ("event_date", "target", "reference_url")
    )
    return f"slowmist:{hashlib.sha256(material.encode()).hexdigest()}"


def _upstream_identity(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "unknown").lower()
    first_path = next((part for part in parsed.path.split("/") if part), "")
    return f"{host}/{first_path}" if first_path else host


def _date_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise SourceSchemaChanged(f"invalid SlowMist event date: {value}") from exc


def _positive_int(value: JsonValue | None, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default
