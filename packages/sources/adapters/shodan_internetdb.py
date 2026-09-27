from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import ip_address
from typing import Any

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
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class ShodanInternetDBAdapter:
    """Passive Shodan InternetDB lookup for a concrete IP address."""

    DEFAULT_BASE_URL = "https://internetdb.shodan.io"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._now = now or (lambda: datetime.now(UTC))

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("Shodan InternetDB source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("Shodan InternetDB source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        raw_ip = spec.filters.get("ip")
        if not isinstance(raw_ip, str) or not raw_ip.strip():
            raise ValueError("Shodan InternetDB query requires filters.ip")
        try:
            target_ip = str(ip_address(raw_ip.strip()))
        except ValueError as exc:
            raise ValueError("Shodan InternetDB filters.ip must be a valid IP address") from exc

        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        url = f"{base_url}/{target_ip}"
        try:
            response = await self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"Shodan InternetDB request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 404:
            return []
        if response.status_code == 429:
            raise SourceRateLimited("Shodan InternetDB rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"Shodan InternetDB returned HTTP {response.status_code}")
        try:
            raw = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("Shodan InternetDB returned invalid JSON") from exc
        if not isinstance(raw, dict):
            raise SourceSchemaChanged("Shodan InternetDB response root must be an object")

        response_ip = raw.get("ip")
        if response_ip is not None and response_ip != target_ip:
            raise SourceSchemaChanged("Shodan InternetDB response IP does not match query")
        ports = raw.get("ports")
        if not isinstance(ports, list) or not all(
            isinstance(port, int) and not isinstance(port, bool) for port in ports
        ):
            raise SourceSchemaChanged("Shodan InternetDB response has invalid ports")

        observed_at = self._now()
        metadata: dict[str, Any] = {
            "provider": "shodan-internetdb",
            "query": f"ip={target_ip}",
            "passive_observation": True,
        }
        for key in ("discovery_context", "relation_context"):
            value = spec.filters.get(key)
            if isinstance(value, dict):
                metadata[key] = value

        return [
            IngestEnvelope.for_json_payload(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=source.source_id,
                external_object_id=f"{target_ip}:{port}/tcp",
                payload=_normalize_internetdb_record(raw, target_ip, port),
                canonical_url=url,
                published_at=None,
                updated_at=observed_at,
                external_revision=observed_at.isoformat(),
                request_metadata=metadata,
                observed_at=observed_at,
            )
            for port in ports
        ]


def _normalize_internetdb_record(raw: dict[str, Any], target_ip: str, port: int) -> dict[str, Any]:
    return {
        "ip": target_ip,
        "port": port,
        "transport": "tcp",
        "hostnames": _string_list(raw.get("hostnames")),
        "domains": [],
        "product": None,
        "version": None,
        "org": None,
        "isp": None,
        "asn": None,
        "cpe": _string_list(raw.get("cpes")),
        "tags": _string_list(raw.get("tags")),
        "vulns": _string_list(raw.get("vulns")),
        "location": {},
        "raw_provider_record": raw,
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
