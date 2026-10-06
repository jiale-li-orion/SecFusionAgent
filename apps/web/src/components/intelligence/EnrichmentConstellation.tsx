import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'

import { type IntelligenceEnrichmentState, type KnowledgeClaim } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

const enrichmentDimensions = [
  { key: 'identity', label: 'IDENTITY', test: /title|description|status|assigner|identifier|cve/i },
  { key: 'severity', label: 'SEVERITY', test: /cvss|severity|score/i },
  { key: 'weakness', label: 'WEAKNESS', test: /weakness|cwe/i },
  { key: 'product_package', label: 'PRODUCT / PACKAGE', test: /product|package|vendor|component/i },
  { key: 'version_applicability', label: 'VERSION APPLICABILITY', test: /version|affected|not_affected|fixed|under_investigation|applicab/i },
  { key: 'fix_remediation', label: 'FIX / REMEDIATION', test: /fix|remediation|patch|upgrade|commit/i },
  { key: 'exploit_state', label: 'EXPLOIT STATE', test: /exploit|kev|poc|weapon/i },
  { key: 'exploit_likelihood', label: 'EXPLOIT LIKELIHOOD', test: /epss|likelihood|probab/i },
  { key: 'advisory_reference', label: 'ADVISORY / REFERENCE', test: /advisory|reference|url|bulletin/i },
  { key: 'asset_exposure', label: 'ASSET EXPOSURE', test: /asset|exposure|internet|deployment/i },
  { key: 'research_paper', label: 'RESEARCH / PAPER', test: /research|paper|academic|publication/i },
  { key: 'incident_context', label: 'INCIDENT CONTEXT', test: /incident|campaign|attack|observed_in_the_wild/i },
] as const

type EnrichmentVisualStatus = IntelligenceEnrichmentState['dimensions'][number]['status'] | 'unavailable'

export function EnrichmentConstellation({ claims, cveId, state, stateLoading, stateError }: { claims: KnowledgeClaim[]; cveId: string; state: IntelligenceEnrichmentState | null; stateLoading: boolean; stateError: boolean }) {
  const { text } = useI18n()
  const [focusedDimension, setFocusedDimension] = useState<string | null>(null)
  const stateByDimension = new Map(state?.dimensions.map((item) => [item.dimension, item]) ?? [])
  const dimensions = enrichmentDimensions.map((dimension, index) => {
    const matchedClaims = claims.filter((claim) => dimension.test.test(claim.predicate))
    const authoritativeState = stateByDimension.get(dimension.key)
    const status: EnrichmentVisualStatus = authoritativeState?.status ?? 'unavailable'
    const angle = -Math.PI / 2 + (index / enrichmentDimensions.length) * Math.PI * 2
    return {
      ...dimension,
      status,
      authoritativeState,
      matchedClaims,
      x: 50 + Math.cos(angle) * 40,
      y: 50 + Math.sin(angle) * 37,
    }
  })
  const counts = dimensions.reduce<Record<EnrichmentVisualStatus, number>>((acc, item) => {
    acc[item.status] += 1
    return acc
  }, { resolved: 0, conflict: 0, unknown: 0, missing: 0, unavailable: 0 })
  const focused = dimensions.find((item) => item.key === focusedDimension) ?? null

  return (
    <section className={`enrichment-constellation ${focused ? 'dimension-focused' : ''}`}>
      <div className="enrichment-head">
        <div><small>ENRICHMENT-V1</small><strong>12-DIMENSION EVIDENCE CONSTELLATION</strong></div>
        <span>{stateLoading
          ? text('解析权威 enrichment state…', 'resolving authoritative enrichment state…')
          : stateError || !state
            ? text('四态 read 不可用 · 不从 Claim 数量推断', 'four-state read unavailable · claim counts are not used as status')
            : `${counts.resolved} resolved · ${counts.conflict} conflict · ${counts.unknown} unknown · ${counts.missing} missing`}</span>
      </div>
      <div className="enrichment-orbit">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {dimensions.map((item) => (
            <line
              key={item.key}
              className={`status-${item.status}`}
              x1="50"
              y1="50"
              x2={item.x}
              y2={item.y}
            />
          ))}
        </svg>
        <button className="enrichment-core" onClick={() => setFocusedDimension(null)}>
          <small>CANONICAL</small>
          <strong>{focused ? focused.label : cveId}</strong>
          <span>{focused ? enrichmentStatusLabel(focused.status, text) : state ? `WORLD REV ${state.world_revision}` : text(`${claims.length} 条可见 Claims`, `${claims.length} visible claims`)}</span>
        </button>
        {dimensions.map((item, index) => (
          <motion.button
            key={item.key}
            className={`enrichment-dimension status-${item.status} ${focusedDimension === item.key ? 'selected' : ''} ${focused && focusedDimension !== item.key ? 'dimmed' : ''}`}
            style={{ left: `${item.x}%`, top: `${item.y}%` }}
            onClick={() => setFocusedDimension((current) => current === item.key ? null : item.key)}
            initial={{ opacity: 0, scale: .82 }}
            animate={{ opacity: focused && focusedDimension !== item.key ? .18 : 1, scale: focusedDimension === item.key ? 1.08 : 1 }}
            transition={{ delay: index * .025 }}
          >
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{item.label}</strong>
            <small>{enrichmentStatusLabel(item.status, text)}</small>
          </motion.button>
        ))}
        <AnimatePresence>
          {focused && (
            <motion.aside
              className="enrichment-dimension-lens"
              initial={{ opacity: 0, x: 18 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 12 }}
            >
              <small>{focused.key.toUpperCase()} / ENRICHMENT DIMENSION</small>
              <strong>{focused.label}</strong>
              <span>{enrichmentStatusLabel(focused.status, text)} · {focused.authoritativeState ? `REV ${focused.authoritativeState.world_revision}` : 'STATE UNAVAILABLE'}</span>
              <div>
                {focused.matchedClaims.slice(0, 4).map((claim) => (
                  <p key={claim.claim_id}><b>{humanize(claim.predicate)}</b>{formatValue(claim.value)}</p>
                ))}
                {focused.matchedClaims.length === 0 && <p><b>{enrichmentStatusLabel(focused.status, text)}</b>{enrichmentStatusExplanation(focused.status, text)}</p>}
                {focused.authoritativeState?.conflict_refs.length ? <p><b>CONFLICT REFS</b>{focused.authoritativeState.conflict_refs.join(' · ')}</p> : null}
                {focused.authoritativeState?.attempted_operator_refs.length ? <p><b>ATTEMPTED OPERATORS</b>{focused.authoritativeState.attempted_operator_refs.join(' · ')}</p> : null}
                {focused.authoritativeState?.blocked_attempt_refs.length ? <p><b>BLOCKED ATTEMPTS</b>{focused.authoritativeState.blocked_attempt_refs.join(' · ')}</p> : null}
              </div>
              <em>{text('再次点击该维度以退出聚焦', 'CLICK DIMENSION AGAIN TO RELEASE FOCUS')}</em>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}


function enrichmentStatusLabel(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'resolved') return text('已解析', 'RESOLVED')
  if (status === 'conflict') return text('冲突', 'CONFLICT')
  if (status === 'unknown') return text('明确未知', 'EXPLICIT UNKNOWN')
  if (status === 'missing') return text('缺失', 'MISSING')
  return text('状态不可用', 'STATE UNAVAILABLE')
}

function enrichmentStatusExplanation(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'unknown') return text('权威查询或成功 operator 已明确返回未知；这与尚未获取证据不同。', 'An authoritative lookup or successful operator explicitly returned unknown; this differs from missing evidence.')
  if (status === 'missing') return text('当前 world revision 没有满足该维度 completion predicate 的 canonical fact。', 'No canonical fact satisfies this dimension completion predicate at the current world revision.')
  if (status === 'conflict') return text('当前 canonical facts 形成互不相容的值或适用性状态，冲突被保留。', 'Current canonical facts contain incompatible values or applicability states; the conflict is preserved.')
  if (status === 'resolved') return text('当前 world revision 已有满足 completion predicate 的 canonical fact。', 'A canonical fact satisfies the completion predicate at the current world revision.')
  return text('权威 enrichment state read 当前不可用；页面不从可见 Claim 数量推断状态。', 'The authoritative enrichment-state read is unavailable; the UI does not infer status from visible claim count.')
}

function humanize(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ').toUpperCase() }
function formatValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(formatValue).join(' · ')
  try { return JSON.stringify(value) } catch { return String(value) }
}
