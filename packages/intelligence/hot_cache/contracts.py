from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field, JsonValue


class HotBugRecord(BaseModel):
    acquisition_run_id: str
    source_id: str
    external_object_id: str
    external_revision: str | None = None
    canonical_url: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    fetched_at: datetime
    content_hash: str
    raw_payload: dict[str, Any]
    projection: dict[str, JsonValue]
    changed_fields: list[str] = Field(default_factory=list)
    priority_signals: list[str] = Field(default_factory=list)

    @property
    def cache_key(self) -> str:
        return f"bug:{self.source_id}:{self.external_object_id}"


class HotNormalizationResult(BaseModel):
    source_id: str
    external_object_id: str
    external_revision: str | None
    available_at: datetime
    changed_fields: list[str]
    current_projection_ref: str
    priority_signals: list[str]


class HotBugCache(Protocol):
    async def get(self, source_id: str, external_object_id: str) -> HotBugRecord | None: ...

    async def admit(self, record: HotBugRecord, *, ttl_seconds: int) -> None: ...

    async def touch(self, source_id: str, external_object_id: str) -> None: ...

    async def pin(self, source_id: str, external_object_id: str) -> None: ...

    async def unpin(self, source_id: str, external_object_id: str) -> None: ...

    async def evict(self, source_id: str, external_object_id: str) -> None: ...
