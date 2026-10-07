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
  if (!response.ok) throw new Error(response.status === 404 ? 'Document not found' : `Document read failed (${response.status})`)
  return response.json() as Promise<ProductDocument>
}

export async function getDocument(documentId: string): Promise<ProductDocument> {
  const response = await fetch(`/api/v1/documents/${encodeURIComponent(documentId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Document not found' : `Document read failed (${response.status})`)
  return response.json() as Promise<ProductDocument>
}
