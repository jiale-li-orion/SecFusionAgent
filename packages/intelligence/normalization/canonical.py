from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.ingestion.evidence import ObservationAck
from packages.sources.contracts import IngestEnvelope, SourceDefinition


class NormalizationResult(BaseModel):
    observation_id: str
    knowledge_revision: int
    committed_at: datetime
    object_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    candidate_match_ids: list[str] = Field(default_factory=list)
    processing_run_id: str


class DurableNormalizer(Protocol):
    async def normalize(
        self,
        session: AsyncSession,
        source: SourceDefinition,
        envelope: IngestEnvelope,
        observation: ObservationAck,
    ) -> NormalizationResult: ...
