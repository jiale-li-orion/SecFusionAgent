from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import JsonValue

from packages.intelligence.hot_cache.contracts import (
    HotBugCache,
    HotBugRecord,
    HotNormalizationResult,
)
from packages.sources.contracts import IngestEnvelope, RetentionMode, SourceDefinition


class HotBugNormalizer(Protocol):
    def projection(self, envelope: IngestEnvelope) -> dict[str, JsonValue]: ...


class HotBugIngress:
    def __init__(
        self,
        cache: HotBugCache,
        normalizers: dict[str, HotBugNormalizer],
        *,
        ttl_seconds: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._cache = cache
        self._normalizers = normalizers
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def accept(
        self,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> HotNormalizationResult:
        if source.retention_mode is not RetentionMode.HOT_WINDOW:
            raise ValueError(f"source {source.source_id} is not configured for hot_window")
        if envelope.source_id != source.source_id:
            raise ValueError("envelope source_id does not match source definition")
        normalizer = self._normalizers.get(source.adapter_type)
        if normalizer is None:
            raise ValueError(f"no hot normalizer for adapter_type={source.adapter_type}")

        previous = await self._cache.get(source.source_id, envelope.external_object_id)
        projection = normalizer.projection(envelope)
        changed_fields = _changed_fields(
            previous.projection if previous is not None else None,
            projection,
        )
        priority_signals = _priority_signals(projection, previous is None, changed_fields)
        available_at = self._now()
        record = HotBugRecord(
            source_id=source.source_id,
            external_object_id=envelope.external_object_id,
            external_revision=envelope.external_revision,
            canonical_url=envelope.canonical_url,
            published_at=envelope.published_at,
            updated_at=envelope.updated_at,
            fetched_at=envelope.observed_at,
            content_hash=envelope.content_hash,
            projection=projection,
            changed_fields=changed_fields,
            priority_signals=priority_signals,
        )
        await self._cache.admit(record, ttl_seconds=self._ttl_seconds)
        return HotNormalizationResult(
            source_id=record.source_id,
            external_object_id=record.external_object_id,
            external_revision=record.external_revision,
            available_at=available_at,
            changed_fields=changed_fields,
            current_projection_ref=record.cache_key,
            priority_signals=priority_signals,
        )


def _changed_fields(
    previous: dict[str, JsonValue] | None,
    current: dict[str, JsonValue],
) -> list[str]:
    if previous is None:
        return sorted(current)
    keys = set(previous) | set(current)
    return sorted(key for key in keys if previous.get(key) != current.get(key))


def _priority_signals(
    projection: dict[str, JsonValue],
    is_new: bool,
    changed_fields: list[str],
) -> list[str]:
    signals: list[str] = []
    if is_new:
        signals.append("new_record")
    elif changed_fields:
        signals.append("material_update")
    score = projection.get("cvss_score")
    if isinstance(score, (int, float)) and score >= 9.0:
        signals.append("critical_severity")
    if projection.get("known_exploited") is True:
        signals.append("known_exploited")
    return signals
