from __future__ import annotations

from datetime import datetime
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


class GitHubGlobalAdvisoryAdapter:
    DEFAULT_BASE_URL = "https://api.github.com/advisories"

    def __init__(self, client: httpx.AsyncClient, *, token: str | None = None) -> None:
        self._client = client
        self._token = token

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("GitHub global advisory source is configured for on-demand query")

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
            QuerySpec(filters={"ghsa_id": ref.external_object_id}),
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
        )
        if len(results) != 1:
            raise SourceSchemaChanged(
                f"GitHub advisory lookup returned {len(results)} records "
                f"for {ref.external_object_id}"
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
        params: dict[str, str] = {}
        for key in ("cve_id", "ghsa_id"):
            value = spec.filters.get(key)
            if isinstance(value, str) and value:
                params[key] = value
        if not params:
            raise ValueError("GitHub advisory query requires filters.cve_id or filters.ghsa_id")

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL)
        try:
            response = await self._client.get(base_url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"GitHub advisory request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code in {401, 403}:
            raise SourceAuthFailed("GitHub advisory API rejected credentials or rate limit")
        if response.status_code == 429:
            raise SourceRateLimited("GitHub advisory API rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"GitHub advisory API returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise SourceSchemaChanged("GitHub advisory response is not a list of objects")
        return [
            _to_envelope(
                source,
                item,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            for item in payload
        ]


def _to_envelope(
    source: SourceDefinition,
    payload: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
) -> IngestEnvelope:
    ghsa_id = payload.get("ghsa_id")
    if not isinstance(ghsa_id, str):
        raise SourceSchemaChanged("GitHub advisory has no ghsa_id")
    updated = _optional_datetime(payload.get("updated_at"))
    published = _optional_datetime(payload.get("published_at"))
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=ghsa_id,
        payload=payload,
        canonical_url=payload.get("html_url") if isinstance(payload.get("html_url"), str) else None,
        published_at=published,
        updated_at=updated,
        external_revision=updated.isoformat() if updated else None,
        request_metadata={"provider": "github_global_advisories"},
    )


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceSchemaChanged("GitHub advisory timestamp is not a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
