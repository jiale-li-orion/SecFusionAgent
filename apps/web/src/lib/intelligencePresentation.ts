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
    const items = claims.filter((claim) => !assigned.has(claim.claim_id) && group.test.test(claim.predicate))
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

const evidenceFields: Record<string, [string, string]> = {
  description_en: ['漏洞说明（英文）', 'Description (English)'], cvss_vector: ['CVSS 攻击向量', 'CVSS vector'], cvss_severity: ['严重等级', 'Severity'], cvss_version: ['CVSS 版本', 'CVSS version'], cvss_score: ['CVSS 评分', 'CVSS score'],
  cwes: ['漏洞类型', 'Weaknesses'], exploit_references: ['利用相关参考', 'Exploitation references'], last_modified: ['最近修改', 'Last modified'], status: ['发布状态', 'Publication status'], published: ['发布时间', 'Published'],
  github_cwes: ['GitHub 漏洞类型', 'GitHub weaknesses'], github_summary: ['GitHub 公告摘要', 'GitHub advisory summary'], github_references: ['GitHub 参考资料', 'GitHub references'], github_description: ['GitHub 公告说明', 'GitHub advisory description'], github_severity: ['GitHub 严重等级', 'GitHub severity'], github_published_at: ['GitHub 发布时间', 'GitHub published'], github_updated_at: ['GitHub 更新时间', 'GitHub updated'],
  epss_percentile: ['EPSS 百分位', 'EPSS percentile'], epss_probability: ['EPSS 利用概率', 'EPSS probability'], kev_vendor_project: ['CISA 厂商或项目', 'CISA vendor or project'], kev_product: ['CISA 产品', 'CISA product'],
  'has-poc': ['利用相关材料', 'Exploitation material'], 'has-weakness': ['漏洞类型关联', 'Weakness association'], 'described-by': ['相关说明文档', 'Supporting document'], 'applicability-status': ['产品适用性', 'Product applicability'],
  known_exploited: ['已知利用情况', 'Known exploitation'], required_action: ['处置要求', 'Required action'],
  date_added: ['收录时间', 'Date added'], ransomware_use: ['勒索软件利用情况', 'Ransomware use'],
  kev_date_added: ['收录时间', 'Date added'], kev_due_date: ['处置截止时间', 'Remediation due date'],
  kev_vulnerability_name: ['漏洞名称', 'Vulnerability name'], kev_ransomware_campaign_use: ['勒索软件利用情况', 'Ransomware use'],
  kev_required_action: ['处置要求', 'Required action'], references: ['参考来源', 'References'],
  severity: ['严重性', 'Severity'], cvss: ['CVSS 评分', 'CVSS score'], affected_versions: ['受影响版本', 'Affected versions'],
  first_fixed_version: ['首个修复版本', 'First fixed version'], description: ['漏洞说明', 'Description'],
}

export function evidenceFieldLabel(label: string, text: (zh: string, en: string) => string) {
  return evidenceFields[label] ? text(...evidenceFields[label]) : label.replaceAll('_', ' ')
}
