from __future__ import annotations

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
from packages.sources.errors import SourceFetchFailed, SourceRateLimited, SourceSchemaChanged


class CISAKEVAdapter:
    DEFAULT_URL = (
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("CISA KEV source is configured for on-demand query")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        results = await self.query(
            source,
            QuerySpec(filters={"cve_id": ref.external_object_id}),
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
        )
        if len(results) != 1:
            raise SourceSchemaChanged(
                f"CISA KEV lookup returned {len(results)} records for {ref.external_object_id}"
            )
        return results[0]

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
            raise ValueError("CISA KEV query requires filters.cve_id")
        url = str(source.discovery_method.get("base_url") or self.DEFAULT_URL)
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"CISA KEV request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("CISA KEV rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"CISA KEV returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("CISA KEV response root is not an object")
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list):
            raise SourceSchemaChanged("CISA KEV response has no vulnerabilities list")
        matches = [
            item
            for item in vulnerabilities
            if isinstance(item, dict) and item.get("cveID") == cve_id.upper()
        ]
        catalog_version = payload.get("catalogVersion")
        catalog_date = payload.get("dateReleased")
        observed = datetime.now(UTC)
        return [
            IngestEnvelope.for_json_payload(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=source.source_id,
                external_object_id=cve_id.upper(),
                payload={
                    "catalogVersion": catalog_version,
                    "dateReleased": catalog_date,
                    "vulnerability": item,
                },
                canonical_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                published_at=_date_as_datetime(item.get("dateAdded")),
                updated_at=_optional_datetime(catalog_date),
                external_revision=str(catalog_version) if catalog_version is not None else None,
                request_metadata={"provider": "cisa_kev"},
                observed_at=observed,
            )
            for item in matches
        ]


def _date_as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(f"{value}T00:00:00+00:00")


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
