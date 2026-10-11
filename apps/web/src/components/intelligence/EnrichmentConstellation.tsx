import { useState } from 'react'
import { ChevronDown } from '../ui/icons'
import { Button } from '../ui/button'
import { EvidenceCapsules } from './KnowledgeSurfaces'
import { evidenceFieldLabel, formatValue } from '../../lib/intelligencePresentation'

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

export function EnrichmentConstellation({
  claims,
  relations,
  cveId,
  state,
  stateLoading,
  stateError,
  onEvidence,
}: {
  claims: KnowledgeClaim[]
  relations: KnowledgeRelation[]
  cveId: string
  state: IntelligenceEnrichmentState | null
  stateLoading: boolean
  stateError: boolean
  onEvidence: (ref: string) => void
}) {
  const { text } = useI18n()
  const [focusedDimension, setFocusedDimension] = useState<string | null>(null)
  const stateByDimension = new Map(state?.dimensions.map((item) => [item.dimension, item]) ?? [])
  const dimensions = enrichmentDimensions.map((dimension) => {
    const authoritativeState = stateByDimension.get(dimension.key)
    const factRefs = new Set(authoritativeState?.accepted_fact_refs ?? [])
    const matchedClaims = claims.filter((claim) => factRefs.has(`claim:${claim.claim_id}`))
    const matchedRelations = relations.filter((relation) => factRefs.has(`relation:${relation.relation_id}`))
    const status: EnrichmentVisualStatus = authoritativeState?.status ?? 'not_materialized'
    return {
      ...dimension,
      status,
      authoritativeState,
      matchedClaims,
      matchedRelations,
    }
  })
  const counts = dimensions.reduce<Record<EnrichmentVisualStatus, number>>(
    (acc, item) => {
      acc[item.status] += 1
      return acc
    },
    { resolved: 0, conflict: 0, unknown: 0, missing: 0, not_materialized: 0 },
  )
  const focused = dimensions.find((item) => item.key === focusedDimension) ?? null

  return (
    <section className="coverage-panel" aria-label={text(`${cveId} 的证据覆盖`, `Evidence coverage for ${cveId}`)}>
      <header className="coverage-heading">
        <div>
          <h2>{text('哪些信息已经有证据支持', 'What the evidence covers')}</h2>
          <p>
            {stateLoading
              ? text('正在读取证据覆盖…', 'Loading evidence coverage…')
              : stateError
                ? text('维度状态暂时不可读，请重试。', 'Dimension states could not be loaded. Please retry.')
                : !state
                  ? text('尚未记录维度状态。', 'No dimension state is recorded.')
                  : text(
                      `${counts.resolved} 个维度已有证据，${counts.conflict} 个存在冲突，${counts.unknown} 个查询后仍未知，${counts.missing} 个待补充。`,
                      `${counts.resolved} supported, ${counts.conflict} conflicting, ${counts.unknown} queried but unknown, ${counts.missing} missing.`,
                    )}
          </p>
        </div>
      </header>
      <div className="coverage-grid">
        {dimensions.map((item) => (
          <button
            key={item.key}
            className={`coverage-dimension status-${item.status} ${focusedDimension === item.key ? 'is-selected' : ''}`}
            aria-expanded={focusedDimension === item.key}
            aria-controls="coverage-detail"
            onClick={() => setFocusedDimension((current) => (current === item.key ? null : item.key))}
          >
            <span className="coverage-status-dot" />
            <div>
              <strong>{text(item.zh, item.label)}</strong>
              <small>{enrichmentStatusLabel(item.status, text)}</small>
            </div>
            <ChevronDown size={14} />
          </button>
        ))}
      </div>
      {focused && (
        <section id="coverage-detail" className="coverage-detail">
          <header>
            <h3>{text(focused.zh, focused.label)}</h3>
            <Button variant="ghost" size="sm" onClick={() => setFocusedDimension(null)}>
              {text('收起', 'Close')}
            </Button>
          </header>
          {focused.matchedClaims.map((claim) => (
            <article key={claim.claim_id}>
              <small>{evidenceFieldLabel(claim.predicate, text)}</small>
              <p>{formatValue(claim.value)}</p>
              <EvidenceCapsules evidence={claim.evidence} onEvidence={onEvidence} />
            </article>
          ))}
          {focused.matchedRelations.map((relation) => (
            <article key={relation.relation_id}>
              <small>{evidenceFieldLabel(relation.relation_type, text)}</small>
              <p>{String(relation.target.properties.title ?? relation.target.properties.name ?? relation.target.canonical_key)}</p>
              <EvidenceCapsules evidence={relation.evidence} onEvidence={onEvidence} />
            </article>
          ))}
          {focused.matchedClaims.length === 0 && focused.matchedRelations.length === 0 && (
            <p>{enrichmentStatusExplanation(focused.status, text)}</p>
          )}
          {focused.authoritativeState && (
            <details>
              <summary>{text('处理详情', 'Processing details')}</summary>
              <p>
                {text('世界修订', 'World revision')} {focused.authoritativeState.world_revision}
              </p>
              {focused.authoritativeState.attempted_operator_refs.length > 0 && (
                <p>{focused.authoritativeState.attempted_operator_refs.join(' · ')}</p>
              )}
              {focused.authoritativeState.blocked_attempt_refs.length > 0 && (
                <p>
                  {text('受阻尝试', 'Blocked attempts')} · {focused.authoritativeState.blocked_attempt_refs.length}
                </p>
              )}
            </details>
          )}
        </section>
      )}
    </section>
  )
}

function enrichmentStatusLabel(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'resolved') return text('已有证据', 'Supported')
  if (status === 'conflict') return text('冲突', 'CONFLICT')
  if (status === 'unknown') return text('已查询，仍未知', 'Queried; still unknown')
  if (status === 'missing') return text('缺少证据', 'Evidence missing')
  return text('尚无记录', 'Not recorded')
}

function enrichmentStatusExplanation(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'unknown')
    return text(
      '权威查询或成功 operator 已明确返回未知；这与尚未获取证据不同。',
      'An authoritative lookup or successful operator explicitly returned unknown; this differs from missing evidence.',
    )
  if (status === 'missing')
    return text(
      '尚未收集到支持这一维度的证据，可以在下方选择补全。',
      'Supporting evidence has not been collected. Select this dimension below to enrich it.',
    )
  if (status === 'conflict')
    return text(
      '来源给出了不同的取值或适用性判断，需要进一步核验。',
      'Sources disagree on values or applicability. Further verification is needed.',
    )
  if (status === 'resolved')
    return text(
      '已有证据支持这一维度，相关事实可在档案中查看。',
      'Evidence supports this dimension. Related facts are available in the dossier.',
    )
  return text(
    '尚未读取到该维度的状态，暂时无法判断证据覆盖。',
    'No state has been read for this dimension, so its evidence coverage is not known.',
  )
}
