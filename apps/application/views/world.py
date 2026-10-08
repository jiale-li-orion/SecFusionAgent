from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class WorldHealthCountsView(BaseModel):
    healthy: int = 0
    degraded: int = 0
    blocked: int = 0


class WorldCategoryHealthView(BaseModel):
    category: str
    healthy: int = 0
    degraded: int = 0
    blocked: int = 0


class WorldSourceHealthView(BaseModel):
    source_id: str
    source_name: str | None = None
    measurement_category: str
    health: str
    latest_scheduled_status: str | None = None
    consecutive_failures: int = 0
    backfill_pending: bool = False
    last_success_at: datetime | None = None
    next_due_at: datetime | None = None
    backoff_until: datetime | None = None
    overdue: bool = False
    latest_error_code: str | None = None


class WorldWindowView(BaseModel):
    observations: int = 0
    fresh_external_changes: int = 0
    backfill_observations: int = 0
    canonical_writes: int = 0
    document_revisions: int = 0
    document_chunks: int = 0
    document_text_bytes: int = 0
    scheduled_runs: int = 0
    scheduled_run_success_rate: float | None = None
    provider_boundary_failure_rate: float | None = None
    runtime_owned_failure_rate: float | None = None
    queue_delay_p95_seconds: float | None = None
    execution_p95_seconds: float | None = None
    fresh_knowledge_latency_p95_seconds: float | None = None
    fresh_contributing_sources: int = 0
    fresh_contributing_categories: int = 0
    fresh_top1_source_share: float | None = None
    evidence_artifacts: int = 0
    evidence_artifacts_present: int = 0
    evidence_integrity_rate: float | None = None
    evidence_physical_bytes: int = 0


class WorldSeriesPointView(BaseModel):
    hour_start: datetime
    observations: int = 0
    fresh_external_changes: int = 0
    backfill_observations: int = 0
    canonical_writes: int = 0
    document_chunks: int = 0
    document_text_bytes: int = 0
    scheduled_runs: int = 0
    scheduled_run_success_rate: float | None = None
    provider_boundary_failure_rate: float | None = None
    runtime_owned_failure_rate: float | None = None
    queue_delay_p95_seconds: float | None = None
    execution_p95_seconds: float | None = None
    fresh_knowledge_latency_p95_seconds: float | None = None
    fresh_contributing_sources: int = 0
    fresh_contributing_categories: int = 0
    fresh_top1_source_share: float | None = None


class WorldOverviewView(BaseModel):
    schema_version: str
    generated_at: datetime
    source_health: WorldHealthCountsView
    healthy_rate: float
    overdue_sources: int
    backfill_pending_sources: int
    categories: list[WorldCategoryHealthView] = Field(default_factory=list)
    sources: list[WorldSourceHealthView] = Field(default_factory=list)
    windows: dict[str, WorldWindowView]
    hourly_series: list[WorldSeriesPointView] = Field(default_factory=list)
    category_hourly_series: dict[str, list[WorldSeriesPointView]] = Field(default_factory=dict)
    outbox_delivered: int = 0
    lexical_ready_documents: int = 0
    artifact_store_status: str | None = None
    public_epoch_artifact_integrity_rate: float | None = None


class WorldKnowledgeChangeView(BaseModel):
    change_id: str
    revision: int
    committed_at: datetime
    object_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    cause_processing_run_id: str | None = None
    cause_observation_id: str | None = None


class WorldKnowledgeChangeListView(BaseModel):
    items: list[WorldKnowledgeChangeView] = Field(default_factory=list)


class WorldIncidentCandidateView(BaseModel):
    candidate_id: str
    incident_type: str
    promotion_state: str
    headline: str
    summary: str | None = None
    source_id: str
    source_name: str | None = None
    canonical_url: str | None = None
    published_at: datetime | None = None
    observed_at: datetime
    signal_count: int = 0
    independent_source_count: int = 0
    anchor_count: int = 0
    watch_priority: int = 0
    pinned: bool = False
    last_material_change: datetime
    next_poll_at: datetime | None = None
    unresolved_question_count: int = 0


class WorldIncidentCandidateListView(BaseModel):
    total: int = 0
    unfiltered_total: int = 0
    total_signals: int = 0
    multi_source_candidates: int = 0
    anchored_candidates: int = 0
    items: list[WorldIncidentCandidateView] = Field(default_factory=list)


class WorldStoryEvidenceView(BaseModel):
    observation_id: str
    document_revision_id: str | None = None
    external_revision: str | None = None
    chunk_id: str | None = None
    locator: dict[str, object] = Field(default_factory=dict)


class WorldStoryView(BaseModel):
    story_id: str
    category: str
    kind: str
    happened_at: datetime
    observed_at: datetime
    published_at: datetime | None = None
    headline: str
    excerpt: str | None = None
    excerpt_origin: str | None = None
    facts: dict[str, object] = Field(default_factory=dict)
    evidence: WorldStoryEvidenceView | None = None
    source_id: str | None = None
    source_name: str | None = None
    object_id: str | None = None
    incident_id: str | None = None
    external_ref: str | None = None


class WorldStoryListView(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    items: list[WorldStoryView] = Field(default_factory=list)


class HotBugView(BaseModel):
    source_name: str | None = None
    source_id: str
    external_object_id: str
    external_revision: str | None = None
    cve_id: str | None = None
    title: str | None = None
    description: str | None = None
    status: str | None = None
    cvss_score: float | None = None
    cvss_severity: str | None = None
    affected_products: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    updated_at: datetime | None = None
    fetched_at: datetime
    changed_fields: list[str] = Field(default_factory=list)
    priority_signals: list[str] = Field(default_factory=list)
    access_count: float = 0.0
    active: bool = False
    pinned: bool = False
    ttl_seconds: int | None = None


class HotBugListView(BaseModel):
    resident_total: int = 0
    items: list[HotBugView] = Field(default_factory=list)


class WorldProcessingView(BaseModel):
    run_id: str
    processor_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    source_name: str | None = None
    external_object_id: str | None = None
    committed_at: datetime | None = None
    revision: int | None = None


class WorldFormationView(BaseModel):
    generated_at: datetime
    processing: list[WorldProcessingView] = Field(default_factory=list)
