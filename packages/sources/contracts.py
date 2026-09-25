from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class SourceRole(StrEnum):
    SIGNAL = "signal"
    TELEMETRY = "telemetry"
    PRIMARY = "primary"
    FORENSIC = "forensic"
    AUTHORITY = "authority"
    REFERENCE = "reference"


class RetentionMode(StrEnum):
    HOT_WINDOW = "hot_window"
    INCIDENT_SIGNAL = "incident_signal"
    SELECTIVE_INDEX = "selective_index"
    DURABLE_MANAGED = "durable_managed"
    TIME_BOUNDED = "time_bounded"


class AcquisitionTrigger(StrEnum):
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    INVESTIGATION = "investigation"
    REPLAY = "replay"
    PROMOTION = "promotion"


class SourceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    adapter_type: str
    source_class: str
    authority_scope: list[str] = Field(default_factory=list)
    source_role: SourceRole
    source_family: str
    upstream_source: str | None = None
    access_mode: str
    update_semantics: str
    discovery_method: dict[str, JsonValue] = Field(default_factory=dict)
    time_semantics: dict[str, JsonValue] = Field(default_factory=dict)
    identity_semantics: dict[str, JsonValue] = Field(default_factory=dict)
    auth_ref: str | None = None
    rate_limit_policy: dict[str, JsonValue] = Field(default_factory=dict)
    access_rights: dict[str, JsonValue] = Field(default_factory=dict)
    retention_mode: RetentionMode
    schedule_policy: dict[str, JsonValue] = Field(default_factory=dict)
    schema_version: str = "1"


class SourceState(BaseModel):
    cursor: dict[str, JsonValue] = Field(default_factory=dict)
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_change_at: datetime | None = None
    next_due_at: datetime | None = None
    consecutive_failures: int = 0
    backoff_until: datetime | None = None
    rate_limit_state: dict[str, JsonValue] = Field(default_factory=dict)


class DiscoveredRef(BaseModel):
    external_object_id: str
    canonical_url: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    external_revision: str | None = None
    locator: dict[str, JsonValue] = Field(default_factory=dict)
    inline_payload: dict[str, Any] | None = None


class DiscoveryBatch(BaseModel):
    items: list[DiscoveredRef]
    next_cursor: dict[str, JsonValue]


class QuerySpec(BaseModel):
    filters: dict[str, JsonValue] = Field(default_factory=dict)


class IngestEnvelope(BaseModel):
    acquisition_run_id: str
    trigger: AcquisitionTrigger
    source_id: str
    external_object_id: str
    canonical_url: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    external_revision: str | None = None
    media_type: str = "application/json"
    payload: dict[str, Any] | None = None
    body: bytes | None = None
    content_hash: str
    request_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    idempotency_key: str

    @model_validator(mode="after")
    def validate_content(self) -> IngestEnvelope:
        if (self.payload is None) == (self.body is None):
            raise ValueError("IngestEnvelope requires exactly one of payload or body")
        return self

    @property
    def json_payload(self) -> dict[str, Any]:
        if self.payload is None:
            raise ValueError(f"{self.media_type} envelope has no JSON payload")
        return self.payload

    def content_bytes(self) -> bytes:
        if self.body is not None:
            return self.body
        return self._canonical_payload(self.json_payload)

    @classmethod
    def for_json_payload(
        cls,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
        source_id: str,
        external_object_id: str,
        payload: dict[str, Any],
        canonical_url: str | None,
        published_at: datetime | None,
        updated_at: datetime | None,
        external_revision: str | None,
        request_metadata: dict[str, JsonValue] | None = None,
        observed_at: datetime | None = None,
    ) -> IngestEnvelope:
        canonical = cls._canonical_payload(payload)
        content_hash = sha256(canonical).hexdigest()
        identity = external_revision or content_hash
        idem = sha256(f"{source_id}:{external_object_id}:{identity}".encode()).hexdigest()
        return cls(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source_id,
            external_object_id=external_object_id,
            canonical_url=canonical_url,
            published_at=published_at,
            updated_at=updated_at,
            observed_at=observed_at or datetime.now(UTC),
            external_revision=external_revision,
            payload=payload,
            content_hash=content_hash,
            request_metadata=request_metadata or {},
            idempotency_key=idem,
        )

    @classmethod
    def for_binary_payload(
        cls,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
        source_id: str,
        external_object_id: str,
        body: bytes,
        media_type: str,
        canonical_url: str | None,
        published_at: datetime | None,
        updated_at: datetime | None,
        external_revision: str | None,
        request_metadata: dict[str, JsonValue] | None = None,
        observed_at: datetime | None = None,
    ) -> IngestEnvelope:
        content_hash = sha256(body).hexdigest()
        identity = external_revision or content_hash
        idem = sha256(f"{source_id}:{external_object_id}:{identity}".encode()).hexdigest()
        return cls(
            acquisition_run_id=acquisition_run_id,
            trigger=trigger,
            source_id=source_id,
            external_object_id=external_object_id,
            canonical_url=canonical_url,
            published_at=published_at,
            updated_at=updated_at,
            observed_at=observed_at or datetime.now(UTC),
            external_revision=external_revision,
            media_type=media_type,
            body=body,
            content_hash=content_hash,
            request_metadata=request_metadata or {},
            idempotency_key=idem,
        )

    @staticmethod
    def _canonical_payload(payload: dict[str, Any]) -> bytes:
        import json

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")


class SourceAdapter(Protocol):
    async def discover(
        self,
        source: SourceDefinition,
        state: SourceState,
    ) -> DiscoveryBatch: ...

    async def fetch(
        self,
        source: SourceDefinition,
        ref: DiscoveredRef,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> IngestEnvelope: ...

    async def query(
        self,
        source: SourceDefinition,
        spec: QuerySpec,
        *,
        acquisition_run_id: str,
        trigger: AcquisitionTrigger,
    ) -> list[IngestEnvelope]: ...
