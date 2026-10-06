import { productHeaders } from './request'

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
  origin_scope: 'product' | 'benchmark' | 'system' | 'unknown'
  can_cancel: boolean
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
