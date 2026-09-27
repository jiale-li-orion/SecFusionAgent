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
from packages.sources.errors import SourceFetchFailed, SourceRateLimited, SourceSchemaChanged


class OSVAdapter:
    DEFAULT_BASE_URL = "https://api.osv.dev/v1/vulns"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("OSV source is configured for on-demand query")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        return await self._query_id(
            source,
            ref.external_object_id,
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
        vulnerability_id = spec.filters.get("vulnerability_id") or spec.filters.get("cve_id")
        if not isinstance(vulnerability_id, str) or not vulnerability_id:
            raise ValueError("OSV query requires filters.vulnerability_id or filters.cve_id")
        try:
            envelope = await self._query_id(
                source,
                vulnerability_id,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
        except SourceFetchFailed as exc:
            if "HTTP 404" in str(exc):
                return []
            raise
        results = [envelope]
        payload = envelope.json_payload
        if vulnerability_id.upper().startswith("CVE-") and not _has_package_affected(payload):
            seen_ids = {envelope.external_object_id}
            for alias in _ghsa_aliases(payload):
                try:
                    alias_envelope = await self._query_id(
                        source,
                        alias,
                        acquisition_run_id=acquisition_run_id,
                        trigger=trigger,
                    )
                except SourceFetchFailed as exc:
                    if "HTTP 404" in str(exc):
                        continue
                    raise
                if alias_envelope.external_object_id in seen_ids:
                    continue
                seen_ids.add(alias_envelope.external_object_id)
                results.append(alias_envelope)
        return results

    async def _query_id(
        self,
        source: SourceDefinition,
        vulnerability_id: str,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        try:
            response = await self._client.get(f"{base_url}/{vulnerability_id}")
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"OSV request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("OSV rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"OSV returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("OSV response root is not an object")
        external_id = payload.get("id")
        if not isinstance(external_id, str):
            raise SourceSchemaChanged("OSV response has no id")
        modified = _optional_datetime(payload.get("modified"))
        published = _optional_datetime(payload.get("published"))
        return IngestEnvelope.for_json_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=external_id,
            payload=payload,
            canonical_url=f"https://osv.dev/vulnerability/{external_id}",
            published_at=published,
            updated_at=modified,
            external_revision=modified.isoformat() if modified else None,
            request_metadata={"provider": "osv", "query_id": vulnerability_id},
        )


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceSchemaChanged("OSV timestamp is not a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _has_package_affected(payload: dict[str, Any]) -> bool:
    affected = payload.get("affected")
    if not isinstance(affected, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("package"), dict)
        and isinstance(item["package"].get("name"), str)
        and isinstance(item["package"].get("ecosystem"), str)
        for item in affected
    )


def _ghsa_aliases(payload: dict[str, Any]) -> list[str]:
    aliases = payload.get("aliases")
    if not isinstance(aliases, list):
        return []
    result: list[str] = []
    for alias in aliases:
        if isinstance(alias, str) and alias.startswith("GHSA-") and alias not in result:
            result.append(alias)
    return result
