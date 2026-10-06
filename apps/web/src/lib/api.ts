export type TaskKind =
  | 'lookup'
  | 'retrieve'
  | 'verify_version_fix'
  | 'resolve_conflict'
  | 'investigate_relation'
  | 'investigate_incident'
  | 'watch_incident'
  | 'assess_normative_applicability'
  | 'observe_live_asset'

const PRODUCT_PRINCIPAL = 'user:product-demo'

function productHeaders(extra: Record<string, string> = {}) {
  return { 'X-Principal': PRODUCT_PRINCIPAL, ...extra }
}

export type QuestionResult = {
  request_id: string
  session_id: string
  turn_index: number
  mode: 'completed' | 'accepted'
  execution_profile: 'DIRECT' | 'RETRIEVE' | 'VERIFY' | 'INVESTIGATE' | 'WATCH' | string
  decision?: DecisionView | null
  investigation?: {
    case_id: string
    status: string
    goal: string
    current_activity?: unknown
    [key: string]: unknown
  } | null
}

export async function getSystemOverview(): Promise<SystemOverview> {
  const response = await fetch('/api/v1/observatory/system')
  if (!response.ok) throw new Error(`System overview unavailable (${response.status})`)
  return response.json() as Promise<SystemOverview>
}

export type ProductDocument = {
  document_id: string
  object_id: string
  source_id: string
  external_object_id: string
  canonical_url: string | null
  created_at: string
  current_revision: {
    document_revision_id: string
    observation_id: string
    external_revision: string | null
    title: string | null
    published_at: string | null
    updated_at: string | null
    content_hash: string
    parser_name: string
    parser_version: string
    created_at: string
  } | null
  chunk_count: number
  index_status_counts: Record<string, number>
  embedded_chunk_count: number
  embedding_models: string[]
  sections: string[]
  insight: {
    insight_candidate_id: string
    change_type: string
    evidence_maturity: string
    promotion_state: string
    related_object_ids: string[]
    related_claim_ids: string[]
    related_relation_ids: string[]
  } | null
}

export async function getDocumentByObject(objectId: string): Promise<ProductDocument> {
  const response = await fetch(`/api/v1/documents/by-object/${encodeURIComponent(objectId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Document not found' : `Document unavailable (${response.status})`)
  return response.json() as Promise<ProductDocument>
}

export async function getDocument(documentId: string): Promise<ProductDocument> {
  const response = await fetch(`/api/v1/documents/${encodeURIComponent(documentId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Document not found' : `Document unavailable (${response.status})`)
  return response.json() as Promise<ProductDocument>
}

export async function getHotWorldItem(sourceId: string, externalObjectId: string): Promise<HotBug> {
  const response = await fetch(
    `/api/v1/world/hot/${encodeURIComponent(sourceId)}/${encodeURIComponent(externalObjectId)}`,
  )
  if (!response.ok) throw new Error(response.status === 404 ? 'Hot object not found' : `Hot object unavailable (${response.status})`)
  return response.json() as Promise<HotBug>
}

export async function listAgentTasks(input: {
  roleId?: string
  status?: string
  caseId?: string
  limit?: number
} = {}): Promise<AgentTaskPage> {
  const params = new URLSearchParams()
  if (input.roleId) params.set('role_id', input.roleId)
  if (input.status) params.set('status', input.status)
  if (input.caseId) params.set('case_id', input.caseId)
  params.set('limit', String(input.limit ?? 72))
  const response = await fetch(`/api/v1/tasks?${params.toString()}`)
  if (!response.ok) throw new Error(`Task list unavailable (${response.status})`)
  return response.json() as Promise<AgentTaskPage>
}

export type IntelligenceSearchItem = {
  object_id: string
  object_type: string
  canonical_key: string
  label: string
  created_revision: number
  external_identifiers: Record<string, string[]>
}

export type IntelligenceSearchResult = {
  query: string
  items: IntelligenceSearchItem[]
}

export async function searchIntelligence(query: string, limit = 12): Promise<IntelligenceSearchResult> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  const response = await fetch(`/api/v1/intelligence/search?${params.toString()}`)
  if (!response.ok) throw new Error(`Intelligence search unavailable (${response.status})`)
  return response.json() as Promise<IntelligenceSearchResult>
}

export function evidenceBoundObjectIds(item: EvidenceDetail): string[] {
  const refs: string[] = []
  if (item.target.target_kind === 'object') refs.push(item.target.target_id)
  const detail = item.target.detail
  const subjectId = typeof detail.subject_id === 'string' ? detail.subject_id : null
  const sourceObjectId = typeof detail.source_object_id === 'string' ? detail.source_object_id : null
  const targetObjectId = typeof detail.target_object_id === 'string' ? detail.target_object_id : null
  if (subjectId) refs.push(subjectId)
  if (sourceObjectId) refs.push(sourceObjectId)
  if (targetObjectId) refs.push(targetObjectId)
  return [...new Set(refs)]
}

export async function getKnowledgeObject(objectId: string): Promise<KnowledgeObject> {
  const response = await fetch(`/api/v1/intelligence/objects/${encodeURIComponent(objectId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Knowledge object not found' : `Knowledge object unavailable (${response.status})`)
  return response.json() as Promise<KnowledgeObject>
}

export type IntelligenceGraph = {
  center: {
    object_id: string
    object_type: string
    canonical_key: string
    label: string
  }
  relations: KnowledgeRelation[]
  total_relation_count: number
  neighborhood: string
}

export async function getIntelligenceGraph(objectId: string, limit = 24): Promise<IntelligenceGraph> {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await fetch(
    `/api/v1/intelligence/objects/${encodeURIComponent(objectId)}/graph?${params.toString()}`,
  )
  if (!response.ok) throw new Error(response.status === 404 ? 'Knowledge graph not found' : `Knowledge graph unavailable (${response.status})`)
  return response.json() as Promise<IntelligenceGraph>
}

export type IntelligenceEnrichmentDimension = {
  dimension: string
  status: 'resolved' | 'conflict' | 'unknown' | 'missing'
  requirement_id: string
  accepted_fact_refs: string[]
  conflict_refs: string[]
  missing_prerequisites: string[]
  attempted_operator_refs: string[]
  blocked_attempt_refs: string[]
  world_revision: number
}

export type IntelligenceEnrichmentState = {
  object_id: string
  object_type: string
  canonical_key: string
  vocabulary_revision: string
  world_revision: number
  dimensions: IntelligenceEnrichmentDimension[]
}

export async function getIntelligenceEnrichment(objectId: string): Promise<IntelligenceEnrichmentState> {
  const response = await fetch(`/api/v1/intelligence/objects/${encodeURIComponent(objectId)}/enrichment`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Enrichment state not found' : `Enrichment state unavailable (${response.status})`)
  return response.json() as Promise<IntelligenceEnrichmentState>
}

export type ProofRunSummary = {
  benchmark_run_id: string
  suite_ref: string
  deployment_revision_id: string
  world_snapshot_ref: string | null
  status: string
  execution_mode: string
  environment: string
  started_at: string
  finished_at: string | null
  case_count: number
  passed_case_count: number
}

export type ProofCaseRun = {
  case_run_id: string
  case_ref: string
  target_refs: string[]
  execution_profile: string | null
  status: string
  failure_class: string | null
  task_run_id: string | null
  execution_id: string | null
  decision_ref: string | null
  replay_checkpoint_ref: string | null
  artifact_refs: string[]
  started_at: string
  finished_at: string | null
}

export type ProofMetricObservation = {
  metric_observation_id: string
  metric_name: string
  value: number
  unit: string | null
  direction: string
  measurement_source: string
  case_run_id: string
  subject_ref: string | null
  evidence_refs: string[]
  created_at: string
}

export type ProofRunDetail = {
  run: ProofRunSummary
  deployment: {
    deployment_revision_id: string
    git_commit: string
    container_image_digest: string | null
    schema_revision: string
    source_inventory_hash: string
    vocabulary_revision: string
    policy_revision: string
    capability_registry_revision: string
    skill_registry_revision: string | null
    model_provider_revision: string
    configuration_digest: string
    created_at: string
  }
  cases: ProofCaseRun[]
  metrics: ProofMetricObservation[]
}

export async function getCompetitionProofRun(runId: string): Promise<ProofRunDetail> {
  const response = await fetch(`/api/v1/observatory/proof/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Benchmark run not found' : `Benchmark run unavailable (${response.status})`)
  return response.json() as Promise<ProofRunDetail>
}

export async function askQuestion(input: {
  question: string
  cveId?: string
  objectId?: string
  sessionId?: string
  taskKind: TaskKind
  requiredSourceRoles?: string[]
  priority?: number
  interactiveTimeoutSeconds?: number
  retrievalLimit?: number
  allowWait?: boolean
  investigationTimeoutSeconds?: number
  agentTurns?: number
  toolCalls?: number
}): Promise<QuestionResult> {
  const response = await fetch('/api/v1/questions', {
    method: 'POST',
    headers: productHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      question: input.question,
      cve_id: input.cveId || undefined,
      object_id: input.objectId || undefined,
      session_id: input.sessionId || undefined,
      task_kind: input.taskKind,
      required_source_roles: input.requiredSourceRoles ?? [],
      priority: input.priority ?? 50,
      interactive_timeout_seconds: input.interactiveTimeoutSeconds ?? 5,
      retrieval_limit: input.retrievalLimit ?? 8,
      allow_wait: input.allowWait ?? true,
      investigation_timeout_seconds: input.investigationTimeoutSeconds ?? 300,
      agent_turns: input.agentTurns ?? 8,
      tool_calls: input.toolCalls ?? 12,
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
  sources: Array<{
    source_id: string
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

export type IncidentSummary = {
  incident_id: string
  candidate_id: string
  incident_type: string
  lifecycle: string
  promotion_reason: string
  current_summary: string | null
  watch_state: Record<string, unknown>
  current_revision: number
  timeline_event_count: number
  source_link_count: number
  source_diversity_count: number
  created_at: string
  updated_at: string
}

export type IncidentTimelineEvent = {
  event_id: string
  signal_id: string
  event_time: string
  observed_at: string
  event_type: string
  summary: string
  source_role: string
  claim_refs: string[]
  evidence_refs: string[]
  supersedes_event_id: string | null
  created_revision: number
}

export type IncidentSourceLink = {
  source_link_id: string
  observation_id: string
  source_id: string
  source_family: string
  upstream_source: string | null
  independence_key: string
  source_role: string
  created_revision: number
}

export type IncidentDetail = {
  incident: IncidentSummary
  timeline: IncidentTimelineEvent[]
  sources: IncidentSourceLink[]
}

export async function listIncidents(limit = 20): Promise<{ items: IncidentSummary[] }> {
  const response = await fetch(`/api/v1/incidents?limit=${limit}`)
  if (!response.ok) throw new Error(`Incidents unavailable (${response.status})`)
  return response.json() as Promise<{ items: IncidentSummary[] }>
}

export async function getIncident(incidentId: string): Promise<IncidentDetail> {
  const response = await fetch(`/api/v1/incidents/${encodeURIComponent(incidentId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Incident not found' : `Incident unavailable (${response.status})`)
  return response.json() as Promise<IncidentDetail>
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
  failure_detail: string | null
  policy_decision_ref: string | null
  canonical_output_ref: string | null
  raw_artifact_ref: string | null
  effect_receipt_ref: string | null
  observation_class: string | null
}

export type AgentModelRuntime = {
  scope: string
  request_limit: number
  request_count: number
  attempt_count: number
  retry_attempt_count: number
  retry_scheduled_count: number
  failed_attempt_count: number
  unknown_after_dispatch_count: number
  p95_latency_ms: number | null
  provider_counts: Record<string, number>
  model_counts: Record<string, number>
  latest_attempt_at: string | null
}

export type AgentControlRuntime = {
  scope: string
  sampled_task_count: number
  dependency_wake_count: number
  waiting_event_count: number
  stop_reason_counts: Record<string, number>
  wake_latency_ms: number | null
  wake_latency_measurement: string
}

export type SystemDependency = {
  component: string
  status: string
  latency_ms: number | null
  detail_code: string | null
}

export type SystemBacklog = {
  pending_count: number
  oldest_pending_at: string | null
}

export type SystemOverview = {
  generated_at: string
  overall: string
  dependencies: SystemDependency[]
  outbox: SystemBacklog
  task_event_delivery: SystemBacklog
  task_event_stream_pending: number | null
  runtime_policy_status: string
  model_provider_status: string
  measurement_boundaries: Record<string, string>
}

export type AgentRuntimeOverview = {
  generated_at: string
  roles: AgentRoleRuntime[]
  recent_tasks: AgentTaskSummary[]
  recent_capabilities: AgentCapabilityActivity[]
  model_runtime: AgentModelRuntime
  control_runtime: AgentControlRuntime
}

export type AgentTaskPage = {
  generated_at: string
  items: AgentTaskSummary[]
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
  budget: {
    account_id: string
    limits: Record<string, number>
    reserved: Record<string, number>
    committed: Record<string, number>
    remaining: Record<string, number>
  } | null
  prompt_assemblies: Array<{
    assembly_id: string
    execution_id: string
    context_manifest_ref: string
    role_revision: string
    execution_profile_revision: string
    materialized_skill_refs: string[]
    materialized_capability_view_refs: string[]
    percept_refs: string[]
    materialized_ref_set_digest: string
    created_at: string
  }>
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
  continuation_session_id: string | null
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
  const response = await fetch(`/api/v1/investigations?limit=${limit}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(`Investigations unavailable (${response.status})`)
  return response.json()
}

export async function getInvestigation(caseId: string): Promise<InvestigationView> {
  const response = await fetch(`/api/v1/investigations/${encodeURIComponent(caseId)}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(response.status === 404 ? 'Investigation not found' : `Investigation unavailable (${response.status})`)
  return response.json()
}

export async function getInvestigationActivity(caseId: string): Promise<{ case_id: string; events: ProductRuntimeEvent[] }> {
  const response = await fetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/activity`)
  if (!response.ok) throw new Error(`Runtime activity unavailable (${response.status})`)
  return response.json()
}

export type CompetitionProof = {
  report_id: string
  report_digest: string
  deployment_revision_id: string
  generated_at: string
  benchmark_runs_completed: number
  case_runs_passed: number
  registered_core_metrics: number
  observed_core_metrics: number
  metric_groups: number
  observed_metric_groups: number
  partial_metric_groups: number
  unevaluated_core_metrics: string[]
  headline_metrics: Array<{
    metric_name: string
    value: number
    unit: string | null
    direction: string
  }>
  target_checks: Array<{
    target_name: string
    requirement: string
    metric_name: string
    observed_value: number
    threshold: number
    comparator: string
    status: string
  }>
  runs: ProofRunSummary[]
}

export async function getCompetitionProof(): Promise<CompetitionProof> {
  const response = await fetch('/api/v1/observatory/proof')
  if (!response.ok) throw new Error(`Competition proof unavailable (${response.status})`)
  return response.json() as Promise<CompetitionProof>
}

export type ProductSkill = {
  skill_ref: string
  skill_id: string
  version: number
  status: string
  source_type: string
  task_patterns: string[]
  evidence_need_patterns: string[]
  applicable_object_types: string[]
  applicability_conditions: string[]
  required_capability_classes: string[]
  optional_capability_classes: string[]
  expected_outcomes: string[]
  risk_hint: string | null
  cost_hint: string | null
  validation_ref: string | null
  supersedes: string | null
  steps: Array<Record<string, unknown>>
  evidence_expectations: string[]
  failure_guards: string[]
  fallbacks: string[]
  stop_conditions: string[]
  provenance_origin: string
  supporting_trajectory_refs: string[]
  supporting_experience_pattern_refs: string[]
  validation_case_refs: string[]
  promotion_history: string[]
}

export type ProductExperience = {
  experience_id: string
  experience_version_id: string
  version: number
  name: string
  task_signature: string
  status: string
  trigger_signals: string[]
  applicable_conditions: string[]
  recommended_actions: string[]
  evidence_expectation: string[]
  failure_modes: string[]
  stop_conditions: string[]
  fallback_actions: string[]
  success_count: number
  failure_count: number
  partial_count: number
  support_records: Array<{
    trajectory_id: string
    case_id: string
    trajectory_status: string
    trajectory_outcome: string | null
    latency_ms: number | null
    tool_calls: number
    started_at: string
    finished_at: string | null
    outcome: string
    evaluation: Record<string, unknown>
    evaluator: string
    created_at: string
  }>
}

export type AgentLearningOverview = {
  skills: ProductSkill[]
  experiences: ProductExperience[]
  experience_candidate_count: number
  trajectory_count: number
  completed_trajectory_count: number
}

export type AgentControlledProofCase = {
  case_id: string
  subsystem: string | null
  metrics: Record<string, number>
  diagnostics: Record<string, unknown>
  task_run_ids: string[]
  evidence_refs: string[]
  capability_invocation_ids: string[]
}

export type AgentControlledProof = {
  schema_version: string
  benchmark_run_id: string
  deployment_revision_id: string
  suite_ref: string
  execution_mode: string
  scope: string
  cases: AgentControlledProofCase[]
}

export async function getAgentLearning(): Promise<AgentLearningOverview> {
  const response = await fetch('/api/v1/agents/learning')
  if (!response.ok) throw new Error(`Agent learning unavailable (${response.status})`)
  return response.json() as Promise<AgentLearningOverview>
}

export async function getAgentControlledProof(): Promise<AgentControlledProof> {
  const response = await fetch('/api/v1/agents/proof')
  if (!response.ok) throw new Error(`Agent controlled proof unavailable (${response.status})`)
  return response.json() as Promise<AgentControlledProof>
}

export async function cancelInvestigation(caseId: string): Promise<InvestigationView> {
  const response = await fetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/cancel`, {
    method: 'POST',
    headers: productHeaders(),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail ?? body?.title ?? `Cancel failed (${response.status})`
    throw new Error(String(detail))
  }
  return body as InvestigationView
}
