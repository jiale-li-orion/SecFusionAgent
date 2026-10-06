import type { QuestionResult } from './api'

export function missionTargetDossierPath(raw: string, requestId: string) {
  const target = parseMissionTarget(raw)
  if (!target) return null
  const params = new URLSearchParams({ from: 'start', request: requestId })
  params.set(target.kind === 'cve' ? 'cve' : 'object', target.value)
  return `/intelligence?${params.toString()}`
}

export function missionTargetEvidencePath(raw: string, evidenceRef: string, requestId: string) {
  const dossier = missionTargetDossierPath(raw, requestId)
  if (!dossier) return null
  const [path, query = ''] = dossier.split('?', 2)
  const params = new URLSearchParams(query)
  params.set('evidence', evidenceRef)
  return `${path}?${params.toString()}`
}

export function compactOutcomeRef(value: string) { return value.length > 26 ? `${value.slice(0, 12)}…${value.slice(-7)}` : value }

export function parseMissionTarget(raw: string): { kind: 'cve' | 'object'; value: string } | null {
  const value = raw.trim()
  if (!value) return null
  const canonical = value.toUpperCase()
  if (/^CVE-\d{4}-\d+$/.test(canonical)) return { kind: 'cve', value: canonical }
  if (/^object:/i.test(value)) {
    const objectId = value.replace(/^object:/i, '').trim()
    if (objectId) return { kind: 'object', value: objectId }
  }
  return null
}

export function originToIntelligence(originRef: string) {
  if (originRef.startsWith('cve:')) return `/intelligence?cve=${encodeURIComponent(originRef.slice(4))}`
  if (originRef.startsWith('object:')) return `/intelligence?object=${encodeURIComponent(originRef.slice(7))}`
  if (originRef.startsWith('incident:')) return `/intelligence?incident=${encodeURIComponent(originRef.slice(9))}`
  return '/intelligence'
}

export function modeTitleEn(id: string) {
  return ({ DIRECT: 'QUICK ANSWER', RETRIEVE: 'EVIDENCE RETRIEVAL', VERIFY: 'TARGETED VERIFICATION', INVESTIGATE: 'DEEP INVESTIGATION', WATCH: 'CONTINUOUS WATCH' } as Record<string, string>)[id] ?? id
}

export function modeDescriptionEn(id: string) {
  return ({
    DIRECT: 'Current Evidence World is sufficient. ORACLE closes directly from the bounded context.',
    RETRIEVE: 'Expand the local retrieval window and bring additional Evidence into the current context.',
    VERIFY: 'Open a durable Case around version, fix-boundary, applicability, or source conflict; ARGUS advances by EvidenceNeed.',
    INVESTIGATE: 'Enter multi-step execution where Skill, Capability, and delegated Enrichment follow task state.',
    WATCH: 'Keep the Case waiting and resume a new episode when the external world or a dependency changes.',
  } as Record<string, string>)[id] ?? id
}

export function summarizeDecision(result: QuestionResult) {
  const decision = result.decision
  if (!decision) return 'Decision returned.'
  const answerItems = Object.entries(decision.answer ?? {}).slice(0, 4)
  if (answerItems.length) return answerItems.map(([key, value]) => `${key}: ${formatDecisionAnswerValue(value)}`).join(' · ')
  const conclusion = decision.conclusions?.[0]?.statement
  if (conclusion) return conclusion
  return `Decision ${decision.decision_id ?? ''} completed.`
}

export function formatDecisionAnswerValue(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}
