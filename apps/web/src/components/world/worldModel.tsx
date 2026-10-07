import { Boxes, Bug, Building2, Code2, FileBadge, GraduationCap, RadioTower, ShieldAlert } from 'lucide-react'

import type { HotBug } from '../../lib/api'

export const sources = [
  { key: 'vulnerability', label: 'VULNERABILITY', labelZh: '漏洞', sub: 'CVE · NVD · KEV', icon: Bug, x: 6.5, y: 19 },
  { key: 'vendor', label: 'VENDOR', labelZh: '厂商', sub: 'Advisory · PSIRT', icon: Building2, x: 5.5, y: 42 },
  { key: 'development', label: 'DEVELOPMENT', labelZh: '开发', sub: 'Git · Package · Release', icon: Code2, x: 10, y: 67 },
  { key: 'academic', label: 'ACADEMIC', labelZh: '学术', sub: 'Paper · Preprint', icon: GraduationCap, x: 25, y: 83 },
  { key: 'independent', label: 'INDEPENDENT', labelZh: '独立情报', sub: 'OSINT · Analysis', icon: RadioTower, x: 49, y: 88 },
  { key: 'normative', label: 'NORMATIVE', labelZh: '规范', sub: 'Standard · Regulation', icon: FileBadge, x: 70, y: 83 },
  { key: 'assets', label: 'ASSETS', labelZh: '资产', sub: 'Exposure · Inventory', icon: Boxes, x: 75, y: 68 },
  { key: 'incidents', label: 'INCIDENTS', labelZh: '事件', sub: 'Report · Signal', icon: ShieldAlert, x: 75, y: 20 },
]

export const worldWindows = ['1h', '6h', '24h', '168h'] as const
export type WorldWindow = (typeof worldWindows)[number]

export const worldLanePoints: Record<string, { x: number; y: number }> = {
  'BUG STREAM': { x: 35, y: 34 },
  'DEVELOPMENT INDEX': { x: 42, y: 27 },
  'INSIGHT CORPUS': { x: 52, y: 24 },
  'INCIDENT WATCH': { x: 65, y: 32 },
  'ASSET OBSERVATION': { x: 68, y: 66 },
}

export const sourceNarrative: Record<string, { lane: string; role: string; roleZh: string; summary: string; summaryZh: string }> = {
  vulnerability: { lane: 'BUG STREAM', role: 'deterministic + canonical identity', roleZh: '确定性抽取 + 规范身份', summary: 'CVE / NVD / KEV form the vulnerability spine and feed normalized security facts into the durable world.', summaryZh: 'CVE / NVD / KEV 构成漏洞主干，规范化安全事实持续进入 durable world。' },
  development: { lane: 'DEVELOPMENT INDEX', role: 'graph + fix intelligence', roleZh: '关系图谱 + 修复情报', summary: 'Repository, release and package evidence expands fix, version and development relationships.', summaryZh: '仓库、Release 与 Package 证据扩展修复、版本和开发关系。' },
  academic: { lane: 'INSIGHT CORPUS', role: 'semantic enrichment', roleZh: '语义增强', summary: 'Papers and research signals add analytical context without overriding authoritative source facts.', summaryZh: '论文与研究信号补充分析上下文，同时保留权威来源的事实边界。' },
  vendor: { lane: 'BUG STREAM', role: 'primary advisory authority', roleZh: '一手厂商权威', summary: 'Vendor advisories provide product, remediation and fix-boundary evidence with source authority kept visible.', summaryZh: '厂商通告提供产品、修复与 fix boundary 证据，并保留来源权威性。' },
  independent: { lane: 'INSIGHT CORPUS', role: 'secondary analysis', roleZh: '独立二手分析', summary: 'Independent analysis contributes supporting observations and cross-source context.', summaryZh: '独立分析提供辅助观察与跨来源上下文。' },
  normative: { lane: 'INSIGHT CORPUS', role: 'standards / normative context', roleZh: '标准 / 规范上下文', summary: 'Standards and normative documents contribute constrained policy and technical context.', summaryZh: '标准与规范文档补充受约束的政策和技术上下文。' },
  assets: { lane: 'ASSET OBSERVATION', role: 'applicability / exposure', roleZh: '适用性 / 暴露面', summary: 'Observed assets bind canonical product/version facts to deployment applicability through an on-demand side path.', summaryZh: '资产观测把规范化产品/版本事实绑定到真实部署适用性与暴露面。' },
  incidents: { lane: 'INCIDENT WATCH', role: 'signal → candidate → durable incident', roleZh: '信号 → 候选 → 持久事件', summary: 'Incident signals remain provisional until evidence is strong enough to enter the durable Incident world.', summaryZh: '事件信号先保持候选态，证据满足强锚点条件后进入 durable Incident。' },
}

export function supportsWebGL() {
  if (typeof document === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

export function sourceState(health: { healthy: number; degraded: number; blocked: number } | undefined) {
  if (!health) return 'unknown'
  const total = health.healthy + health.degraded + health.blocked
  if (total > 0 && health.blocked === total) return 'blocked'
  if (health.degraded > 0 || health.blocked > 0) return 'degraded'
  if (health.healthy > 0) return 'healthy'
  return 'unknown'
}

export function laneClass(source: (typeof sources)[number] | null, focusedLane: string | null, lane: string) {
  if (focusedLane) return focusedLane === lane ? 'active selected' : 'dimmed'
  if (!source) return ''
  return sourceNarrative[source.key]?.lane === lane ? 'active' : 'dimmed'
}

export function laneSlug(lane: string) {
  if (lane === 'BUG STREAM') return 'lane-bug'
  if (lane === 'DEVELOPMENT INDEX') return 'lane-development'
  if (lane === 'INSIGHT CORPUS') return 'lane-insight'
  if (lane === 'INCIDENT WATCH') return 'lane-incident'
  return 'lane-assets'
}

export function hotIdentity(item: HotBug) {
  return `${item.source_id}:${item.external_object_id}`
}

export function parseHotIdentity(value: string | null) {
  if (!value) return null
  const separator = value.indexOf(':')
  if (separator <= 0 || separator >= value.length - 1) return null
  return {
    sourceId: value.slice(0, separator),
    externalObjectId: value.slice(separator + 1),
  }
}

export function snapshotAge(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}
