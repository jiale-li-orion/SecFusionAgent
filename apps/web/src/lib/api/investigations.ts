import { productFetch, productHeaders } from './request'

const pendingQuestionKeys = new Map<string, string>()
const pendingCancelKeys = new Map<string, string>()

function pendingKey(keys: Map<string, string>, fingerprint: string): string {
  const existing = keys.get(fingerprint)
  if (existing) return existing
  const key = crypto.randomUUID()
  keys.set(fingerprint, key)
  return key
}

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
  report_paragraphs: Array<{ text: string; evidence_refs: string[] }>
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
  idempotencyKey?: string
}): Promise<QuestionResult> {
  const payload = {
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
  }
  const fingerprint = JSON.stringify(payload)
  const key = input.idempotencyKey ?? pendingKey(pendingQuestionKeys, fingerprint)
  const response = await productFetch('/api/v1/questions', {
    method: 'POST',
    headers: productHeaders({ 'Content-Type': 'application/json', 'Idempotency-Key': key }),
    body: fingerprint,
  })

  const body = await response.json().catch(() => null)
  if (!response.ok && response.status !== 202) {
    const detail = body?.detail ?? body?.title ?? `Request failed (${response.status})`
    if (body?.code === 'idempotency_conflict' && String(detail).includes('original command failed')) pendingQuestionKeys.delete(fingerprint)
    throw Object.assign(new Error(String(detail)), { code: body?.code, context: body?.context })
  }
  pendingQuestionKeys.delete(fingerprint)
  return body as QuestionResult
}

export type QuestionStreamEvent =
  | { event: 'status'; phase: string; request_id: string }
  | { event: 'model_delta'; kind: 'content' | 'reasoning'; text: string }
  | { event: 'result'; result: QuestionResult }

export async function streamQuestion(
  input: Parameters<typeof askQuestion>[0],
  options: { includeReasoning: boolean; onEvent: (event: QuestionStreamEvent) => void; signal?: AbortSignal },
): Promise<QuestionResult> {
  const payload = {
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
  }
  const fingerprint = JSON.stringify(payload)
  const key = input.idempotencyKey ?? pendingKey(pendingQuestionKeys, fingerprint)
  const response = await productFetch('/api/v1/questions/stream', {
    method: 'POST',
    headers: productHeaders({ 'Content-Type': 'application/json', Accept: 'text/event-stream', 'Idempotency-Key': key }),
    body: JSON.stringify({
      ...payload,
      include_reasoning: options.includeReasoning,
    }),
    signal: options.signal,
  })
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null)
    if (body?.code === 'idempotency_conflict' && String(body?.detail).includes('original command failed')) pendingQuestionKeys.delete(fingerprint)
    throw new Error(String(body?.detail ?? body?.title ?? `Question stream failed (${response.status})`))
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: QuestionResult | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replaceAll('\r\n', '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const name = frame.split('\n').find(line => line.startsWith('event: '))?.slice(7)
      const raw = frame.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n')
      if (name && raw) {
        const data = JSON.parse(raw)
        if (name === 'error') {
          if (data.code === 'question_failed' || String(data.message).includes('original command failed')) pendingQuestionKeys.delete(fingerprint)
          throw new Error(String(data.message ?? data.code ?? 'Question failed'))
        }
        if (name === 'status') options.onEvent({ event: 'status', phase: String(data.phase), request_id: String(data.request_id) })
        if (name === 'model_delta') options.onEvent({ event: 'model_delta', kind: data.kind, text: String(data.text) })
        if (name === 'result') {
          result = data as QuestionResult
          options.onEvent({ event: 'result', result })
        }
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
  if (!result) throw new Error('Question stream ended without a result')
  pendingQuestionKeys.delete(fingerprint)
  return result
}

export async function cancelInvestigation(caseId: string, revision: number, idempotencyKey?: string): Promise<InvestigationView> {
  const fingerprint = `${caseId}:${revision}`
  const key = idempotencyKey ?? pendingKey(pendingCancelKeys, fingerprint)
  const response = await productFetch(`/api/v1/investigations/${encodeURIComponent(caseId)}/cancel`, {
    method: 'POST',
    headers: productHeaders({ 'Idempotency-Key': key, 'If-Match': `"${revision}"` }),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail ?? body?.title ?? `Cancel failed (${response.status})`
    throw new Error(String(detail))
  }
  pendingCancelKeys.delete(fingerprint)
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
  has_more: boolean
  next_before_turn: number | null
}

export type AccountConversation = {
  session_id: string
  updated_at: string
  latest_turn: QuestionSessionTurn
}

export type AccountConversationPage = { items: AccountConversation[]; has_more: boolean; next_cursor: string | null }

export async function listAccountConversations(limit = 20, signal?: AbortSignal, cursor?: string): Promise<AccountConversationPage> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (cursor) params.set('cursor', cursor)
  const response = await productFetch(`/api/v1/questions/sessions?${params}`, { headers: productHeaders(), signal })
  if (!response.ok) throw new Error(`Conversation list read failed (${response.status})`)
  return response.json()
}

export async function getQuestionSession(sessionId: string, beforeTurn?: number, signal?: AbortSignal): Promise<QuestionSessionHistory> {
  const params = new URLSearchParams()
  if (beforeTurn) params.set('before_turn', String(beforeTurn))
  const suffix = params.size ? `?${params}` : ''
  const response = await productFetch(`/api/v1/questions/sessions/${encodeURIComponent(sessionId)}${suffix}`, { headers: productHeaders(), signal })
  if (!response.ok) throw new Error(response.status === 403 ? 'Session access denied' : `Session read failed (${response.status})`)
  return response.json()
}
