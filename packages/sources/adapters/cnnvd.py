from __future__ import annotations

import secrets
import string
import time
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


class CNNVDAdapter:
    """CNNVD public frontend API using the site's published tourist-sign flow."""

    DEFAULT_ORIGIN = "https://www.cnnvd.org.cn"
    DEFAULT_BASE_PATH = "/cnnvdweb"
    DEFAULT_APP_ID = "6i8417579268034679HXvp0Kb6r1C2A9"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        del source, state
        raise ValueError("CNNVD source is on-demand until provider access is validated")

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        del source, ref, acquisition_run_id, trigger
        raise ValueError("CNNVD source uses query()")

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        cve_id = spec.filters.get("cve_id")
        cnnvd_id = spec.filters.get("cnnvd_id")
        page_size = _positive_int(spec.filters.get("page_size"), 10)
        if isinstance(cve_id, str) and cve_id.strip():
            payload = {
                "keyword": cve_id.strip(),
                "page": 1,
                "pageSize": page_size,
                "sortField": "publishDate",
                "sortOrder": "desc",
            }
            response = await self._signed_post(source, "/homePage/searchVul", payload)
            records = _records(response)
            query_meta = {"operation": "searchVul", "cve_id": cve_id.strip()}
        elif isinstance(cnnvd_id, str) and cnnvd_id.strip():
            payload = {"cnnvdCode": cnnvd_id.strip()}
            response = await self._signed_post(
                source,
                "/homePage/searchVulByCnnvdCode",
                payload,
            )
            data = response.get("data")
            if isinstance(data, dict) and isinstance(data.get("records"), list):
                records = [item for item in data["records"] if isinstance(item, dict)]
            elif isinstance(data, dict):
                records = [data]
            elif isinstance(data, list):
                records = [item for item in data if isinstance(item, dict)]
            else:
                records = []
            query_meta = {"operation": "searchVulByCnnvdCode", "cnnvd_id": cnnvd_id.strip()}
        else:
            raise ValueError("CNNVD query requires filters.cve_id or filters.cnnvd_id")

        observed_at = datetime.now(UTC)
        return [
            _record_envelope(
                source,
                record,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
                observed_at=observed_at,
                query_meta=query_meta,
            )
            for record in records
        ]

    async def _signed_post(
        self,
        source: SourceDefinition,
        api_path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        origin = str(source.discovery_method.get("origin") or self.DEFAULT_ORIGIN).rstrip("/")
        base_path = str(source.discovery_method.get("base_path") or self.DEFAULT_BASE_PATH)
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        base_path = base_path.rstrip("/")
        app_id = str(source.discovery_method.get("app_id") or self.DEFAULT_APP_ID)
        timestamp = str(int(time.time() * 1000))
        alphabet = string.ascii_letters + string.digits
        nonce = "".join(secrets.choice(alphabet) for _ in range(32))
        signed_path = base_path + api_path
        sign_string = f"POST{signed_path}{timestamp}{nonce}"
        headers = {
            "X-Appid": app_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "SecFusionAgent/0.1 cnnvd-source-adapter",
        }
        sign_response = await self._post_json(
            origin + base_path + "/tourist/sign",
            {"signStr": sign_string},
            headers,
        )
        if sign_response.get("code") != 200 or not isinstance(sign_response.get("data"), str):
            message = sign_response.get("message") or sign_response.get("msg") or "unknown"
            raise SourceFetchFailed(
                f"CNNVD provider access denied during tourist sign: "
                f"code={sign_response.get('code')} message={message}"
            )
        headers["X-Sign"] = sign_response["data"]
        result = await self._post_json(origin + signed_path, payload, headers)
        if result.get("code") != 200:
            message = result.get("message") or result.get("msg") or "unknown"
            raise SourceFetchFailed(
                f"CNNVD API rejected request: code={result.get('code')} message={message}"
            )
        return result

    async def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = await self._client.post(
                url,
                json=payload,
                headers=headers,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"CNNVD request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("CNNVD rate limit reached")
        if response.is_error:
            raise SourceFetchFailed(f"CNNVD returned HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("CNNVD returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise SourceSchemaChanged("CNNVD response root is not an object")
        return data


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SourceSchemaChanged("CNNVD search response data is not an object")
    records = data.get("records")
    if not isinstance(records, list):
        raise SourceSchemaChanged("CNNVD search response has no records list")
    return [item for item in records if isinstance(item, dict)]


def _record_envelope(
    source: SourceDefinition,
    record: dict[str, Any],
    *,
    acquisition_run_id: str,
    trigger: AcquisitionTrigger,
    observed_at: datetime,
    query_meta: dict[str, str],
) -> IngestEnvelope:
    cnnvd_id = record.get("cnnvdId") or record.get("cnnvdCode")
    internal_id = record.get("id")
    if isinstance(cnnvd_id, str) and cnnvd_id:
        external_id = cnnvd_id
    elif isinstance(internal_id, (str, int)) and not isinstance(internal_id, bool):
        external_id = f"cnnvd-internal:{internal_id}"
    else:
        raise SourceSchemaChanged("CNNVD record has no cnnvd id/internal id")
    updated = _optional_date(record.get("updateTime") or record.get("updateDate"))
    published = _optional_date(record.get("publishDate") or record.get("publishTime"))
    canonical = (
        f"https://www.cnnvd.org.cn/frontend/detail?vulId={internal_id}"
        if isinstance(internal_id, (str, int)) and not isinstance(internal_id, bool)
        else "https://www.cnnvd.org.cn/frontend/loophole"
    )
    return IngestEnvelope.for_json_payload(
        acquisition_run_id=acquisition_run_id,
        trigger=trigger,
        source_id=source.source_id,
        external_object_id=external_id,
        payload=record,
        canonical_url=canonical,
        published_at=published,
        updated_at=updated,
        external_revision=updated.isoformat() if updated else None,
        request_metadata={"provider": "cnnvd", **query_meta},
        observed_at=observed_at,
    )


def _optional_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for candidate in (raw, raw.replace("/", "-")):
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return min(value, 100)
    return default
