import type { HotBug, WorldStory } from './api/world'

export function projectHot(item: HotBug): WorldStory {
  return {
    story_id: `hot:${item.source_id}:${item.external_object_id}`, category: 'vulnerability',
    kind: 'HotVulnerability', headline: item.title ?? item.cve_id ?? item.external_object_id,
    excerpt: item.description, excerpt_origin: 'source_field', published_at: null,
    happened_at: item.updated_at ?? item.fetched_at, observed_at: item.fetched_at,
    source_id: item.source_id, source_name: item.source_name ?? item.source_id, object_id: null, incident_id: null,
    external_ref: item.canonical_url, evidence: null,
    facts: { cve_id: item.cve_id, external_object_id: item.external_object_id, affected_products: item.affected_products, changed_fields: item.changed_fields, external_revision: item.external_revision, active: item.active, pinned: item.pinned, priority_signals: item.priority_signals, access_count: item.access_count, ttl_seconds: item.ttl_seconds },
  }
}
