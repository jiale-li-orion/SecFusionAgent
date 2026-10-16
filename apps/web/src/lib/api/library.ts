import type { WorldStory } from './world'

export type LibraryFacet = { key: string; label: string; label_en: string; count: number }
export type LibraryMaterial = WorldStory & { subjects: string[] }
export type MaterialLibraryResponse = {
  items: LibraryMaterial[]; total: number; corpus_total: number; offset: number
  next_offset: number | null; limit: number; as_of: string
  categories: LibraryFacet[]; sources: LibraryFacet[]; subjects: LibraryFacet[]
}
export async function getMaterialLibrary(filters: { offset: number; limit?: number; asOf?: string; category?: string; source?: string; subject?: string; query?: string }, signal?: AbortSignal): Promise<MaterialLibraryResponse> {
  const params = new URLSearchParams({ limit: String(filters.limit ?? 48), offset: String(filters.offset) })
  for (const [key, value] of Object.entries({ as_of: filters.asOf, category: filters.category, source: filters.source, subject: filters.subject, q: filters.query })) if (value) params.set(key, value)
  const response = await fetch(`/api/v1/intelligence/library?${params}`, { signal })
  if (!response.ok) throw new Error(`Material library read failed (${response.status})`)
  return response.json() as Promise<MaterialLibraryResponse>
}
