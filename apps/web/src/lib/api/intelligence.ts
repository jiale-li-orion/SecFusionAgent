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
