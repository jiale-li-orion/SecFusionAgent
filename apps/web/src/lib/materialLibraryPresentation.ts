import type { LibraryFacet, LibraryMaterial } from './api/library'
import { clusterLibraryMaterials, type MaterialCluster } from './libraryPresentation'

export const LIBRARY_PAGE_SIZE = 48
const specificSubjects = ['prompt-injection', 'runtime-containment', 'agent-memory', 'rag-retrieval', 'identity-access', 'supply-chain', 'training-poisoning', 'privacy-leakage', 'jailbreak', 'model-evaluation', 'inference-infrastructure', 'vulnerability-exploit', 'ai-governance', 'incident-response', 'agent-safety']

/** Clustering stays bounded to one fetched page; facet names label, never decide, its groups. */
export function clusterMaterialPage(items: LibraryMaterial[], facets: LibraryFacet[]): MaterialCluster[] {
  const page = items.slice(0, LIBRARY_PAGE_SIZE)
  const byId = new Map(page.map(item => [item.story_id, item]))
  return clusterLibraryMaterials(page).map(cluster => {
    if (cluster.items.length < 2) return cluster
    const shared = specificSubjects.find(key => cluster.items.every(item => byId.get(item.story_id)?.subjects.includes(key)))
    const facet = facets.find(item => item.key === shared)
    return facet ? { ...cluster, zh: facet.label, en: facet.label_en } : cluster
  })
}
