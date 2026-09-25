from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field, JsonValue

from packages.sources.contracts import IngestEnvelope


class ObjectCandidate(BaseModel):
    object_type: str
    canonical_key: str
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    identifiers: dict[str, list[str]] = Field(default_factory=dict)


class ClaimCandidate(BaseModel):
    predicate: str
    value: JsonValue
    qualifier: dict[str, JsonValue] = Field(default_factory=dict)
    locator: dict[str, JsonValue]


class RelationCandidate(BaseModel):
    relation_type: str
    target: ObjectCandidate
    qualifier: dict[str, JsonValue] = Field(default_factory=dict)
    locator: dict[str, JsonValue]


class EnrichmentCandidate(BaseModel):
    root_object: ObjectCandidate | None = None
    root_identifiers: dict[str, list[str]] = Field(default_factory=dict)
    claims: list[ClaimCandidate] = Field(default_factory=list)
    relations: list[RelationCandidate] = Field(default_factory=list)
    replace_predicates: list[str] = Field(default_factory=list)
    replace_relation_types: list[str] = Field(default_factory=list)


class EnrichmentMapper(Protocol):
    PROCESSOR_NAME: str
    PROCESSOR_VERSION: str

    def map(self, envelope: IngestEnvelope) -> EnrichmentCandidate: ...
