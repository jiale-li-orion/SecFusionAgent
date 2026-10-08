import { productFetch, productHeaders } from './request'

export type ProductEnrichmentRun = {
  object_id: string
  cve_id: string
  task_run_id: string
  role_id: string
  execution_profile: string
  status: string
  required_dimensions: string[]
  stop_reason: string | null
  task_url: string
  state_url: string
  replayed: boolean
}

export async function startProductEnrichment(
  objectId: string,
  input: { dimensions: string[]; expected_world_revision?: number },
  idempotencyKey: string,
): Promise<ProductEnrichmentRun> {
  const response = await productFetch(
    `/api/v1/intelligence/objects/${encodeURIComponent(objectId)}/enrichment/runs`,
    {
      method: 'POST',
      headers: productHeaders({ 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey }),
      body: JSON.stringify(input),
    },
  )
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { detail?: string; code?: string } | null
    throw new Error(problem?.code === 'revision_conflict'
      ? 'REVISION_CHANGED'
      : problem?.detail ?? `Enrichment request failed (${response.status})`)
  }
  return response.json() as Promise<ProductEnrichmentRun>
}

export async function listProductEnrichmentRuns(objectId: string): Promise<{ items: ProductEnrichmentRun[] }> {
  const response = await productFetch(
    `/api/v1/intelligence/objects/${encodeURIComponent(objectId)}/enrichment/runs`,
    { headers: productHeaders() },
  )
  if (!response.ok) throw new Error(`Enrichment tasks read failed (${response.status})`)
  return response.json() as Promise<{ items: ProductEnrichmentRun[] }>
}
