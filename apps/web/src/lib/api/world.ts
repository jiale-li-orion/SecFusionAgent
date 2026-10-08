export async function getHotWorldItem(sourceId: string, externalObjectId: string): Promise<HotBug> {
  const response = await fetch(
    `/api/v1/world/hot/${encodeURIComponent(sourceId)}/${encodeURIComponent(externalObjectId)}`,
  )
  if (!response.ok) throw new Error(response.status === 404 ? 'Hot object not found' : `Hot object read failed (${response.status})`)
  return response.json() as Promise<HotBug>
}

export type WorldOverview = {
  schema_version: string
  generated_at: string
  source_health: { healthy: number; degraded: number; blocked: number }
  healthy_rate: number
  overdue_sources: number
  backfill_pending_sources: number
  categories: Array<{ category: string; healthy: number; degraded: number; blocked: number }>
  sources: Array<{
    source_id: string
    source_name: string | null
    measurement_category: string
    health: string
    latest_scheduled_status: string | null
    consecutive_failures: number
    backfill_pending: boolean
    last_success_at: string | null
    next_due_at: string | null
    backoff_until: string | null
    overdue: boolean
    latest_error_code: string | null
  }>
  windows: Record<string, {
    observations: number
    fresh_external_changes: number
    backfill_observations: number
    canonical_writes: number
    document_revisions: number
    document_chunks: number
    document_text_bytes: number
    scheduled_runs: number
    scheduled_run_success_rate: number | null
    provider_boundary_failure_rate: number | null
    runtime_owned_failure_rate: number | null
    queue_delay_p95_seconds: number | null
    execution_p95_seconds: number | null
    fresh_knowledge_latency_p95_seconds: number | null
    fresh_contributing_sources: number
    fresh_contributing_categories: number
    fresh_top1_source_share: number | null
    evidence_artifacts: number
    evidence_artifacts_present: number
    evidence_integrity_rate: number | null
    evidence_physical_bytes: number
  }>
  hourly_series: Array<Record<string, number | string | null>>
  category_hourly_series: Record<string, Array<Record<string, number | string | null>>>
  outbox_delivered: number
  lexical_ready_documents: number
  artifact_store_status: string | null
  public_epoch_artifact_integrity_rate: number | null
}

export async function getWorldOverview(): Promise<WorldOverview> {
  const response = await fetch('/api/v1/world/overview')
  if (!response.ok) throw new Error(`World overview read failed (${response.status})`)
  return response.json() as Promise<WorldOverview>
}

export type WorldKnowledgeChange = {
  change_id: string
  revision: number
  committed_at: string
  object_ids: string[]
  claim_ids: string[]
  relation_ids: string[]
  cause_processing_run_id: string | null
  cause_observation_id: string | null
}

export async function getWorldKnowledgeChanges(limit = 12): Promise<{ items: WorldKnowledgeChange[] }> {
  const response = await fetch(`/api/v1/world/knowledge-changes?limit=${limit}`)
  if (!response.ok) throw new Error(`Knowledge changes read failed (${response.status})`)
  return response.json() as Promise<{ items: WorldKnowledgeChange[] }>
}

export type WorldStory = {
  story_id: string
  category: string
  kind: string
  happened_at: string
  observed_at: string
  published_at: string | null
  headline: string
  excerpt: string | null
  excerpt_origin: string | null
  facts: Record<string, unknown>
  evidence: {
    observation_id: string
    document_revision_id: string | null
    external_revision: string | null
    chunk_id: string | null
    locator: Record<string, unknown>
  } | null
  source_id: string | null
  source_name: string | null
  object_id: string | null
  incident_id: string | null
  external_ref: string | null
}

export async function getWorldStories(limit = 10): Promise<{ items: WorldStory[] }> {
  const response = await fetch(`/api/v1/world/stories?limit=${limit}`)
  if (!response.ok) throw new Error(`World stories read failed (${response.status})`)
  return response.json() as Promise<{ items: WorldStory[] }>
}

export type WorldIncidentCandidate = {
  candidate_id: string
  incident_type: string
  promotion_state: string
  headline: string
  summary: string | null
  source_id: string
  source_name: string | null
  canonical_url: string | null
  published_at: string | null
  observed_at: string
  signal_count: number
  independent_source_count: number
  anchor_count: number
  watch_priority: number
  pinned: boolean
  last_material_change: string
  next_poll_at: string | null
  unresolved_question_count: number
}

export type WorldIncidentCandidateList = { total: number; unfiltered_total: number; total_signals: number; multi_source_candidates: number; anchored_candidates: number; items: WorldIncidentCandidate[] }

export async function getWorldIncidentCandidates(limit = 24): Promise<WorldIncidentCandidateList> {
  const response = await fetch(`/api/v1/world/incident-candidates?limit=${limit}`)
  if (!response.ok) throw new Error(`Incident candidates read failed (${response.status})`)
  return response.json() as Promise<WorldIncidentCandidateList>
}

export type HotBug = {
  source_name?: string | null
  source_id: string
  external_object_id: string
  external_revision: string | null
  cve_id: string | null
  title: string | null
  description: string | null
  status: string | null
  cvss_score: number | null
  cvss_severity: string | null
  affected_products: string[]
  canonical_url: string | null
  updated_at: string | null
  fetched_at: string
  changed_fields: string[]
  priority_signals: string[]
  access_count: number
  active: boolean
  pinned: boolean
  ttl_seconds: number | null
}

export async function getHotWorld(limit = 6): Promise<{ resident_total: number; items: HotBug[] }> {
  const response = await fetch(`/api/v1/world/hot?limit=${limit}`)
  if (!response.ok) throw new Error(`Hot world read failed (${response.status})`)
  return response.json() as Promise<{ resident_total: number; items: HotBug[] }>
}

export type WorldFormation = {
  generated_at: string
  processing: Array<{ run_id: string; processor_name: string; status: string; started_at: string; finished_at: string | null; source_name: string | null; external_object_id: string | null; committed_at: string | null; revision: number | null }>
}
export async function getWorldFormation(): Promise<WorldFormation> {
  const response = await fetch('/api/v1/world/formation')
  if (!response.ok) throw new Error(`World formation read failed (${response.status})`)
  return response.json() as Promise<WorldFormation>
}
