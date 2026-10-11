from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from packages.intelligence.knowledge.read import EvidenceRef


class IntelligencePreferencesInput(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=20)
    target_object_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("keywords", "target_object_ids")
    @classmethod
    def normalize_values(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            value = value.strip()
            if not value or len(value) > 128:
                raise ValueError("preference values must contain 1-128 characters")
            if value.casefold() not in {item.casefold() for item in normalized}:
                normalized.append(value)
        return normalized


class FollowedObjectView(BaseModel):
    object_id: str
    object_type: str
    canonical_key: str
    label: str


class IntelligencePreferencesView(IntelligencePreferencesInput):
    updated_at: datetime | None = None
    target_objects: list[FollowedObjectView] = Field(default_factory=list)


class RecommendationFeedbackInput(BaseModel):
    feedback: Literal["interested", "ignored", "neutral"]


class RecommendationFeedbackView(RecommendationFeedbackInput):
    object_id: str
    updated_at: datetime


class RecommendationReasonView(BaseModel):
    kind: Literal["keyword", "followed_object", "related_object", "interested"]
    value: str
    label: str
    weight: int
    relation_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


PreviewOrigin = Literal["canonical_property", "accepted_claim", "retained_excerpt"]


class IntelligenceRecommendationView(FollowedObjectView):
    score: int
    feedback: Literal["interested"] | None = None
    reasons: list[RecommendationReasonView]
    evidence: list[EvidenceRef]
    created_revision: int
    title: str | None = None
    summary: str | None = None
    title_origin: PreviewOrigin | None = None
    title_evidence_refs: list[str] = Field(default_factory=list)
    preview_origin: PreviewOrigin | None = None
    preview_evidence_refs: list[str] = Field(default_factory=list)
    preview_chunk_ref: str | None = None
    evidence_count: int = 0
    source_count: int = 0
    published_at: datetime | None = None
    observed_at: datetime | None = None
    timestamp_evidence_ref: str | None = None


class IntelligenceRecommendationsView(BaseModel):
    generated_at: datetime
    knowledge_revision: int
    preferences_updated_at: datetime | None = None
    candidate_limit: int = 128
    items: list[IntelligenceRecommendationView] = Field(default_factory=list)


class FollowResolutionView(BaseModel):
    query: str
    exact_match: FollowedObjectView | None = None
    candidates: list[FollowedObjectView] = Field(default_factory=list)


class IntelligenceActivityView(IntelligenceRecommendationView):
    activity_id: str
    activity_kind: str
    activity_at: datetime
    activity_evidence_ref: str


class IntelligenceFeedView(BaseModel):
    generated_at: datetime
    knowledge_revision: int
    mode: Literal["following", "recommended"]
    window: Literal["30d", "all"]
    items: list[IntelligenceActivityView] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
