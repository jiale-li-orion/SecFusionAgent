from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class EmbeddingBatch(BaseModel):
    model: str
    version: str
    dimensions: int
    vectors: list[list[float]] = Field(default_factory=list)


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingBatch: ...


class CandidateKind(StrEnum):
    OBJECT = "object"
    PROJECTION = "projection"
    DOCUMENT_CHUNK = "document_chunk"
    RELATION = "relation"
    EVIDENCE = "evidence"


class RetrievedCandidate(BaseModel):
    candidate_id: str
    candidate_kind: CandidateKind
    object_id: str | None = None
    relation_id: str | None = None
    evidence_ref: str | None = None
    document_chunk_id: str | None = None
    source_id: str | None = None
    source_role: str | None = None
    source_family: str | None = None
    upstream_source: str | None = None
    revision: str | int | None = None
    observed_at: datetime | None = None
    valid_time: datetime | None = None
    score_channels: dict[str, float] = Field(default_factory=dict)
    locator: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


class RetrievalAvailability(BaseModel):
    operator: str
    available: bool
    reason: str | None = None
