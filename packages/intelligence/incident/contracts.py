from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from packages.sources.contracts import IngestEnvelope, SourceDefinition, SourceRole


class SignalItem(BaseModel):
    signal_id: str
    acquisition_run_id: str
    source_id: str
    source_role: SourceRole
    source_family: str
    upstream_source: str | None = None
    external_object_id: str
    external_revision: str | None = None
    published_at: datetime | None = None
    observed_at: datetime
    canonical_url: str | None = None
    content_hash: str
    title: str
    summary: str | None = None
    incident_type: str = "security-incident"
    entity_hints: dict[str, list[str]] = Field(default_factory=dict)
    anchors: dict[str, list[str]] = Field(default_factory=dict)
    unresolved_questions: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any]
    incident_candidate_id: str | None = None

    @property
    def independence_key(self) -> str:
        return self.upstream_source or self.source_family


class IncidentCandidate(BaseModel):
    candidate_id: str
    incident_type: str
    anchor_set: dict[str, list[str]] = Field(default_factory=dict)
    source_diversity: list[str] = Field(default_factory=list)
    independent_source_count: int = 0
    signal_ids: list[str] = Field(default_factory=list)
    watch_priority: int = 50
    next_poll_at: datetime | None = None
    last_material_change: datetime
    unresolved_questions: list[str] = Field(default_factory=list)
    promotion_state: str = "candidate"
    pinned: bool = False


class IncidentSignalResult(BaseModel):
    signal_id: str
    incident_candidate_id: str
    available_at: datetime
    material_change: bool
    source_role: SourceRole
    next_watch_at: datetime | None = None


class IncidentSignalExtractor(Protocol):
    def extract(
        self,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> SignalItem: ...


class IncidentSignalStore(Protocol):
    async def get_signal(self, signal_id: str) -> SignalItem | None: ...

    async def put_signal(self, signal: SignalItem, *, ttl_seconds: int) -> None: ...

    async def get_candidate(self, candidate_id: str) -> IncidentCandidate | None: ...

    async def put_candidate(self, candidate: IncidentCandidate, *, ttl_seconds: int) -> None: ...

    async def candidate_ids_for_anchor(self, anchor_type: str, value: str) -> set[str]: ...

    async def index_candidate_anchor(
        self,
        candidate_id: str,
        anchor_type: str,
        value: str,
        *,
        ttl_seconds: int,
    ) -> None: ...

    async def schedule_watch(self, candidate_id: str, next_poll_at: datetime) -> None: ...


class GenericNewsSignalExtractor:
    """Normalizer for adapters that already emit the incident signal schema."""

    def extract(
        self,
        source: SourceDefinition,
        envelope: IngestEnvelope,
    ) -> SignalItem:
        payload = envelope.json_payload
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("incident signal payload requires title")
        summary = payload.get("summary")
        if summary is not None and not isinstance(summary, str):
            raise ValueError("incident signal summary must be a string")
        upstream_source = payload.get("upstream_source")
        if upstream_source is not None and not isinstance(upstream_source, str):
            raise ValueError("upstream_source must be a string")
        incident_type = payload.get("incident_type", "security-incident")
        if not isinstance(incident_type, str):
            raise ValueError("incident_type must be a string")
        entity_hints = _string_list_map(payload.get("entity_hints", {}), "entity_hints")
        anchors = _string_list_map(payload.get("anchors", {}), "anchors")
        unresolved = payload.get("unresolved_questions", [])
        if not isinstance(unresolved, list) or not all(
            isinstance(item, str) for item in unresolved
        ):
            raise ValueError("unresolved_questions must be a list of strings")
        return SignalItem(
            signal_id=envelope.idempotency_key,
            acquisition_run_id=envelope.acquisition_run_id,
            source_id=envelope.source_id,
            source_role=source.source_role,
            source_family=source.source_family,
            upstream_source=upstream_source or source.upstream_source,
            external_object_id=envelope.external_object_id,
            external_revision=envelope.external_revision,
            published_at=envelope.published_at,
            observed_at=envelope.observed_at,
            canonical_url=envelope.canonical_url,
            content_hash=envelope.content_hash,
            title=title.strip(),
            summary=summary,
            incident_type=incident_type,
            entity_hints=entity_hints,
            anchors=anchors,
            unresolved_questions=list(unresolved),
            raw_payload=envelope.json_payload,
        )


def _string_list_map(value: Any, field: str) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    normalized: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(key, str) or not isinstance(items, list):
            raise ValueError(f"{field} must map strings to lists")
        values = [item.strip() for item in items if isinstance(item, str) and item.strip()]
        if values:
            normalized[key] = sorted(set(values))
    return normalized
