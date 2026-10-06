from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IncidentSummaryView(BaseModel):
    incident_id: str
    candidate_id: str
    incident_type: str
    lifecycle: str
    promotion_reason: str
    current_summary: str | None = None
    watch_state: dict[str, object] = Field(default_factory=dict)
    current_revision: int
    timeline_event_count: int = 0
    source_link_count: int = 0
    source_diversity_count: int = 0
    created_at: datetime
    updated_at: datetime


class IncidentTimelineEventView(BaseModel):
    event_id: str
    signal_id: str
    event_time: datetime
    observed_at: datetime
    event_type: str
    summary: str
    source_role: str
    claim_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    supersedes_event_id: str | None = None
    created_revision: int


class IncidentSourceLinkView(BaseModel):
    source_link_id: str
    observation_id: str
    source_id: str
    source_family: str
    upstream_source: str | None = None
    independence_key: str
    source_role: str
    created_revision: int


class IncidentDetailView(BaseModel):
    incident: IncidentSummaryView
    timeline: list[IncidentTimelineEventView] = Field(default_factory=list)
    sources: list[IncidentSourceLinkView] = Field(default_factory=list)


class IncidentListView(BaseModel):
    items: list[IncidentSummaryView] = Field(default_factory=list)
