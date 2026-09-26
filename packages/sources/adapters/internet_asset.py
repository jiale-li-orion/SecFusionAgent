from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime
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
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class CensysAssetAdapter:
    DEFAULT_URL = "https://api.platform.censys.io/v3/global/search/query"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        pat: str | None,
        organization_id: str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._pat = pat
        self._organization_id = organization_id
        self._now = now or (lambda: datetime.now(UTC))

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("Censys asset source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("Censys asset source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        if not self._pat:
            raise SourceAuthFailed("Censys PAT is required")
        query = _required_query(spec, "Censys")
        page_size = _bounded_int(spec.filters.get("page_size", 25), "page_size", 1, 100)
        page_token = spec.filters.get("page_token")
        if page_token is not None and not isinstance(page_token, str):
            raise ValueError("Censys page_token must be a string")
        fields = spec.filters.get("fields")
        if fields is None:
            fields = [
                "host.ip",
                "host.name",
                "host.location.country",
                "host.location.city",
                "host.autonomous_system.asn",
                "host.autonomous_system.name",
                "host.services.port",
                "host.services.transport_protocol",
                "host.services.protocol",
                "host.services.software.product",
                "host.services.software.version",
            ]
        if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
            raise ValueError("Censys fields must be a list of strings")
        body: dict[str, Any] = {"query": query, "page_size": page_size, "fields": fields}
        if page_token:
            body["page_token"] = page_token
        headers = {"Authorization": f"Bearer {self._pat}", "Accept": "application/json"}
        params: dict[str, str | int] = {}
        if self._organization_id:
            params["organization_id"] = self._organization_id
        url = str(source.discovery_method.get("base_url") or self.DEFAULT_URL)
        response = await _request_json(
            self._client,
            "POST",
            url,
            provider="Censys",
            headers=headers,
            params=params,
            json=body,
        )
        result = response.get("result")
        if not isinstance(result, dict):
            raise SourceSchemaChanged("Censys response has no result object")
        hits = result.get("hits")
        if not isinstance(hits, list):
            raise SourceSchemaChanged("Censys response has no result.hits list")
        observed_at = self._now()
        next_token = result.get("next_page_token") or result.get("nextPageToken")
        return [
            _asset_envelope(
                source,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                provider="censys",
                query=query,
                payload=_normalize_censys_hit(hit),
                observed_at=observed_at,
                request_metadata={
                    "page_size": page_size,
                    "next_page_token": next_token,
                },
            )
            for hit in hits
            if isinstance(hit, dict) and _censys_has_host(hit)
        ]


class FOFAAssetAdapter:
    DEFAULT_URL = "https://fofa.info/api/v1/search/next"
    DEFAULT_FIELDS = "ip,port,protocol,country,city,asn,org,host,domain,os,server,product,version"

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

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("FOFA asset source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("FOFA asset source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        if not self._api_key:
            raise SourceAuthFailed("FOFA API key is required")
        query = _required_query(spec, "FOFA")
        size = _bounded_int(spec.filters.get("size", 25), "size", 1, 10000)
        fields_value = spec.filters.get("fields", self.DEFAULT_FIELDS)
        if not isinstance(fields_value, str) or not fields_value.strip():
            raise ValueError("FOFA fields must be a non-empty string")
        fields = [item.strip() for item in fields_value.split(",") if item.strip()]
        params: dict[str, str | int] = {
            "key": self._api_key,
            "qbase64": base64.b64encode(query.encode()).decode(),
            "fields": ",".join(fields),
            "size": size,
            "r_type": "json",
        }
        next_token = spec.filters.get("next")
        if isinstance(next_token, str) and next_token:
            params["next"] = next_token
        url = str(source.discovery_method.get("base_url") or self.DEFAULT_URL)
        payload = await _request_json(
            self._client,
            "GET",
            url,
            provider="FOFA",
            params=params,
        )
        if payload.get("error") is True:
            message = payload.get("errmsg") or payload.get("message") or "FOFA API error"
            raise SourceFetchFailed(str(message))
        results = payload.get("results")
        if not isinstance(results, list):
            raise SourceSchemaChanged("FOFA response has no results list")
        observed_at = self._now()
        return [
            _asset_envelope(
                source,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                provider="fofa",
                query=query,
                payload=_normalize_fofa_row(row, fields),
                observed_at=observed_at,
                request_metadata={"next": payload.get("next"), "fields": fields},
            )
            for row in results
            if isinstance(row, list) and row
        ]


class ZoomEyeAssetAdapter:
    DEFAULT_URL = "https://api.zoomeye.ai/v2/search"

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

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("ZoomEye asset source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("ZoomEye asset source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        if not self._api_key:
            raise SourceAuthFailed("ZoomEye API key is required")
        query = _required_query(spec, "ZoomEye")
        page = _bounded_int(spec.filters.get("page", 1), "page", 1, 100000)
        page_size = _bounded_int(spec.filters.get("pagesize", 20), "pagesize", 1, 10000)
        body = {
            "qbase64": base64.b64encode(query.encode()).decode(),
            "page": page,
            "pagesize": page_size,
        }
        url = str(source.discovery_method.get("base_url") or self.DEFAULT_URL)
        payload = await _request_json(
            self._client,
            "POST",
            url,
            provider="ZoomEye",
            headers={"API-KEY": self._api_key, "Content-Type": "application/json"},
            json=body,
        )
        code = payload.get("code")
        if code != 60000:
            if code in {60001, 60002, 60003, 60005}:
                raise SourceAuthFailed(f"ZoomEye API rejected credentials/permission: code={code}")
            raise SourceFetchFailed(f"ZoomEye API returned business code={code!r}")
        records = payload.get("data")
        if not isinstance(records, list):
            raise SourceSchemaChanged("ZoomEye response has no data list")
        observed_at = self._now()
        return [
            _asset_envelope(
                source,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                provider="zoomeye",
                query=query,
                payload=_normalize_zoomeye_record(record),
                observed_at=observed_at,
                request_metadata={"page": page, "pagesize": page_size},
            )
            for record in records
            if isinstance(record, dict) and record.get("ip")
        ]


def _required_query(spec: QuerySpec, provider: str) -> str:
    query = spec.filters.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(f"{provider} query requires filters.query")
    return query.strip()


def _bounded_int(value: object, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise SourceFetchFailed(f"{provider} request failed: {exc.__class__.__name__}") from exc
    if response.status_code == 429:
        raise SourceRateLimited(f"{provider} rate limit reached")
    if response.status_code in {401, 403}:
        raise SourceAuthFailed(
            f"{provider} authentication/permission failed with HTTP {response.status_code}"
        )
    if response.is_error:
        raise SourceFetchFailed(f"{provider} returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceSchemaChanged(f"{provider} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SourceSchemaChanged(f"{provider} response root must be an object")
    return payload


def _asset_envelope(
    source: SourceDefinition,
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
    provider: str,
    query: str,
    payload: dict[str, Any],
    observed_at: datetime,
    request_metadata: dict[str, Any],
) -> IngestEnvelope:
    ip_value = payload.get("ip")
    port = payload.get("port")
    transport = payload.get("transport") or "tcp"
    if not isinstance(ip_value, str) or not isinstance(port, int) or isinstance(port, bool):
        raise SourceSchemaChanged(f"{provider} normalized result is missing ip/port")
    if not isinstance(transport, str):
        transport = "tcp"
    external_id = f"{ip_value}:{port}/{transport.lower()}"
    metadata: dict[str, Any] = {"provider": provider, "query": query}
    metadata.update(request_metadata)
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=external_id,
        payload=payload,
        canonical_url=None,
        published_at=None,
        updated_at=observed_at,
        external_revision=observed_at.isoformat(),
        request_metadata=metadata,
        observed_at=observed_at,
    )


def _censys_has_host(hit: dict[str, Any]) -> bool:
    host = hit.get("host")
    return isinstance(host, dict) and isinstance(host.get("ip"), str)


def _normalize_censys_hit(hit: dict[str, Any]) -> dict[str, Any]:
    host = hit.get("host")
    if not isinstance(host, dict):
        raise SourceSchemaChanged("Censys hit has no host object")
    ip_value = host.get("ip")
    matched = hit.get("matched_services")
    if not isinstance(matched, list):
        matched = host.get("services")
    services = matched if isinstance(matched, list) else []
    service = next((item for item in services if isinstance(item, dict)), {})
    software = service.get("software") if isinstance(service, dict) else None
    software_item: dict[str, Any] = {}
    if isinstance(software, list):
        software_item = next((item for item in software if isinstance(item, dict)), {})
    elif isinstance(software, dict):
        software_item = software
    asn = host.get("autonomous_system")
    asn_obj = asn if isinstance(asn, dict) else {}
    location = host.get("location")
    location_obj = location if isinstance(location, dict) else {}
    return {
        "ip": ip_value,
        "port": _first_int(service, "port"),
        "transport": _first_string(service, "transport_protocol") or "tcp",
        "protocol": _first_string(service, "protocol"),
        "product": _first_string(software_item, "product"),
        "version": _first_string(software_item, "version"),
        "org": _first_string(asn_obj, "name"),
        "asn": str(asn_obj.get("asn")) if asn_obj.get("asn") is not None else None,
        "hostnames": _hostnames(host),
        "domains": _domains(host),
        "location": location_obj,
        "raw_provider_record": hit,
    }


def _normalize_fofa_row(row: list[Any], fields: list[str]) -> dict[str, Any]:
    values = {field: row[index] if index < len(row) else None for index, field in enumerate(fields)}
    port_int = _coerce_int(values.get("port"))
    return {
        "ip": values.get("ip"),
        "port": port_int,
        "transport": values.get("protocol") or "tcp",
        "protocol": values.get("protocol"),
        "product": values.get("product") or values.get("server"),
        "version": values.get("version"),
        "org": values.get("org"),
        "asn": str(values.get("asn")) if values.get("asn") is not None else None,
        "os": values.get("os"),
        "hostnames": [values["host"]]
        if isinstance(values.get("host"), str) and values.get("host")
        else [],
        "domains": [values["domain"]]
        if isinstance(values.get("domain"), str) and values.get("domain")
        else [],
        "location": {"country": values.get("country"), "city": values.get("city")},
        "raw_provider_record": values,
    }


def _normalize_zoomeye_record(record: dict[str, Any]) -> dict[str, Any]:
    port_int = _coerce_int(record.get("port"))
    country = record.get("country")
    city = record.get("city")
    country_name = country.get("name") if isinstance(country, dict) else country
    city_name = city.get("name") if isinstance(city, dict) else city
    hostname = record.get("hostname")
    domain = record.get("domain")
    return {
        "ip": record.get("ip"),
        "port": port_int,
        "transport": record.get("protocol") or "tcp",
        "protocol": record.get("service") or record.get("protocol"),
        "product": record.get("product"),
        "version": record.get("version"),
        "org": record.get("org"),
        "asn": str(record.get("asn")) if record.get("asn") is not None else None,
        "os": record.get("os"),
        "banner": record.get("banner"),
        "hostnames": [hostname] if isinstance(hostname, str) and hostname else [],
        "domains": [domain] if isinstance(domain, str) and domain else [],
        "location": {"country": country_name, "city": city_name},
        "raw_provider_record": record,
    }


def _first_string(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    return item if isinstance(item, str) and item else None


def _first_int(value: dict[str, Any], key: str) -> int | None:
    item = value.get(key)
    if isinstance(item, bool):
        return None
    if isinstance(item, int):
        return item
    if isinstance(item, str) and item.isdigit():
        return int(item)
    return None


def _hostnames(host: dict[str, Any]) -> list[str]:
    names = (
        host.get("name") or host.get("names") or host.get("dns", {}).get("names")
        if isinstance(host.get("dns"), dict)
        else None
    )
    if isinstance(names, str):
        return [names]
    if isinstance(names, list):
        return [item for item in names if isinstance(item, str)]
    return []


def _domains(host: dict[str, Any]) -> list[str]:
    dns = host.get("dns")
    if not isinstance(dns, dict):
        return []
    names = dns.get("names")
    return [item for item in names if isinstance(item, str)] if isinstance(names, list) else []


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
