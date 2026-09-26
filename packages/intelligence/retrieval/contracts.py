from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class EmbeddingBatch(BaseModel):
    model: str
    version: str
    dimensions: int
    vectors: list[list[float]] = Field(default_factory=list)


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingBatch: ...
