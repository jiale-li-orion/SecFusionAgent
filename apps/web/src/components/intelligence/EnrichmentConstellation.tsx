import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'

import { type IntelligenceEnrichmentState, type KnowledgeRelation, type KnowledgeClaim } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

const enrichmentDimensions = [
  { key: 'identity', label: 'Identity', zh: '漏洞身份' },
  { key: 'severity', label: 'Severity', zh: '严重性' },
  { key: 'weakness', label: 'Weakness', zh: '漏洞类型' },
  { key: 'product_package', label: 'Product / package', zh: '产品与软件包' },
  { key: 'version_applicability', label: 'Version applicability', zh: '版本适用性' },
  { key: 'fix_remediation', label: 'Fix / remediation', zh: '修复与缓解' },
  { key: 'exploit_state', label: 'Exploit state', zh: '公开利用证据' },
  { key: 'exploit_likelihood', label: 'Exploit likelihood', zh: '利用可能性' },
  { key: 'advisory_reference', label: 'Advisory / reference', zh: '公告与参考资料' },
  { key: 'asset_exposure', label: 'Asset exposure', zh: '资产暴露' },
  { key: 'research_paper', label: 'Research / paper', zh: '相关研究' },
  { key: 'incident_context', label: 'Incident context', zh: '事件背景' },
] as const

type EnrichmentVisualStatus = IntelligenceEnrichmentState['dimensions'][number]['status'] | 'not_materialized'

export function EnrichmentConstellation({ claims, relations, cveId, state, stateLoading, stateError, onEvidence }: { claims: KnowledgeClaim[]; relations: KnowledgeRelation[]; cveId: string; state: IntelligenceEnrichmentState | null; stateLoading: boolean; stateError: boolean; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const reduceMotion = Boolean(useReducedMotion())
  const [focusedDimension, setFocusedDimension] = useState<string | null>(null)
  const stateByDimension = new Map(state?.dimensions.map((item) => [item.dimension, item]) ?? [])
  const dimensions = enrichmentDimensions.map((dimension, index) => {
    const authoritativeState = stateByDimension.get(dimension.key)
    const factRefs = new Set(authoritativeState?.accepted_fact_refs ?? [])
    const matchedClaims = claims.filter(claim => factRefs.has(`claim:${claim.claim_id}`))
    const matchedRelations = relations.filter(relation => factRefs.has(`relation:${relation.relation_id}`))
    const status: EnrichmentVisualStatus = authoritativeState?.status ?? 'not_materialized'
    const angle = -Math.PI / 2 + (index / enrichmentDimensions.length) * Math.PI * 2
    return {
      ...dimension,
      status,
      authoritativeState,
      matchedClaims,
      matchedRelations,
      x: 50 + Math.cos(angle) * 40,
      y: 50 + Math.sin(angle) * 37,
    }
  })
  const counts = dimensions.reduce<Record<EnrichmentVisualStatus, number>>((acc, item) => {
    acc[item.status] += 1
    return acc
  }, { resolved: 0, conflict: 0, unknown: 0, missing: 0, not_materialized: 0 })
  const focused = dimensions.find((item) => item.key === focusedDimension) ?? null

  return (
    <section className={`enrichment-constellation ${focused ? 'dimension-focused' : ''}`}>
      <div className="enrichment-head">
        <div><small>{text('证据补全', 'EVIDENCE COVERAGE')}</small><strong>{text('围绕漏洞，已经知道什么', 'What we know about this vulnerability')}</strong></div>
        <span>{stateLoading
          ? text('正在读取证据覆盖…', 'Loading evidence coverage…')
          : stateError
            ? text('暂时无法读取维度状态', 'Dimension states are temporarily unavailable')
            : !state
              ? text('正在整理这个对象的证据', 'Organizing evidence for this object')
            : text(`${counts.resolved} 已有证据 · ${counts.conflict} 冲突 · ${counts.unknown} 未知 · ${counts.missing} 待补全`, `${counts.resolved} supported · ${counts.conflict} conflict · ${counts.unknown} unknown · ${counts.missing} missing`)}</span>
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
          <small>{text('漏洞档案', 'VULNERABILITY')}</small>
          <strong>{focused ? text(focused.zh, focused.label) : cveId}</strong>
          <span>{focused ? enrichmentStatusLabel(focused.status, text) : text('选择维度，查看事实与来源', 'Select a dimension for facts and sources')}</span>
        </button>
        {dimensions.map((item, index) => (
          <motion.button
            key={item.key}
            className={`enrichment-dimension status-${item.status} ${focusedDimension === item.key ? 'selected' : ''} ${focused && focusedDimension !== item.key ? 'dimmed' : ''}`}
            style={{ left: `${item.x}%`, top: `${item.y}%` }}
            onClick={() => setFocusedDimension((current) => current === item.key ? null : item.key)}
            initial={reduceMotion ? false : { opacity: 0, scale: .82 }}
            animate={{ opacity: focused && focusedDimension !== item.key ? .18 : 1, scale: focusedDimension === item.key ? 1.08 : 1 }}
            transition={{ delay: reduceMotion ? 0 : index * .025, duration: reduceMotion ? 0 : .25 }}
          >
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{text(item.zh, item.label)}</strong>
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
              <small>{text('维度详情', 'DIMENSION DETAIL')}</small>
              <strong>{text(focused.zh, focused.label)}</strong>
              <span>{enrichmentStatusLabel(focused.status, text)}</span>
              <div>
                {focused.matchedClaims.slice(0, 4).map((claim) => (
                  <div className="dimension-fact" key={claim.claim_id}><p><b>{humanize(claim.predicate)}</b>{formatValue(claim.value)}</p>{claim.evidence.map((ref, index) => <button key={ref.evidence_ref} onClick={() => onEvidence(ref.evidence_ref)}>{text(`查看来源 ${index + 1}`, `View source ${index + 1}`)}</button>)}</div>
                ))}
                {focused.matchedRelations.slice(0, 4).map(relation => <div className="dimension-fact" key={relation.relation_id}><p><b>{humanize(relation.relation_type)}</b>{String(relation.target.properties.title ?? relation.target.properties.name ?? relation.target.canonical_key)}</p>{relation.evidence.map((ref, index) => <button key={ref.evidence_ref} onClick={() => onEvidence(ref.evidence_ref)}>{text(`查看来源 ${index + 1}`, `View source ${index + 1}`)}</button>)}</div>)}
                {focused.matchedClaims.length === 0 && focused.matchedRelations.length === 0 && <p><b>{enrichmentStatusLabel(focused.status, text)}</b>{enrichmentStatusExplanation(focused.status, text)}</p>}
                {focused.authoritativeState && <details className="dimension-technical"><summary>{text('处理详情', 'Processing details')}</summary><p>REV {focused.authoritativeState.world_revision}</p>{focused.authoritativeState.attempted_operator_refs.length > 0 && <p>{focused.authoritativeState.attempted_operator_refs.join(' · ')}</p>}{focused.authoritativeState.blocked_attempt_refs.length > 0 && <p>{text('受阻尝试', 'Blocked attempts')} · {focused.authoritativeState.blocked_attempt_refs.length}</p>}</details>}
              </div>
              <em>{text('再次点击该维度以收起详情', 'Select the dimension again to close details')}</em>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}


function enrichmentStatusLabel(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'resolved') return text('已有证据', 'Supported')
  if (status === 'conflict') return text('冲突', 'CONFLICT')
  if (status === 'unknown') return text('已查询，仍未知', 'Queried; still unknown')
  if (status === 'missing') return text('缺少证据', 'Evidence missing')
  return text('尚未加载', 'Not loaded')
}

function enrichmentStatusExplanation(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'unknown') return text('权威查询或成功 operator 已明确返回未知；这与尚未获取证据不同。', 'An authoritative lookup or successful operator explicitly returned unknown; this differs from missing evidence.')
  if (status === 'missing') return text('尚未收集到支持这一维度的证据，可以在下方选择补全。', 'Supporting evidence has not been collected. Select this dimension below to enrich it.')
  if (status === 'conflict') return text('来源给出了不同的取值或适用性判断，需要进一步核验。', 'Sources disagree on values or applicability. Further verification is needed.')
  if (status === 'resolved') return text('已有证据支持这一维度，相关事实可在档案中查看。', 'Evidence supports this dimension. Related facts are available in the dossier.')
  return text('维度状态正在读取，加载后可查看事实与来源。', 'The dimension state is loading. Facts and sources will become available.')
}

function humanize(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ').toUpperCase() }
function formatValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(formatValue).join(' · ')
  try { return JSON.stringify(value) } catch { return String(value) }
}
