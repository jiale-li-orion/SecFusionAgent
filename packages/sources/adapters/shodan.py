from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import ip_address

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
from packages.sources.errors import (
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class ShodanAdapter:
    DEFAULT_BASE_URL = "https://api.shodan.io"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str | None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._now = now or (lambda: datetime.now(UTC))

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("Shodan asset source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("Shodan asset source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        if not self._api_key:
            raise SourceAuthFailed("Shodan API key is required")
        query = spec.filters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Shodan query requires filters.query")
        page = spec.filters.get("page", 1)
        if isinstance(page, bool) or not isinstance(page, int) or page <= 0:
            raise ValueError("Shodan query page must be a positive integer")
        minify = spec.filters.get("minify", True)
        if not isinstance(minify, bool):
            raise ValueError("Shodan query minify must be boolean")

        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        params: dict[str, str | int] = {
            "key": self._api_key,
            "query": query,
            "page": page,
            "minify": "true" if minify else "false",
        }
        fields = spec.filters.get("fields")
        if isinstance(fields, str) and fields:
            params["fields"] = fields

        try:
            response = await self._client.get(
                f"{base_url}/shodan/host/search",
                params=params,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"Shodan request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("Shodan rate limit reached")
        if response.status_code in {401, 403}:
            raise SourceAuthFailed(f"Shodan authentication failed with HTTP {response.status_code}")
        if response.is_error:
            raise SourceFetchFailed(f"Shodan search returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("Shodan search returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
            raise SourceSchemaChanged("Shodan search response has no matches list")

        observed_at = self._now()
        envelopes: list[IngestEnvelope] = []
        for match in payload["matches"]:
            if not isinstance(match, dict):
                continue
            external_id = _external_id(match)
            updated_at = _match_time(match) or observed_at
            envelopes.append(
                IngestEnvelope.for_json_payload(
                    acquisition_run_id=acquisition_run_id,
                    trigger=trigger,
                    source_id=source.source_id,
                    external_object_id=external_id,
                    payload=_normalize_match(match),
                    canonical_url=None,
                    published_at=None,
                    updated_at=updated_at,
                    external_revision=updated_at.isoformat(),
                    request_metadata={
                        "provider": "shodan",
                        "query": query,
                        "page": page,
                        "minify": minify,
                        "total": payload.get("total"),
                    },
                    observed_at=observed_at,
                )
            )
        return envelopes


def _external_id(match: dict[str, object]) -> str:
    ip_value = match.get("ip_str")
    if not isinstance(ip_value, str):
        numeric = match.get("ip")
        if not isinstance(numeric, int):
            raise SourceSchemaChanged("Shodan match has no ip_str/ip")
        ip_value = str(ip_address(numeric))
    port = match.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        raise SourceSchemaChanged("Shodan match has no integer port")
    transport = match.get("transport")
    transport_value = transport.lower() if isinstance(transport, str) and transport else "tcp"
    return f"{ip_value}:{port}/{transport_value}"


def _normalize_match(match: dict[str, object]) -> dict[str, object]:
    ip_value = match.get("ip_str")
    if not isinstance(ip_value, str):
        numeric = match.get("ip")
        if not isinstance(numeric, int) or isinstance(numeric, bool):
            raise SourceSchemaChanged("Shodan match has no ip_str/ip")
        ip_value = str(ip_address(numeric))
    port = match.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        raise SourceSchemaChanged("Shodan match has no integer port")
    transport = match.get("transport")
    shodan_meta = match.get("_shodan")
    protocol = shodan_meta.get("module") if isinstance(shodan_meta, dict) else None
    return {
        "ip": ip_value,
        "port": port,
        "transport": transport.lower() if isinstance(transport, str) and transport else "tcp",
        "protocol": protocol,
        "product": match.get("product"),
        "version": match.get("version"),
        "org": match.get("org"),
        "isp": match.get("isp"),
        "asn": match.get("asn"),
        "hostnames": match.get("hostnames") if isinstance(match.get("hostnames"), list) else [],
        "domains": match.get("domains") if isinstance(match.get("domains"), list) else [],
        "cpe": match.get("cpe") if isinstance(match.get("cpe"), list) else [],
        "location": match.get("location") if isinstance(match.get("location"), dict) else {},
        "banner": match.get("data"),
        "raw_provider_record": match,
    }


def _match_time(match: dict[str, object]) -> datetime | None:
    value = match.get("timestamp")
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceSchemaChanged(f"invalid Shodan timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
