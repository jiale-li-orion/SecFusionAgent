import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getIntelligenceEnrichment, getVulnerability, type IntelligenceEnrichmentDimension } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

const RADIAL_CENTER = 50
const RADIAL_RADIUS = 39

function point(index: number, count: number) {
  const angle = -Math.PI / 2 + index / Math.max(1, count) * Math.PI * 2
  return {
    x: RADIAL_CENTER + Math.cos(angle) * RADIAL_RADIUS,
    y: RADIAL_CENTER + Math.sin(angle) * RADIAL_RADIUS,
  }
}

function dimensionCounts(dimensions: IntelligenceEnrichmentDimension[]) {
  return dimensions.reduce<Record<IntelligenceEnrichmentDimension['status'], number>>((counts, dimension) => {
    counts[dimension.status] += 1
    return counts
  }, { resolved: 0, conflict: 0, unknown: 0, missing: 0 })
}

export function HotEnrichmentPreview({ cveId }: { cveId: string | null }) {
  const { text } = useI18n()
  const knowledgeQuery = useQuery({
    queryKey: ['world-hot-knowledge', cveId],
    queryFn: () => getVulnerability(cveId!),
    enabled: Boolean(cveId),
    staleTime: 30_000,
  })
  const object = knowledgeQuery.data
  const enrichmentQuery = useQuery({
    queryKey: ['world-hot-enrichment', object?.object_id],
    queryFn: () => getIntelligenceEnrichment(object!.object_id),
    enabled: object?.object_type === 'Vulnerability',
    staleTime: 30_000,
  })
  const state = enrichmentQuery.data
  const counts = useMemo(() => dimensionCounts(state?.dimensions ?? []), [state?.dimensions])

  if (!cveId) {
    return <div className="world-enrichment-boundary unavailable"><small>ENRICHMENT-V1 / N/A</small><span>{text('该 Hot object 没有 CVE 身份，不推断十二维富化状态。', 'This Hot object has no CVE identity; no 12D enrichment state is inferred.')}</span></div>
  }
  if (knowledgeQuery.isLoading) {
    return <div className="world-enrichment-boundary resolving"><small>ENRICHMENT-V1 / RESOLVING</small><span>{text('正在解析 canonical Vulnerability…', 'Resolving canonical Vulnerability…')}</span></div>
  }
  if (knowledgeQuery.isError || !object) {
    return <div className="world-enrichment-boundary hot-only"><small>HOT ONLY / KNOWLEDGE UNAVAILABLE</small><span>{text('对象仍可存在于 Hot Layer；canonical Knowledge 尚不可读，因此不展示虚构的 enrichment。', 'The object may remain in the Hot Layer; canonical Knowledge is unreadable, so no enrichment is fabricated.')}</span></div>
  }
  if (enrichmentQuery.isLoading) {
    return <div className="world-enrichment-boundary resolving"><small>ENRICHMENT-V1 / CANONICAL</small><span>{text('正在读取权威十二维状态…', 'Resolving authoritative 12D state…')}</span></div>
  }
  if (enrichmentQuery.isError || !state) {
    return <div className="world-enrichment-boundary unavailable"><small>ENRICHMENT-V1 / UNAVAILABLE</small><span>{text('canonical object 已解析，但 enrichment read seam 当前不可用。', 'Canonical object resolved, but the enrichment read seam is unavailable.')}</span></div>
  }

  return (
    <section className="world-enrichment-preview" aria-label={text('权威十二维富化状态', 'Authoritative 12D enrichment state')}>
      <div className="world-enrichment-head">
        <div><small>ENRICHMENT-V1 / CANONICAL</small><strong>{counts.resolved}/{state.dimensions.length} {text('已解析', 'RESOLVED')}</strong></div>
        <span className="mono">WORLD REV {state.world_revision}</span>
      </div>
      <div className="world-enrichment-radial">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <circle cx="50" cy="50" r="39" />
          <circle cx="50" cy="50" r="21" className="inner" />
          {state.dimensions.map((dimension, index) => {
            const location = point(index, state.dimensions.length)
            return <line key={dimension.dimension} className={`status-${dimension.status}`} x1="50" y1="50" x2={location.x} y2={location.y} />
          })}
        </svg>
        <div className="world-enrichment-core"><small>12D</small><strong>{cveId}</strong></div>
        {state.dimensions.map((dimension, index) => {
          const location = point(index, state.dimensions.length)
          return (
            <span
              key={dimension.dimension}
              className={`world-enrichment-node status-${dimension.status}`}
              style={{ left: `${location.x}%`, top: `${location.y}%` }}
              title={`${dimension.dimension} · ${dimension.status}`}
            >
              <i />
            </span>
          )
        })}
      </div>
      <div className="world-enrichment-ledger">
        <span className="status-resolved">{counts.resolved} resolved</span>
        <span className="status-conflict">{counts.conflict} conflict</span>
        <span className="status-unknown">{counts.unknown} unknown</span>
        <span className="status-missing">{counts.missing} missing</span>
      </div>
    </section>
  )
}
