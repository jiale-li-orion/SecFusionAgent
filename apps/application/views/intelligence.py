from __future__ import annotations

from pydantic import BaseModel, Field

from packages.intelligence.knowledge.read import RelationView


class IntelligenceSearchItemView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    label: str
    created_revision: int
    external_identifiers: dict[str, list[str]] = Field(default_factory=dict)


class IntelligenceSearchView(BaseModel):
    query: str
    items: list[IntelligenceSearchItemView] = Field(default_factory=list)


class ProductDocumentRevisionView(BaseModel):
    document_revision_id: str
    observation_id: str
    external_revision: str | None = None
    title: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    content_hash: str
    parser_name: str
    parser_version: str
    created_at: str


class ProductDocumentInsightView(BaseModel):
    insight_candidate_id: str
    change_type: str
    evidence_maturity: str
    promotion_state: str
    related_object_ids: list[str] = Field(default_factory=list)
    related_claim_ids: list[str] = Field(default_factory=list)
    related_relation_ids: list[str] = Field(default_factory=list)


class ProductDocumentView(BaseModel):
    document_id: str
    object_id: str
    source_id: str
    external_object_id: str
    canonical_url: str | None = None
    created_at: str
    current_revision: ProductDocumentRevisionView | None = None
    chunk_count: int = 0
    index_status_counts: dict[str, int] = Field(default_factory=dict)
    embedded_chunk_count: int = 0
    embedding_models: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    insight: ProductDocumentInsightView | None = None


class IntelligenceGraphCenterView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    label: str


class IntelligenceGraphView(BaseModel):
    center: IntelligenceGraphCenterView
    relations: list[RelationView] = Field(default_factory=list)
    total_relation_count: int = 0
    neighborhood: str = "canonical_outbound_one_hop"
