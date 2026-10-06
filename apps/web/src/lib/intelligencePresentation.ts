import type { KnowledgeClaim, KnowledgeRelation } from './api/intelligence'

export function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

export function evidenceProvenanceClass(role: string, sourceClass: string) {
  const value = (role + ' ' + sourceClass).toLowerCase()
  if (/authority|primary|official|vendor/.test(value)) return 'provenance-authority'
  if (/forensic|incident|telemetry|asset/.test(value)) return 'provenance-forensic'
  if (/reference|normative|academic|research/.test(value)) return 'provenance-reference'
  if (/signal|independent|osint/.test(value)) return 'provenance-signal'
  return 'provenance-general'
}

export function evidenceProvenanceLabel(role: string, sourceClass: string) {
  const cls = evidenceProvenanceClass(role, sourceClass)
  if (cls === 'provenance-authority') return 'AUTHORITATIVE TESTIMONY'
  if (cls === 'provenance-forensic') return 'FORENSIC OBSERVATION'
  if (cls === 'provenance-reference') return 'REFERENCE RECORD'
  if (cls === 'provenance-signal') return 'CORROBORATING SIGNAL'
  return 'EVIDENCE RECORD'
}

export function countEvidence(claims: KnowledgeClaim[], relations: KnowledgeRelation[]) {
  return new Set([...claims.flatMap((item) => item.evidence.map((e) => e.evidence_ref)), ...relations.flatMap((item) => item.evidence.map((e) => e.evidence_ref))]).size
}

export function groupClaims(claims: KnowledgeClaim[]) {
  const groups = [
    { title: 'IDENTITY & SEVERITY', test: /status|title|description|cvss|severity|weakness|cwe/i },
    { title: 'AFFECTED & FIX', test: /affected|product|package|version|fix|remediation/i },
    { title: 'EXPLOIT & LIKELIHOOD', test: /exploit|epss|kev|poc|likelihood/i },
    { title: 'SOURCE & TIMELINE', test: /published|modified|assigner|reference|advisory/i },
  ]
  const assigned = new Set<string>()
  const result = groups.map((group) => {
    const items = claims.filter((claim) => group.test.test(claim.predicate))
    items.forEach((claim) => assigned.add(claim.claim_id))
    return { title: group.title, claims: items }
  }).filter((group) => group.claims.length)
  const other = claims.filter((claim) => !assigned.has(claim.claim_id))
  if (other.length) result.push({ title: 'OTHER CANONICAL FACTS', claims: other })
  return result
}

export function humanize(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ').toUpperCase() }
export function formatDate(value: string) { return new Date(value).toLocaleString() }
export function formatLocator(value: Record<string, unknown>) { return Object.entries(value).map(([key, val]) => `${key}=${formatValue(val)}`).join(' · ') || 'root' }
export function formatValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(formatValue).join(' · ')
  try { return JSON.stringify(value) } catch { return String(value) }
}
