from __future__ import annotations

from datetime import datetime
from typing import Any

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
from packages.sources.errors import (
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class GitHubRepoAdapter:
    DEFAULT_API_URL = "https://api.github.com"

    def __init__(self, client: httpx.AsyncClient, *, token: str | None = None) -> None:
        self._client = client
        self._token = token

    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch:
        repos = _repo_list(source.discovery_method.get("repos"))
        previous = state.cursor.get("repo_revisions")
        previous_revisions = previous if isinstance(previous, dict) else {}
        next_revisions: dict[str, JsonValue] = {}
        items: list[DiscoveredRef] = []
        for full_name in repos:
            payload = await self._get_repo(source, full_name)
            ref = _to_ref(payload)
            revision = ref.external_revision or ""
            next_revisions[full_name] = revision
            if previous_revisions.get(full_name) != revision:
                items.append(ref)
        return DiscoveryBatch(
            items=items,
            next_cursor={"repo_revisions": next_revisions},
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        payload = ref.inline_payload
        if payload is None:
            payload = await self._get_repo(source, ref.external_object_id)
        return _to_envelope(
            source,
            payload,
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
        full_name = spec.filters.get("repo_full_name")
        if not isinstance(full_name, str) or not full_name:
            raise ValueError("GitHub repo query requires filters.repo_full_name")
        payload = await self._get_repo(source, full_name)
        return [
            _to_envelope(
                source,
                payload,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
        ]

    async def _get_repo(
        self,
        source: SourceDefinition,
        full_name: str,
    ) -> dict[str, Any]:
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_API_URL).rstrip("/")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            response = await self._client.get(f"{base_url}/repos/{full_name}", headers=headers)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"GitHub repo request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 401:
            raise SourceAuthFailed("GitHub repo API rejected credentials")
        if response.status_code in {403, 429}:
            raise SourceRateLimited("GitHub repo API rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"GitHub repo API returned HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("GitHub repo response root is not an object")
        return payload


def _to_ref(payload: dict[str, Any]) -> DiscoveredRef:
    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or not full_name:
        raise SourceSchemaChanged("GitHub repo response has no full_name")
    updated = _optional_datetime(payload.get("updated_at"))
    pushed = _optional_datetime(payload.get("pushed_at"))
    revision = f"updated={_iso(updated)};pushed={_iso(pushed)}"
    html_url = payload.get("html_url")
    return DiscoveredRef(
        external_object_id=full_name,
        canonical_url=html_url if isinstance(html_url, str) else f"https://github.com/{full_name}",
        updated_at=max(item for item in [updated, pushed] if item is not None)
        if updated is not None or pushed is not None
        else None,
        external_revision=revision,
        locator={"repo_full_name": full_name},
        inline_payload=payload,
    )


def _to_envelope(
    source: SourceDefinition,
    payload: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
) -> IngestEnvelope:
    ref = _to_ref(payload)
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=ref.external_object_id,
        payload=payload,
        canonical_url=ref.canonical_url,
        published_at=_optional_datetime(payload.get("created_at")),
        updated_at=ref.updated_at,
        external_revision=ref.external_revision,
        request_metadata={"provider": "github", "object_type": "repository"},
    )


def _repo_list(value: JsonValue | None) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("GitHub repo source requires discovery_method.repos")
    repos = [item for item in value if isinstance(item, str) and item]
    if not repos:
        raise ValueError("GitHub repo source has no configured repos")
    return repos


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceSchemaChanged("GitHub repo timestamp is not a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "none"
