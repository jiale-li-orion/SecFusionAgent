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


class RedHatCSAFVEXAdapter:
    DEFAULT_BASE_URL = "https://security.access.redhat.com/data/csaf/v2/vex"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("Red Hat CSAF VEX is configured for exact CVE query")

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
            raise SourceFetchFailed(
                f"Red Hat CSAF VEX record unavailable: {ref.external_object_id}"
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
        if not isinstance(cve_id, str) or not cve_id.upper().startswith("CVE-"):
            raise ValueError("Red Hat CSAF VEX query requires filters.cve_id")
        cve_id = cve_id.upper()
        parts = cve_id.split("-")
        if len(parts) < 3 or not parts[1].isdigit():
            raise ValueError("invalid CVE id")
        base = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        url = f"{base}/{parts[1]}/{cve_id.lower()}.json"
        try:
            response = await self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"Red Hat CSAF VEX request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 404:
            return []
        if response.status_code == 429:
            raise SourceRateLimited("Red Hat CSAF VEX rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"Red Hat CSAF VEX returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("Red Hat CSAF VEX response is not JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("Red Hat CSAF VEX root is not an object")
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list) or not any(
            isinstance(item, dict) and item.get("cve") == cve_id for item in vulnerabilities
        ):
            raise SourceSchemaChanged("Red Hat CSAF VEX record does not contain requested CVE")
        revision = _tracking_release_date(payload)
        return [
            IngestEnvelope.for_json_payload(
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                source_id=source.source_id,
                external_object_id=cve_id,
                payload=payload,
                canonical_url=url,
                published_at=None,
                updated_at=_parse_datetime(revision),
                external_revision=revision,
                request_metadata={"provider": "redhat", "format": "csaf_vex"},
            )
        ]


def _tracking_release_date(payload: dict[str, Any]) -> str | None:
    document = payload.get("document")
    tracking = document.get("tracking") if isinstance(document, dict) else None
    if not isinstance(tracking, dict):
        return None
    value = tracking.get("current_release_date")
    return value if isinstance(value, str) else None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
