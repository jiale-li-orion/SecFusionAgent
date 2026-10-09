import { productFetch } from './request'

export async function listAgentTasks(input: {
  roleId?: string
  status?: string
  caseId?: string
  limit?: number
  cursor?: string
} = {}): Promise<AgentTaskPage> {
  const params = new URLSearchParams()
  if (input.roleId) params.set('role_id', input.roleId)
  if (input.status) params.set('status', input.status)
  if (input.caseId) params.set('case_id', input.caseId)
  params.set('limit', String(input.limit ?? 72))
  if (input.cursor) params.set('cursor', input.cursor)
  const response = await productFetch(`/api/v1/tasks?${params.toString()}`)
  if (!response.ok) throw new Error(`Task list read failed (${response.status})`)
  return response.json() as Promise<AgentTaskPage>
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
  predecessor_run_id: string | null
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
  next_cursor: string | null
  has_more: boolean
}

export type AgentTaskDetail = {
  task: AgentTaskSummary
  parent: AgentTaskSummary | null
  predecessor: AgentTaskSummary | null
  children: AgentTaskSummary[]
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
    fragments: Array<{ kind: string | null; source_ref: string | null; selection_reason: string | null; trust_class: string | null; disclosure_level: string | null }>
    created_at: string
  }>
  model_attempts: Array<{
    model_request_id: string
    model_attempt_id: string
    purpose: string
    prompt_revision: string
    requested_model: string
    actual_model: string
    status: string
    ordinal: number
    latency_ms: number | null
    input_tokens: number | null
    output_tokens: number | null
    total_tokens: number | null
    reasoning_tokens: number | null
    usage_source: string
    budget_settlement: string | null
    budget_committed_model_tokens: number | null
    started_at: string
  }>
  context: {
    context_id: string
    context_revision: number
    parent_context_id: string | null
    role_ref: string
    case_ref: string | null
    knowledge_revision: number | null
    evidence_refs: string[]
    object_refs: string[]
    relation_refs: string[]
    retrieval_invocation_refs: string[]
    query_intent: {
      original_text: string
      targets: string[]
      requested_predicates: string[]
      comparison_dimensions: string[]
      time_scope: string | null
      evidence_requirements: string[]
      candidate_subquestions: string[]
      search_phrases: string[]
      compiled_queries?: string[]
      query_revision: string
    } | null
    query_intent_model_ref: string | null
    policy_context_ref: string
    capability_envelope_ref: string
    budget_ref: string
  } | null
}

export async function getAgentRuntime(): Promise<AgentRuntimeOverview> {
  const response = await productFetch('/api/v1/agents/runtime?task_limit=72')
  if (!response.ok) throw new Error(`Agent runtime read failed (${response.status})`)
  return response.json() as Promise<AgentRuntimeOverview>
}

export async function getAgentTask(runId: string): Promise<AgentTaskDetail> {
  const response = await productFetch(`/api/v1/tasks/${encodeURIComponent(runId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Task not found' : `Task read failed (${response.status})`)
  return response.json() as Promise<AgentTaskDetail>
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

export async function getAgentLearning(): Promise<AgentLearningOverview> {
  const response = await productFetch('/api/v1/agents/learning')
  if (!response.ok) throw new Error(`Agent learning read failed (${response.status})`)
  return response.json() as Promise<AgentLearningOverview>
}

export async function getAgentSkills(): Promise<ProductSkill[]> {
  const response = await productFetch('/api/v1/agents/skills')
  if (!response.ok) throw new Error(`Agent skills read failed (${response.status})`)
  return response.json() as Promise<ProductSkill[]>
}

export async function getAgentSkill(skillRef: string): Promise<ProductSkill> {
  const response = await productFetch(`/api/v1/agents/skills/${encodeURIComponent(skillRef)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Skill not found' : `Agent skill read failed (${response.status})`)
  return response.json() as Promise<ProductSkill>
}

export async function getAgentExperiences(): Promise<ProductExperience[]> {
  const response = await productFetch('/api/v1/agents/experiences')
  if (!response.ok) throw new Error(`Agent experiences read failed (${response.status})`)
  return response.json() as Promise<ProductExperience[]>
}

export async function getAgentExperience(experienceRef: string): Promise<ProductExperience> {
  const response = await productFetch(`/api/v1/agents/experiences/${encodeURIComponent(experienceRef)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Experience not found' : `Agent experience read failed (${response.status})`)
  return response.json() as Promise<ProductExperience>
}
