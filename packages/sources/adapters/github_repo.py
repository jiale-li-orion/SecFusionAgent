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
            payload = await self._get_json(source, f"/repos/{full_name}")
            if not isinstance(payload, dict):
                raise SourceSchemaChanged("GitHub repo response root is not an object")
            ref = _to_repo_ref(payload)
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
            loaded = await self._get_json(source, f"/repos/{ref.external_object_id}")
            if not isinstance(loaded, dict):
                raise SourceSchemaChanged("GitHub repo response root is not an object")
            payload = loaded
        return _to_repo_envelope(
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
        object_type = spec.filters.get("object_type", "repository")
        if not isinstance(object_type, str):
            raise ValueError("GitHub repo query filters.object_type must be a string")

        if object_type == "repository":
            payload = await self._get_json(source, f"/repos/{full_name}")
            if not isinstance(payload, dict):
                raise SourceSchemaChanged("GitHub repo response root is not an object")
            return [
                _to_repo_envelope(
                    source,
                    payload,
                    acquisition_run_id=acquisition_run_id,
                    trigger=trigger,
                )
            ]

        if object_type == "issue":
            number = _required_int(spec, "issue_number")
            payload = await self._get_json(source, f"/repos/{full_name}/issues/{number}")
            return [
                self._typed_envelope(
                    source, full_name, "issue", payload, acquisition_run_id, trigger
                )
            ]

        if object_type == "pull_request":
            number = _required_int(spec, "pull_number")
            payload = await self._get_json(source, f"/repos/{full_name}/pulls/{number}")
            return [
                self._typed_envelope(
                    source, full_name, "pull_request", payload, acquisition_run_id, trigger
                )
            ]

        if object_type == "commit":
            sha = _required_str(spec, "commit_sha")
            payload = await self._get_json(source, f"/repos/{full_name}/commits/{sha}")
            return [
                self._typed_envelope(
                    source, full_name, "commit", payload, acquisition_run_id, trigger
                )
            ]

        if object_type == "release":
            tag = spec.filters.get("tag")
            release_id = spec.filters.get("release_id")
            if isinstance(tag, str) and tag:
                path = f"/repos/{full_name}/releases/tags/{tag}"
            elif isinstance(release_id, int):
                path = f"/repos/{full_name}/releases/{release_id}"
            else:
                raise ValueError("GitHub release query requires filters.tag or filters.release_id")
            payload = await self._get_json(source, path)
            return [
                self._typed_envelope(
                    source, full_name, "release", payload, acquisition_run_id, trigger
                )
            ]

        if object_type == "releases":
            limit = spec.filters.get("limit", 20)
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                raise ValueError(
                    "GitHub releases query filters.limit must be an integer in [1, 100]"
                )
            payload = await self._get_json(
                source,
                f"/repos/{full_name}/releases",
                params={"per_page": str(limit)},
            )
            if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
                raise SourceSchemaChanged("GitHub releases response root is not a list of objects")
            return [
                self._typed_envelope(
                    source, full_name, "release", item, acquisition_run_id, trigger
                )
                for item in payload
            ]

        raise ValueError(f"unsupported GitHub repository object_type={object_type!r}")

    def _typed_envelope(
        self,
        source: SourceDefinition,
        full_name: str,
        object_type: str,
        payload: object,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if not isinstance(payload, dict):
            raise SourceSchemaChanged(f"GitHub {object_type} response root is not an object")
        return _to_development_envelope(
            source,
            full_name,
            object_type,
            payload,
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
        )

    async def _get_json(
        self,
        source: SourceDefinition,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> object:
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_API_URL).rstrip("/")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            response = await self._client.get(f"{base_url}{path}", headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(
                f"GitHub repository request failed: {exc.__class__.__name__}"
            ) from exc
        if response.status_code == 401:
            raise SourceAuthFailed("GitHub repository API rejected credentials")
        if response.status_code in {403, 429}:
            raise SourceRateLimited("GitHub repository API rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"GitHub repository API returned HTTP {response.status_code}")
        return response.json()


def _to_repo_ref(payload: dict[str, Any]) -> DiscoveredRef:
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


def _to_repo_envelope(
    source: SourceDefinition,
    payload: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
) -> IngestEnvelope:
    ref = _to_repo_ref(payload)
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
        request_metadata={
            "provider": "github",
            "object_type": "repository",
            "repo_full_name": ref.external_object_id,
        },
    )


def _to_development_envelope(
    source: SourceDefinition,
    full_name: str,
    object_type: str,
    payload: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
) -> IngestEnvelope:
    external_object_id = _development_external_id(full_name, object_type, payload)
    canonical_url = payload.get("html_url")
    updated_at = _optional_datetime(payload.get("updated_at"))
    published_at = _development_published_at(object_type, payload)
    revision = _development_revision(object_type, payload, updated_at, published_at)
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=external_object_id,
        payload=payload,
        canonical_url=canonical_url if isinstance(canonical_url, str) else None,
        published_at=published_at,
        updated_at=updated_at,
        external_revision=revision,
        request_metadata={
            "provider": "github",
            "object_type": object_type,
            "repo_full_name": full_name,
        },
    )


def _development_external_id(full_name: str, object_type: str, payload: dict[str, Any]) -> str:
    if object_type in {"issue", "pull_request"}:
        number = payload.get("number")
        if not isinstance(number, int):
            raise SourceSchemaChanged(f"GitHub {object_type} response has no numeric number")
        marker = "issue" if object_type == "issue" else "pull"
        return f"{full_name}#{marker}-{number}"
    if object_type == "commit":
        sha = payload.get("sha")
        if not isinstance(sha, str) or not sha:
            raise SourceSchemaChanged("GitHub commit response has no sha")
        return f"{full_name}@{sha}"
    if object_type == "release":
        release_id = payload.get("id")
        if not isinstance(release_id, int):
            raise SourceSchemaChanged("GitHub release response has no numeric id")
        return f"{full_name}@release-{release_id}"
    raise ValueError(f"unsupported development object_type={object_type!r}")


def _development_published_at(object_type: str, payload: dict[str, Any]) -> datetime | None:
    if object_type == "commit":
        commit = payload.get("commit")
        if isinstance(commit, dict):
            committer = commit.get("committer")
            if isinstance(committer, dict):
                date = committer.get("date")
                if date is not None:
                    return _optional_datetime(date)
    for field in ("published_at", "created_at"):
        value = payload.get(field)
        if value is not None:
            return _optional_datetime(value)
    return None


def _development_revision(
    object_type: str,
    payload: dict[str, Any],
    updated_at: datetime | None,
    published_at: datetime | None,
) -> str | None:
    if object_type == "commit":
        sha = payload.get("sha")
        return sha if isinstance(sha, str) and sha else None
    if updated_at is not None:
        return updated_at.isoformat()
    if published_at is not None:
        return published_at.isoformat()
    node_id = payload.get("node_id")
    return node_id if isinstance(node_id, str) and node_id else None


def _required_str(spec: QuerySpec, field: str) -> str:
    value = spec.filters.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"GitHub repository query requires filters.{field}")
    return value


def _required_int(spec: QuerySpec, field: str) -> int:
    value = spec.filters.get(field)
    if not isinstance(value, int):
        raise ValueError(f"GitHub repository query requires integer filters.{field}")
    return value


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
        raise SourceSchemaChanged("GitHub timestamp is not a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "none"
