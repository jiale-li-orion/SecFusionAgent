export type TaskKind =
  | 'lookup'
  | 'retrieve'
  | 'verify_version_fix'
  | 'investigate_incident'
  | 'watch_incident'

export type QuestionResult = {
  request_id: string
  session_id: string
  turn_index: number
  mode: 'completed' | 'accepted'
  execution_profile: 'DIRECT' | 'RETRIEVE' | 'VERIFY' | 'INVESTIGATE' | 'WATCH' | string
  decision?: {
    decision_id: string
    answer?: string | null
    recommendation?: string | null
    conclusions?: unknown[]
    citations?: string[]
    conflicts?: unknown[]
    unknowns?: unknown[]
    [key: string]: unknown
  } | null
  investigation?: {
    case_id: string
    status: string
    goal: string
    current_activity?: unknown
    [key: string]: unknown
  } | null
}

export async function askQuestion(input: {
  question: string
  cveId?: string
  sessionId?: string
  taskKind: TaskKind
}): Promise<QuestionResult> {
  const response = await fetch('/api/v1/questions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Principal': 'user:product-demo',
    },
    body: JSON.stringify({
      question: input.question,
      cve_id: input.cveId || undefined,
      session_id: input.sessionId || undefined,
      task_kind: input.taskKind,
    }),
  })

  const body = await response.json().catch(() => null)
  if (!response.ok && response.status !== 202) {
    const detail = body?.detail ?? body?.title ?? `Request failed (${response.status})`
    throw new Error(String(detail))
  }
  return body as QuestionResult
}


export type WorldOverview = {
  schema_version: string
  generated_at: string
  source_health: { healthy: number; degraded: number; blocked: number }
  healthy_rate: number
  overdue_sources: number
  backfill_pending_sources: number
  categories: Array<{ category: string; healthy: number; degraded: number; blocked: number }>
  windows: Record<string, {
    observations: number
    fresh_external_changes: number
    backfill_observations: number
    canonical_writes: number
    scheduled_runs: number
    scheduled_run_success_rate: number | null
    provider_boundary_failure_rate: number | null
    runtime_owned_failure_rate: number | null
    queue_delay_p95_seconds: number | null
    execution_p95_seconds: number | null
    fresh_knowledge_latency_p95_seconds: number | null
    evidence_integrity_rate: number | null
  }>
  hourly_series: Array<Record<string, number | string | null>>
  outbox_delivered: number
  lexical_ready_documents: number
  artifact_store_status: string | null
  public_epoch_artifact_integrity_rate: number | null
}

export async function getWorldOverview(): Promise<WorldOverview> {
  const response = await fetch('/api/v1/world/overview')
  if (!response.ok) throw new Error(`World overview unavailable (${response.status})`)
  return response.json() as Promise<WorldOverview>
}

export type HotBug = {
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

export async function getHotWorld(limit = 6): Promise<{ items: HotBug[] }> {
  const response = await fetch(`/api/v1/world/hot?limit=${limit}`)
  if (!response.ok) throw new Error(`Hot world unavailable (${response.status})`)
  return response.json() as Promise<{ items: HotBug[] }>
}
