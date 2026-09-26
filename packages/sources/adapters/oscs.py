from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

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


class OSCSAdapter:
    DEFAULT_BASE_URL = "https://www.oscs1024.com"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        del source, state
        raise ValueError("OSCS source is on-demand only")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("OSCS source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        keyword = spec.filters.get("keyword")
        project_id = spec.filters.get("project_id")
        if isinstance(keyword, str) and keyword.strip():
            path = f"/oscs_api/v2/project/search?keyword={quote(keyword.strip())}"
            payload = await self._get_json(base_url + path)
            data = _data(payload)
            if not isinstance(data, list):
                raise SourceSchemaChanged("OSCS project search data is not a list")
            observed_at = datetime.now(UTC)
            return [
                _envelope(
                    source,
                    acquisition_run_id=acquisition_run_id,
                    trigger=trigger,
                    external_object_id=_project_external_id(item),
                    payload=item,
                    canonical_url=f"{base_url}/?search={quote(keyword.strip())}",
                    observed_at=observed_at,
                    query_metadata={"operation": "project_search", "keyword": keyword.strip()},
                )
                for item in data
                if isinstance(item, dict)
            ]
        if isinstance(project_id, str) and project_id.strip():
            path = f"/oscs_api/v2/detail/project/info?project_id={quote(project_id.strip())}"
            payload = await self._get_json(base_url + path)
            data = _data(payload)
            if not isinstance(data, dict):
                raise SourceSchemaChanged("OSCS project info data is not an object")
            observed_at = datetime.now(UTC)
            return [
                _envelope(
                    source,
                    acquisition_run_id=acquisition_run_id,
                    trigger=trigger,
                    external_object_id=f"project:{project_id.strip()}",
                    payload=data,
                    canonical_url=f"{base_url}/project/{project_id.strip()}",
                    observed_at=observed_at,
                    query_metadata={"operation": "project_info", "project_id": project_id.strip()},
                )
            ]
        raise ValueError("OSCS query requires filters.keyword or filters.project_id")

    async def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = await self._client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": "SecFusionAgent/0.1 oscs-source-adapter"},
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"OSCS request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("OSCS rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"OSCS returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("OSCS returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("OSCS response root is not an object")
        if payload.get("code") != 200 or payload.get("success") is not True:
            raise SourceFetchFailed(
                f"OSCS API rejected request: code={payload.get('code')} info={payload.get('info')}"
            )
        return payload


def _data(payload: dict[str, Any]) -> Any:
    return payload.get("data")


def _project_external_id(item: dict[str, Any]) -> str:
    project_id = item.get("project_id")
    name = item.get("project_name")
    if isinstance(project_id, str) and project_id and project_id != "0":
        return f"project:{project_id}"
    if isinstance(name, str) and name:
        return f"repo:{name}"
    raise SourceSchemaChanged("OSCS project result has no stable id/name")


def _envelope(
    source: SourceDefinition,
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
    external_object_id: str,
    payload: dict[str, Any],
    canonical_url: str,
    observed_at: datetime,
    query_metadata: dict[str, str],
) -> IngestEnvelope:
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=external_object_id,
        payload=payload,
        canonical_url=canonical_url,
        published_at=None,
        updated_at=None,
        external_revision=None,
        request_metadata={"provider": "oscs", **query_metadata},
        observed_at=observed_at,
    )
