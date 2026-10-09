from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, JsonValue


class EvidenceSourceView(BaseModel):
    source_id: str
    source_class: str
    source_role: str
    source_family: str
    authority_scope: list[str] = Field(default_factory=list)
    retention_mode: str


class EvidenceObservationView(BaseModel):
    observation_id: str
    acquisition_trigger: str
    external_object_id: str
    external_revision: str | None = None
    canonical_url: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    observed_at: datetime
    content_hash: str


class EvidenceArtifactView(BaseModel):
    artifact_id: str
    media_type: str
    content_hash: str
    trust_class: str
    created_at: datetime


class EvidenceTargetView(BaseModel):
    target_kind: str
    target_id: str
    label: str
    detail: dict[str, JsonValue] = Field(default_factory=dict)


class EvidenceDocumentPassageView(BaseModel):
    chunk_ref: str
    section: str | None = None
    text: str


class EvidenceView(BaseModel):
    evidence_ref: str
    source: EvidenceSourceView
    observation: EvidenceObservationView
    target: EvidenceTargetView
    locator: dict[str, JsonValue] = Field(default_factory=dict)
    artifact: EvidenceArtifactView | None = None
    document_passages: list[EvidenceDocumentPassageView] = Field(default_factory=list)
