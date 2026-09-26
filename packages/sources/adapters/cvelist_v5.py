from __future__ import annotations

import re
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

_CVE_RE = re.compile(r"^CVE-(\d{4})-(\d{4,})$")


class CVEListV5Adapter:
    DEFAULT_DELTA_LOG_URL = (
        "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/deltaLog.json"
    )
    DEFAULT_RAW_ROOT = "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        delta_log_url = str(
            source.discovery_method.get("delta_log_url") or self.DEFAULT_DELTA_LOG_URL
        )
        payload = await self._get_json(delta_log_url)
        if not isinstance(payload, list):
            raise SourceSchemaChanged("cvelistV5 deltaLog root is not a list")

        cursor_value = state.cursor.get("last_fetch_time")
        cursor = _parse_datetime(cursor_value) if isinstance(cursor_value, str) else None
        entries: list[tuple[datetime, dict[str, Any]]] = []
        for item in payload:
            if not isinstance(item, dict):
                raise SourceSchemaChanged("cvelistV5 deltaLog contains a non-object entry")
            fetch_time = item.get("fetchTime")
            if not isinstance(fetch_time, str):
                raise SourceSchemaChanged("cvelistV5 delta entry has no fetchTime")
            parsed = _parse_datetime(fetch_time)
            if cursor is None or parsed > cursor:
                entries.append((parsed, item))

        if cursor is None and entries:
            initial_entries = _positive_int(
                source.discovery_method.get("initial_entries"),
                default=1,
            )
            entries = entries[-initial_entries:]

        latest_by_cve: dict[str, DiscoveredRef] = {}
        for _, entry in entries:
            for bucket in ("new", "updated"):
                changes = entry.get(bucket, [])
                if not isinstance(changes, list):
                    raise SourceSchemaChanged(f"cvelistV5 delta {bucket} is not a list")
                for change in changes:
                    ref = _change_ref(change)
                    previous = latest_by_cve.get(ref.external_object_id)
                    if previous is None or _ref_updated(ref) >= _ref_updated(previous):
                        latest_by_cve[ref.external_object_id] = ref

        latest_fetch = max((item[0] for item in entries), default=cursor)
        if latest_fetch is None and payload:
            tail = payload[-1]
            if isinstance(tail, dict) and isinstance(tail.get("fetchTime"), str):
                latest_fetch = _parse_datetime(tail["fetchTime"])
        next_cursor = dict(state.cursor)
        if latest_fetch is not None:
            next_cursor["last_fetch_time"] = latest_fetch.isoformat()
        return DiscoveryBatch(
            items=sorted(latest_by_cve.values(), key=lambda item: item.external_object_id),
            next_cursor=next_cursor,
        )

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        url = ref.canonical_url or _raw_url(source, ref.external_object_id)
        payload = await self._get_json(url)
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("cvelistV5 CVE record root is not an object")
        return _record_envelope(
            source,
            payload,
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            canonical_url=url,
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
        if not isinstance(cve_id, str) or not _CVE_RE.fullmatch(cve_id):
            raise ValueError("cvelistV5 query requires filters.cve_id")
        ref = DiscoveredRef(
            external_object_id=cve_id,
            canonical_url=_raw_url(source, cve_id),
        )
        return [
            await self.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
        ]

    async def _get_json(self, url: str) -> Any:
        try:
            response = await self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"cvelistV5 request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("cvelistV5 rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"cvelistV5 returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("cvelistV5 response is not valid JSON") from exc


def _change_ref(value: Any) -> DiscoveredRef:
    if not isinstance(value, dict):
        raise SourceSchemaChanged("cvelistV5 change is not an object")
    cve_id = value.get("cveId")
    github_link = value.get("githubLink")
    updated_raw = value.get("dateUpdated")
    if not isinstance(cve_id, str) or not _CVE_RE.fullmatch(cve_id):
        raise SourceSchemaChanged("cvelistV5 change has invalid cveId")
    if not isinstance(github_link, str) or not github_link.startswith("https://"):
        raise SourceSchemaChanged("cvelistV5 change has invalid githubLink")
    updated = _parse_datetime(updated_raw) if isinstance(updated_raw, str) else None
    return DiscoveredRef(
        external_object_id=cve_id,
        canonical_url=github_link,
        updated_at=updated,
        external_revision=updated.isoformat() if updated else None,
        locator={"cve_id": cve_id, "cve_org_link": value.get("cveOrgLink")},
    )


def _record_envelope(
    source: SourceDefinition,
    payload: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
    canonical_url: str,
) -> IngestEnvelope:
    metadata = payload.get("cveMetadata")
    if not isinstance(metadata, dict):
        raise SourceSchemaChanged("cvelistV5 record has no cveMetadata")
    cve_id = metadata.get("cveId")
    if not isinstance(cve_id, str) or not _CVE_RE.fullmatch(cve_id):
        raise SourceSchemaChanged("cvelistV5 record has invalid cveMetadata.cveId")
    published = _optional_datetime(metadata.get("datePublished"))
    updated = _optional_datetime(metadata.get("dateUpdated"))
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=cve_id,
        payload=payload,
        canonical_url=canonical_url,
        published_at=published,
        updated_at=updated,
        external_revision=updated.isoformat() if updated else None,
        request_metadata={"provider": "cve-program", "format": payload.get("dataVersion")},
    )


def _raw_url(source: SourceDefinition, cve_id: str) -> str:
    match = _CVE_RE.fullmatch(cve_id)
    if match is None:
        raise ValueError(f"invalid CVE id: {cve_id}")
    year, number = match.groups()
    prefix = number[:-3] or "0"
    root = str(source.discovery_method.get("raw_root") or CVEListV5Adapter.DEFAULT_RAW_ROOT)
    return f"{root.rstrip('/')}/{year}/{prefix}xxx/{cve_id}.json"


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SourceSchemaChanged("cvelistV5 timestamp is not a string")
    return _parse_datetime(value)


def _ref_updated(ref: DiscoveredRef) -> datetime:
    return ref.updated_at or datetime.min.replace(tzinfo=UTC)


def _positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return default
