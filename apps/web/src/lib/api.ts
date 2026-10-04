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

export type EvidenceRef = {
  evidence_ref: string
  source_id: string
  observation_id: string
  artifact_id: string | null
  external_object_id: string
  external_revision: string | null
  published_at: string | null
  updated_at: string | null
  observed_at: string
  canonical_url: string | null
  locator: Record<string, unknown>
}

export type KnowledgeClaim = {
  claim_id: string
  predicate: string
  value: unknown
  origin: string
  qualifier: Record<string, unknown>
  created_revision: number
  evidence: EvidenceRef[]
}

export type KnowledgeRelation = {
  relation_id: string
  relation_type: string
  origin: string
  qualifier: Record<string, unknown>
  created_revision: number
  target: {
    object_id: string
    object_type: string
    canonical_key: string
    properties: Record<string, unknown>
    external_identifiers: Record<string, string[]>
  }
  evidence: EvidenceRef[]
}

export type KnowledgeObject = {
  object_id: string
  object_type: string
  canonical_key: string
  properties: Record<string, unknown>
  external_identifiers: Record<string, string[]>
  claims: KnowledgeClaim[]
  relations: KnowledgeRelation[]
}

export type EvidenceDetail = {
  evidence_ref: string
  source: {
    source_id: string
    source_class: string
    source_role: string
    source_family: string
    authority_scope: string[]
    retention_mode: string
  }
  observation: {
    observation_id: string
    acquisition_trigger: string
    external_object_id: string
    external_revision: string | null
    canonical_url: string | null
    published_at: string | null
    updated_at: string | null
    observed_at: string
    content_hash: string
  }
  target: {
    target_kind: string
    target_id: string
    label: string
    detail: Record<string, unknown>
  }
  locator: Record<string, unknown>
  artifact: {
    artifact_id: string
    media_type: string
    content_hash: string
    trust_class: string
    created_at: string
  } | null
}

export async function getVulnerability(cveId: string): Promise<KnowledgeObject> {
  const response = await fetch(`/api/v1/vulnerabilities/${encodeURIComponent(cveId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Vulnerability not found' : `Vulnerability unavailable (${response.status})`)
  return response.json() as Promise<KnowledgeObject>
}

export async function getEvidence(evidenceRef: string): Promise<EvidenceDetail> {
  const response = await fetch(`/api/v1/evidence/${encodeURIComponent(evidenceRef)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Evidence not found' : `Evidence unavailable (${response.status})`)
  return response.json() as Promise<EvidenceDetail>
}

export type AgentRoleRuntime = {
  role_id: string
  version: string
  state_model: string
  planner_profile: string
  default_execution_profile: string
  accepted_task_kinds: string[]
  skill_scope: string[]
  status_counts: Record<string, number>
  active_tasks: number
  total_tasks: number
  last_updated_at: string | null
}

export type AgentTaskSummary = {
  run_id: string
  task_kind: string
  case_id: string | null
  parent_run_id: string | null
  role_id: string
  role_version: string
  status: string
  stop_reason: string | null
  result_available: boolean
  event_count: number
  last_event_type: string | null
  last_event_at: string | null
  created_at: string
  updated_at: string
  finished_at: string | null
}

export type AgentCapabilityActivity = {
  invocation_id: string
  task_run_id: string
  case_id: string | null
  capability_id: string
  binding_id: string
  tool_impl_id: string
  status: string
  started_at: string
  finished_at: string | null
  failure_code: string | null
}

export type AgentRuntimeOverview = {
  generated_at: string
  roles: AgentRoleRuntime[]
  recent_tasks: AgentTaskSummary[]
  recent_capabilities: AgentCapabilityActivity[]
}

export type AgentTaskDetail = {
  task: AgentTaskSummary
  events: Array<{
    event_id: string
    seq: number
    event_type: string
    producer: string
    emitted_at: string
  }>
  capabilities: AgentCapabilityActivity[]
}

export async function getAgentRuntime(): Promise<AgentRuntimeOverview> {
  const response = await fetch('/api/v1/agents/runtime?task_limit=72')
  if (!response.ok) throw new Error(`Agent runtime unavailable (${response.status})`)
  return response.json() as Promise<AgentRuntimeOverview>
}

export async function getAgentTask(runId: string): Promise<AgentTaskDetail> {
  const response = await fetch(`/api/v1/tasks/${encodeURIComponent(runId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Task not found' : `Task unavailable (${response.status})`)
  return response.json() as Promise<AgentTaskDetail>
}

export type InvestigationFinding = {
  proposition: string
  target_ref: string | null
  evidence_refs: string[]
  updated_revision: number
}

export type EvidenceNeedSummary = {
  need_id: string
  question: string
  purpose: string
  status: string
  priority: number
  required_source_roles: string[]
  updated_revision: number
}

export type DecisionView = {
  decision_id: string
  case_revision: number
  conclusions: Array<{ statement: string; type: string; evidence_refs: string[] }>
  citations: Array<{ conclusion_index: number; evidence_ref: string; source_ref: string | null; locator: Record<string, unknown> }>
  conflicts: string[]
  unknowns: string[]
  assumptions: string[]
  answer: Record<string, unknown>
  stop_reason: string
  created_at: string
}

export type InvestigationView = {
  case_id: string
  revision: number
  status: string
  execution_profile: string | null
  target_object_ids: string[]
  goal: string
  confirmed_findings: InvestigationFinding[]
  conflicts: InvestigationFinding[]
  unknowns: InvestigationFinding[]
  open_evidence_needs: EvidenceNeedSummary[]
  current_activity: {
    phase: string
    actor_role: string | null
    task_kind: string | null
    task_status: string | null
    updated_at: string | null
  }
  latest_decision: DecisionView | null
  terminal_reason: string | null
  created_at: string
  updated_at: string
  closed_at: string | null
}

export type ProductRuntimeEvent = {
  event_id: string
  event_type: string
  technical_type: string
  source_kind: string
  case_id: string
  task_run_id: string | null
  role_id: string | null
  status: string | null
  actor: string | null
  summary: string
  evidence_refs: string[]
  case_revision: number | null
  occurred_at: string
}

export async function listInvestigations(limit = 40): Promise<{ items: InvestigationView[]; next_cursor: string | null; has_more: boolean }> {
  const response = await fetch(`/api/v1/investigations?limit=${limit}`)
  if (!response.ok) throw new Error(`Investigations unavailable (${response.status})`)
  return response.json()
}

export async function getInvestigation(caseId: string): Promise<InvestigationView> {
  const response = await fetch(`/api/v1/investigations/${encodeURIComponent(caseId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Investigation not found' : `Investigation unavailable (${response.status})`)
  return response.json()
}

export async function getInvestigationActivity(caseId: string): Promise<{ case_id: string; events: ProductRuntimeEvent[] }> {
  const response = await fetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/activity`)
  if (!response.ok) throw new Error(`Runtime activity unavailable (${response.status})`)
  return response.json()
}
