import type { EvidenceRef } from './intelligence'

export type NetworkNode = {
  object_id: string
  object_type: string
  label: string
  canonical_key: string
  created_revision: number
  created_at: string | null
  evidence_ref?: string | null
  canonical_object_id?: string | null
  event_time?: string | null
}
export type NetworkEdge = {
  relation_id: string
  source_id: string
  target_id: string
  relation_type: string
  origin: string
  qualifier: Record<string, unknown>
  created_revision: number
  superseded_revision: number | null
  created_at: string | null
  superseded_at: string | null
  evidence: EvidenceRef[]
}
export type KnowledgeNetwork = {
  center_id: string
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  snapshot_revision: number
  next_cursor: string | null
  remaining_count: number
  history_scope: string
  revision_domain?: string
}
export async function getKnowledgeNetwork(objectId: string, options: {
  limit?: number; focusId?: string; existingIds?: string[]; cursor?: string; revision?: number
} = {}, signal?: AbortSignal, incident = false): Promise<KnowledgeNetwork> {
  const params = new URLSearchParams({ limit: String(options.limit ?? 40) })
  if (options.focusId) params.set('focus_id', options.focusId)
  if (options.existingIds?.length) params.set('existing_ids', options.existingIds.join(','))
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.revision != null) params.set('revision', String(options.revision))
  const response = await fetch(`/api/v1/${incident ? 'incidents' : 'intelligence/objects'}/${encodeURIComponent(objectId)}/network?${params}`, { signal })
  if (!response.ok) throw new Error(response.status === 404 ? '对象尚无关系记录' : `关系网络读取失败 (${response.status})`)
  return response.json() as Promise<KnowledgeNetwork>
}
