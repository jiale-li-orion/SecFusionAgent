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
from packages.sources.errors import (
    SourceAuthFailed,
    SourceFetchFailed,
    SourceRateLimited,
    SourceSchemaChanged,
)


class XUserSignalAdapter:
    DEFAULT_BASE_URL = "https://api.x.com/2"

    def __init__(self, client: httpx.AsyncClient, *, bearer_token: str | None) -> None:
        self._client = client
        self._bearer_token = bearer_token

    async def discover(self, source: SourceDefinition, state: SourceState) -> DiscoveryBatch:
        token = self._require_token()
        username = _username(source)
        base_url = str(source.discovery_method.get("base_url") or self.DEFAULT_BASE_URL).rstrip("/")
        user = await self._get_json(
            f"{base_url}/users/by/username/{username}",
            token,
            params={"user.fields": "id,username,name"},
        )
        user_data = user.get("data")
        if not isinstance(user_data, dict) or not isinstance(user_data.get("id"), str):
            raise SourceSchemaChanged("X user lookup returned no data.id")
        user_id = user_data["id"]
        max_results = _max_results(source)
        params = {
            "max_results": str(max_results),
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,entities",
        }
        since_id = state.cursor.get("since_id")
        if isinstance(since_id, str) and since_id:
            params["since_id"] = since_id
        timeline = await self._get_json(f"{base_url}/users/{user_id}/tweets", token, params=params)
        data = timeline.get("data", [])
        if data is None:
            data = []
        if not isinstance(data, list):
            raise SourceSchemaChanged("X timeline data is not a list")

        items: list[DiscoveredRef] = []
        ids: list[int] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            tweet_id = raw.get("id")
            text = raw.get("text")
            if not isinstance(tweet_id, str) or not isinstance(text, str):
                continue
            try:
                ids.append(int(tweet_id))
            except ValueError:
                pass
            created_at = _optional_datetime(raw.get("created_at"))
            canonical_url = f"https://x.com/{username}/status/{tweet_id}"
            payload = {
                "title": f"@{username}: {text[:180]}",
                "summary": text,
                "incident_type": "security-incident",
                "entity_hints": {},
                "anchors": {},
                "unresolved_questions": ["primary confirmation", "affected scope"],
                "event_type": "reported",
                "upstream_source": f"x.com/{username.lower()}",
                "x_user_id": user_id,
                "x_username": username,
                "tweet_id": tweet_id,
            }
            items.append(
                DiscoveredRef(
                    external_object_id=tweet_id,
                    canonical_url=canonical_url,
                    published_at=created_at,
                    updated_at=created_at,
                    external_revision=tweet_id,
                    locator={"username": username, "tweet_id": tweet_id},
                    inline_payload=payload,
                )
            )
        next_cursor = dict(state.cursor)
        if ids:
            next_cursor["since_id"] = str(max(ids))
        return DiscoveryBatch(items=items, next_cursor=next_cursor)

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope:
        if ref.inline_payload is None:
            raise SourceSchemaChanged("X discovered ref has no inline payload")
        return IngestEnvelope.for_json_payload(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source.source_id,
            external_object_id=ref.external_object_id,
            payload=ref.inline_payload,
            canonical_url=ref.canonical_url,
            published_at=ref.published_at,
            updated_at=ref.updated_at,
            external_revision=ref.external_revision,
            request_metadata={"provider": "x", **ref.locator},
        )

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]:
        del spec
        batch = await self.discover(source, SourceState())
        return [
            await self.fetch(
                source,
                ref,
                acquisition_run_id=acquisition_run_id,
                trigger=trigger,
            )
            for ref in batch.items
        ]

    def _require_token(self) -> str:
        if not self._bearer_token:
            raise SourceAuthFailed("X bearer token is required")
        return self._bearer_token

    async def _get_json(
        self,
        url: str,
        token: str,
        *,
        params: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = await self._client.get(
                url,
                params=params,
                follow_redirects=True,
                headers={"Authorization": f"Bearer {token}", "User-Agent": "SecFusionAgent/0.1"},
            )
        except httpx.HTTPError as exc:
            raise SourceFetchFailed(f"X API request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 429:
            raise SourceRateLimited("X API rate limit reached")
        if response.status_code in {401, 403}:
            raise SourceAuthFailed(
                f"X API authentication/access failed with HTTP {response.status_code}"
            )
        if response.is_error:
            raise SourceFetchFailed(f"X API returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceSchemaChanged("X API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceSchemaChanged("X API response root is not an object")
        return payload


def _username(source: SourceDefinition) -> str:
    value = source.discovery_method.get("username")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("X source requires discovery_method.username")
    return value.strip().lstrip("@")


def _max_results(source: SourceDefinition) -> int:
    value = source.discovery_method.get("max_results", 10)
    if isinstance(value, int) and not isinstance(value, bool):
        return max(5, min(100, value))
    return 10


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceSchemaChanged(f"invalid X created_at: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
