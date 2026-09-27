from __future__ import annotations

from datetime import UTC, datetime

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


class FIRSTEPSSAdapter:
    DEFAULT_URL = "https://api.first.org/data/v1/epss"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("FIRST EPSS source is configured for on-demand query")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        filters: dict[str, JsonValue] = {"cve_id": ref.external_object_id}
        if ref.external_revision:
            filters["date"] = ref.external_revision
        results = await self.query(
            source,
            QuerySpec(filters=filters),
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
        )
        if len(results) != 1:
            raise SourceSchemaChanged(
                f"FIRST EPSS lookup returned {len(results)} records for {ref.external_object_id}"
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
            raise ValueError("FIRST EPSS query requires filters.cve_id")
        params: dict[str, str] = {"cve": cve_id.upper()}
        score_date = spec.filters.get("date")
        if score_date is not None:
            if not isinstance(score_date, str) or not score_date:
                raise ValueError("FIRST EPSS filters.date must be YYYY-MM-DD text")
            params["date"] = score_date
        url = str(source.discovery_method.get("base_url") or self.DEFAULT_URL)
        try:
            response = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"FIRST EPSS request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("FIRST EPSS rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"FIRST EPSS returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("FIRST EPSS response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("FIRST EPSS response root is not an object")
        data = payload.get("data")
        if not isinstance(data, list):
            raise SourceSchemaChanged("FIRST EPSS response has no data list")

        results: list[IngestEnvelope] = []
        for item in data:
            if not isinstance(item, dict) or item.get("cve") != cve_id.upper():
                continue
            date_value = item.get("date") or item.get("created")
            normalized_date = date_value if isinstance(date_value, str) else None
            results.append(
                IngestEnvelope.for_json_payload(
                    acquisition_run_id=acquisition_run_id,
                    trigger=trigger,
                    source_id=source.source_id,
                    external_object_id=cve_id.upper(),
                    payload={
                        "api_version": payload.get("version"),
                        "record": item,
                    },
                    canonical_url=f"{url}?cve={cve_id.upper()}",
                    published_at=None,
                    updated_at=_date_as_datetime(normalized_date),
                    external_revision=normalized_date,
                    request_metadata={
                        "provider": "first_epss",
                        "score_date": normalized_date,
                    },
                    observed_at=datetime.now(UTC),
                )
            )
        return results


def _date_as_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")
    except ValueError:
        return None
