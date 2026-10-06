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

export async function getSystemOverview(): Promise<SystemOverview> {
  const response = await fetch('/api/v1/observatory/system')
  if (!response.ok) throw new Error(`System overview unavailable (${response.status})`)
  return response.json() as Promise<SystemOverview>
}
