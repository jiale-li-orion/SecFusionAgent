export const observatoryWindows = ['1h', '6h', '24h', '168h'] as const
export type ObservatoryWindow = (typeof observatoryWindows)[number]

import type { CompetitionProof, ProofMetricObservation, ProofRunDetail } from './api'

export function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

export function proofTargetPath(ref: string, runId: string, caseRunId: string) {
  const base = { from: 'proof', proofRun: runId, caseRun: caseRunId }
  if (ref.startsWith('cve:')) return `/intelligence?${new URLSearchParams({ ...base, cve: ref.slice(4) }).toString()}`
  if (ref.startsWith('knowledge-key:cve:')) return `/intelligence?${new URLSearchParams({ ...base, cve: ref.slice('knowledge-key:cve:'.length) }).toString()}`
  if (ref.startsWith('object:')) return `/intelligence?${new URLSearchParams({ ...base, object: ref.slice(7) }).toString()}`
  if (ref.startsWith('incident:')) return `/intelligence?${new URLSearchParams({ ...base, incident: ref.slice(9) }).toString()}`
  return null
}

export function proofTargetLabel(ref: string) {
  if (ref.startsWith('cve:') || ref.startsWith('knowledge-key:cve:')) return 'CVE DOSSIER'
  if (ref.startsWith('object:')) return 'OBJECT DOSSIER'
  if (ref.startsWith('incident:')) return 'INCIDENT DOSSIER'
  return 'TARGET'
}

export function proofRefKind(ref: string) {
  const [kind] = ref.split(':', 1)
  return kind?.replaceAll('-', ' ').toUpperCase() || 'FROZEN REF'
}

export function pairRunMetrics(left: ProofRunDetail, right: ProofRunDetail) {
  const leftCaseRefs = new Map(left.cases.map((item) => [item.case_run_id, item.case_ref]))
  const rightCaseRefs = new Map(right.cases.map((item) => [item.case_run_id, item.case_ref]))
  const rightIndex = new Map<string, ProofMetricObservation>()
  for (const metric of right.metrics) {
    const caseRef = rightCaseRefs.get(metric.case_run_id)
    if (!caseRef) continue
    rightIndex.set(`${caseRef}\u0000${metric.metric_name}\u0000${metric.measurement_source}`, metric)
  }

  return left.metrics.flatMap((metric) => {
    const caseRef = leftCaseRefs.get(metric.case_run_id)
    if (!caseRef) return []
    const key = `${caseRef}\u0000${metric.metric_name}\u0000${metric.measurement_source}`
    const matched = rightIndex.get(key)
    if (!matched || matched.unit !== metric.unit) return []
    return [{ key, caseRef, left: metric, right: matched, delta: matched.value - metric.value }]
  }).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.left.metric_name.localeCompare(b.left.metric_name))
}

export function compactCoordinate(value: string) {
  return value.length > 34 ? `${value.slice(0, 15)}…${value.slice(-11)}` : value
}

export function formatObservedMetric(metric: ProofMetricObservation) {
  if (metric.unit === 'ratio') return pct(metric.value)
  if (metric.unit === 'seconds') return `${metric.value.toFixed(metric.value < 10 ? 3 : 2)}s`
  return `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ''}`
}

export function formatMetricDelta(value: number, unit: string | null) {
  if (Math.abs(value) < 1e-12) return 'Δ 0'
  const sign = value > 0 ? '+' : '−'
  const magnitude = Math.abs(value)
  if (unit === 'ratio') return `Δ ${sign}${(magnitude * 100).toFixed(2)}pp`
  if (unit === 'seconds') return `Δ ${sign}${magnitude.toFixed(magnitude < 10 ? 3 : 2)}s`
  return `Δ ${sign}${formatNumber(magnitude)}${unit ? ` ${unit}` : ''}`
}

export function linePath(values: number[], width: number, height: number, max: number) { if (!values.length) return ''; if (values.length === 1) return `M 0 ${height - values[0] / max * height}`; return values.map((value, index) => `${index ? 'L' : 'M'} ${(index / (values.length - 1)) * width} ${height - Math.min(value / max, 1) * (height - 10) - 5}`).join(' ') }

export function numeric(value: number | string | null | undefined) { return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) || 0 : 0 }

export function seconds(value: number | null | undefined) { return value == null ? '—' : value < 1 ? `${(value * 1000).toFixed(0)}ms` : `${value.toFixed(value < 10 ? 2 : 1)}s` }

export function pct(value: number) { return `${(value * 100).toFixed(value >= .995 ? 0 : 1)}%` }

export function compactNumber(value: number) { return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) }

export function bytes(value: number) { return value < 1024 ? `${value} B` : value < 1024 ** 2 ? `${(value / 1024).toFixed(1)} KiB` : `${(value / 1024 ** 2).toFixed(1)} MiB` }

export function formatNumber(value: number) { return Math.abs(value) < 10 ? value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') : value.toFixed(0) }

export function proofMetric(metric: CompetitionProof['headline_metrics'][number] | undefined) { if (!metric) return '—'; if (metric.unit === 'ratio') return pct(metric.value); if (metric.unit === 'seconds') return `${metric.value.toFixed(3)}s`; return `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ''}` }

export function rawMetric(metric: CompetitionProof['headline_metrics'][number] | undefined) { return metric ? formatNumber(metric.value) : '—' }

export function snapshotAge(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); if (seconds < 60) return `${seconds}s ago`; const minutes = Math.floor(seconds / 60); if (minutes < 60) return `${minutes}m ago`; const hours = Math.floor(minutes / 60); return hours < 48 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago` }
