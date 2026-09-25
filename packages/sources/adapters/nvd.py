from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
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


class NVDAdapter:
    """NVD CVE API 2.0 adapter.

    NVD is treated as an external canonical bug source. Discovery uses the
    provider's last-modified window; the returned CVE payload is carried
    inline so the hot path does not perform a second request per CVE.
    """

    DEFAULT_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str | None = None,
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
        end = self._now()
        cursor_value = state.cursor.get("last_modified")
        if isinstance(cursor_value, str):
            start = _parse_datetime(cursor_value)
        else:
            lookback = _int_setting(
                source.discovery_method.get("initial_lookback_seconds"), default=3600
            )
            start = end - timedelta(seconds=lookback)

        page_size = _int_setting(source.discovery_method.get("results_per_page"), default=2000)
        params: dict[str, str | int] = {
            "lastModStartDate": _nvd_datetime(start),
            "lastModEndDate": _nvd_datetime(end),
            "resultsPerPage": page_size,
        }
        vulnerabilities: list[dict[str, Any]] = []
        start_index = 0
        while True:
            payload = await self._get_json(source, params={**params, "startIndex": start_index})
            page = _expect_vulnerabilities(payload)
            vulnerabilities.extend(page)
            total_results = _expect_int(payload, "totalResults")
            if start_index + len(page) >= total_results:
                break
            if not page:
                raise SourceSchemaChanged("NVD pagination returned an empty non-terminal page")
            start_index += len(page)
        items = [_to_discovered_ref(source, item) for item in vulnerabilities]
        return DiscoveryBatch(
            items=items,
            next_cursor={"last_modified": end.isoformat()},
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if ref.inline_payload is not None:
            vulnerability = ref.inline_payload
        else:
            payload = await self._get_json(source, params={"cveId": ref.external_object_id})
            vulnerabilities = _expect_vulnerabilities(payload)
            if len(vulnerabilities) != 1:
                raise SourceSchemaChanged(
                    f"NVD cveId query returned {len(vulnerabilities)} records"
                )
            vulnerability = vulnerabilities[0]
        return _to_ingest_envelope(
            source,
            vulnerability,
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        cve_id = spec.filters.get("cve_id")
        if not isinstance(cve_id, str) or not cve_id:
            raise ValueError("NVD query currently requires filters.cve_id")
        payload = await self._get_json(source, params={"cveId": cve_id})
        vulnerabilities = _expect_vulnerabilities(payload)
        return [
            _to_ingest_envelope(
                source,
                vulnerability,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            for vulnerability in vulnerabilities
        ]

    async def _get_json(
        self,
        source: SourceDefinition,
        *,
        params: dict[str, str | int],
    ) -> dict[str, Any]:
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL)
        headers = {"apiKey": self._api_key} if self._api_key else {}
        try:
            response = await self._client.get(base_url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"NVD request failed: {exc.__class__.__name__}") from exc
        if response.status_code in {401, 403}:
            raise SourceAuthFailed("NVD rejected credentials")
        if response.status_code == 429:
            raise SourceRateLimited("NVD rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"NVD returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("NVD response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("NVD response root is not an object")
        return payload


def _expect_vulnerabilities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    vulnerabilities = payload.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        raise SourceSchemaChanged("NVD response has no vulnerabilities list")
    if not all(isinstance(item, dict) for item in vulnerabilities):
        raise SourceSchemaChanged("NVD vulnerabilities contains a non-object item")
    return vulnerabilities


def _expect_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaChanged(f"NVD response {key} is missing or invalid")
    return value


def _to_discovered_ref(source: SourceDefinition, vulnerability: dict[str, Any]) -> DiscoveredRef:
    cve = _expect_cve(vulnerability)
    cve_id = _expect_text(cve, "id")
    published = _optional_datetime(cve.get("published"))
    updated = _optional_datetime(cve.get("lastModified"))
    revision = updated.isoformat() if updated else None
    return DiscoveredRef(
        external_object_id=cve_id,
        canonical_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        published_at=published,
        updated_at=updated,
        external_revision=revision,
        locator={"cve_id": cve_id},
        inline_payload=vulnerability,
    )


def _to_ingest_envelope(
    source: SourceDefinition,
    vulnerability: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
) -> IngestEnvelope:
    ref = _to_discovered_ref(source, vulnerability)
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=ref.external_object_id,
        payload=vulnerability,
        canonical_url=ref.canonical_url,
        published_at=ref.published_at,
        updated_at=ref.updated_at,
        external_revision=ref.external_revision,
        request_metadata={"provider": "nvd", "api_version": "2.0"},
    )


def _expect_cve(vulnerability: dict[str, Any]) -> dict[str, Any]:
    cve = vulnerability.get("cve")
    if not isinstance(cve, dict):
        raise SourceSchemaChanged("NVD vulnerability has no cve object")
    return cve


def _expect_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SourceSchemaChanged(f"NVD cve.{key} is missing or invalid")
    return value


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceSchemaChanged("NVD timestamp is not a string")
    return _parse_datetime(value)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _nvd_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def _int_setting(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer setting")
    if isinstance(value, (str, int, float)):
        return int(value)
    raise ValueError(f"unsupported integer setting type: {type(value).__name__}")
