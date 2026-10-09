from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field


class RetrievalDisposition(StrEnum):
    EXECUTED = "executed"
    REUSED = "reused"
    FAILED = "failed"


class RetrievalRequestCoordinate(BaseModel):
    operator: str = Field(min_length=1)
    operator_revision: str = Field(min_length=1)
    query_digest: str = Field(min_length=64, max_length=64)
    knowledge_revision: int = Field(ge=0)
    limit: int = Field(ge=1)
    source_ids: list[str] = Field(default_factory=list)

    @property
    def request_digest(self) -> str:
        payload = self.model_dump(mode="json")
        return sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()

    @classmethod
    def lexical(
        cls,
        *,
        query: str,
        knowledge_revision: int,
        limit: int,
        source_ids: list[str] | None = None,
    ) -> RetrievalRequestCoordinate:
        normalized = query.strip()
        return cls(
            operator="lexical",
            operator_revision="postgres-simple-tsquery-v1",
            query_digest=sha256(normalized.encode()).hexdigest(),
            knowledge_revision=knowledge_revision,
            limit=limit,
            source_ids=sorted(set(source_ids or [])),
        )

    @classmethod
    def compact_name(
        cls, *, query: str, knowledge_revision: int, limit: int,
    ) -> RetrievalRequestCoordinate:
        return cls(
            operator="compact_name",
            operator_revision="ascii-name-whitespace-fold-v1",
            query_digest=sha256(query.strip().casefold().encode()).hexdigest(),
            knowledge_revision=knowledge_revision,
            limit=limit,
        )


class RetrievalInvocation(BaseModel):
    invocation_id: str
    request_owner_ref: str
    product_session_id: str
    product_turn_index: int = Field(ge=1)
    request: RetrievalRequestCoordinate
    result_refs: list[str] = Field(default_factory=list)
    disposition: RetrievalDisposition
    reuse_of_invocation_id: str | None = None
    failure_class: str | None = None
    started_at: datetime
    finished_at: datetime

    @property
    def ref(self) -> str:
        return f"retrieval-invocation:{self.invocation_id}"
