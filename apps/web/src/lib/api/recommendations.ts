import type { EvidenceRef } from './intelligence'
import { productFetch, productHeaders } from './request'

export type FollowedIntelligenceObject = {
  object_id: string
  object_type: string
  canonical_key: string
  label: string
}

export type IntelligencePreferences = {
  keywords: string[]
  target_object_ids: string[]
  target_objects: FollowedIntelligenceObject[]
  updated_at: string | null
}

export type IntelligenceRecommendation = {
  object_id: string
  object_type: string
  canonical_key: string
  label: string
  score: number
  feedback: 'interested' | null
  reasons: Array<{
    kind: 'keyword' | 'followed_object' | 'related_object' | 'interested'
    value: string
    label: string
    weight: number
    relation_id?: string | null
    evidence_refs: string[]
  }>
  evidence: EvidenceRef[]
  created_revision: number
}

export type IntelligenceRecommendationPage = {
  generated_at: string
  knowledge_revision: number
  preferences_updated_at: string | null
  items: IntelligenceRecommendation[]
  candidate_limit: number
}

async function recommendationRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await productFetch(`/api/v1/intelligence/${path}`, {
    method: body === undefined ? 'GET' : 'PUT',
    headers: productHeaders(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(problem?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function getIntelligencePreferences(): Promise<IntelligencePreferences> {
  return recommendationRequest('preferences')
}

export function saveIntelligencePreferences(input: {
  keywords: string[]
  target_object_ids: string[]
}): Promise<IntelligencePreferences> {
  return recommendationRequest('preferences', input)
}

export function getIntelligenceRecommendations(limit = 5): Promise<IntelligenceRecommendationPage> {
  return recommendationRequest(`recommendations?${new URLSearchParams({ limit: String(limit) })}`)
}

export function saveIntelligenceRecommendationFeedback(
  objectId: string,
  feedback: 'interested' | 'ignored' | 'neutral',
): Promise<{ object_id: string; feedback: 'interested' | 'ignored' | 'neutral'; updated_at: string }> {
  return recommendationRequest(`recommendations/${encodeURIComponent(objectId)}/feedback`, { feedback })
}
