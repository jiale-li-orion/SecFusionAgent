import { productFetch, productHeaders } from './request'

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
  investigation?: InvestigationView | null
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
  case_lifecycle: string | null
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
  const response = await productFetch(`/api/v1/investigations?origin_scope=product&limit=${limit}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(`Investigation index read failed (${response.status})`)
  return response.json()
}

export async function getInvestigation(caseId: string): Promise<InvestigationView> {
  const response = await productFetch(`/api/v1/investigations/${encodeURIComponent(caseId)}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(response.status === 404 ? 'Investigation not found' : `Investigation read failed (${response.status})`)
  return response.json()
}

export async function getInvestigationActivity(caseId: string): Promise<{ case_id: string; events: ProductRuntimeEvent[] }> {
  const response = await productFetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/activity`, { headers: productHeaders() })
  if (!response.ok) throw new Error(`Runtime activity read failed (${response.status})`)
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
  const response = await productFetch('/api/v1/questions', {
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
    throw Object.assign(new Error(String(detail)), { code: body?.code, context: body?.context })
  }
  return body as QuestionResult
}

export async function cancelInvestigation(caseId: string): Promise<InvestigationView> {
  const response = await productFetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/cancel`, {
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

export async function getDecision(decisionId: string): Promise<DecisionView> {
  const response = await productFetch(`/api/v1/decisions/${encodeURIComponent(decisionId)}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(response.status === 404 ? 'Decision not found' : `Decision read failed (${response.status})`)
  return response.json()
}


export type QuestionSessionTurn = {
  turn_index: number
  request_id: string
  question: string
  task_kind: string
  target_object_ids: string[]
  knowledge_revision: number | null
  context_id: string | null
  decision_ref: string | null
  investigation_ref: string | null
  created_at: string
}

export type QuestionSessionHistory = {
  session_id: string
  turns: QuestionSessionTurn[]
}

export type AccountConversation = {
  session_id: string
  updated_at: string
  latest_turn: QuestionSessionTurn
}

export async function listAccountConversations(limit = 20, signal?: AbortSignal): Promise<{ items: AccountConversation[]; has_more: boolean }> {
  const response = await productFetch(`/api/v1/questions/sessions?limit=${limit}`, { headers: productHeaders(), signal })
  if (!response.ok) throw new Error(`Conversation list read failed (${response.status})`)
  return response.json()
}

export async function getQuestionSession(sessionId: string): Promise<QuestionSessionHistory> {
  const response = await productFetch(`/api/v1/questions/sessions/${encodeURIComponent(sessionId)}`, { headers: productHeaders() })
  if (!response.ok) throw new Error(response.status === 403 ? 'Session access denied' : `Session read failed (${response.status})`)
  return response.json()
}
