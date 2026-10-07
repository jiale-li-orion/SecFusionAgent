import { BadgeCheck, ExternalLink, FileSearch, Fingerprint, GitBranch, Radar } from 'lucide-react'

import { getDocumentByObject, getKnowledgeObject, listIncidents, type HotBug, type IncidentDetail, type KnowledgeClaim } from '../../lib/api'
import { formatDate, formatValue, humanize } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { EvidenceCapsules } from './KnowledgeSurfaces'

export function IncidentDossier({ incident, onEvidence }: { incident: IncidentDetail; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const watchEntries = Object.entries(incident.incident.watch_state)
  return (
    <section className="incident-dossier">
      <div className="incident-state">
        <div className="incident-state-copy">
          <small>DURABLE INCIDENT / REV {incident.incident.current_revision}</small>
          <strong>{incident.incident.current_summary ?? text('当前 Incident 尚无摘要。', 'No current Incident summary.')}</strong>
          <p>{text(
            `该 Incident 由 ${humanize(incident.incident.promotion_reason)} 提升进入 durable world；生命周期为 ${incident.incident.lifecycle}。`,
            `Promoted into the durable world by ${humanize(incident.incident.promotion_reason)}; lifecycle is ${incident.incident.lifecycle}.`,
          )}</p>
        </div>
        <div className="incident-state-facts">
          <div><small>LIFECYCLE</small><strong>{incident.incident.lifecycle}</strong></div>
          <div><small>PROMOTION</small><strong>{humanize(incident.incident.promotion_reason)}</strong></div>
          <div><small>CANDIDATE</small><strong className="mono">{incident.incident.candidate_id}</strong></div>
          <div><small>UPDATED</small><strong>{formatDate(incident.incident.updated_at)}</strong></div>
        </div>
        {watchEntries.length > 0 && (
          <div className="incident-watch">
            <small>WATCH STATE</small>
            <div>{watchEntries.map(([key, value]) => <span key={key}><b>{humanize(key)}</b>{formatValue(value)}</span>)}</div>
          </div>
        )}
      </div>

      <div className="incident-reading">
        <section className="incident-timeline">
          <div className="incident-section-head">
            <div><small>INCIDENT TIMELINE</small><strong>{text('事件演进', 'EVENT EVOLUTION')}</strong></div>
            <span>{incident.timeline.length} durable events</span>
          </div>
          <div className="incident-timeline-track">
            {incident.timeline.map((event, index) => (
              <article key={event.event_id} className="incident-event">
                <div className="incident-event-coordinate"><span>{String(index + 1).padStart(2, '0')}</span><i /></div>
                <div className="incident-event-body">
                  <div><small>{event.source_role} · REV {event.created_revision}</small><strong>{humanize(event.event_type)}</strong><time>{formatDate(event.event_time)}</time></div>
                  <p>{event.summary}</p>
                  <div className="incident-event-refs">
                    {event.evidence_refs.map((ref) => ref.startsWith('evidence:')
                      ? <button key={ref} onClick={() => onEvidence(ref)}><BadgeCheck size={11} /> EVIDENCE</button>
                      : <span key={ref} title={ref}>{typedRefLabel(ref)}</span>)}
                    {event.claim_refs.map((ref) => <span key={ref} title={ref}>CLAIM</span>)}
                    {event.supersedes_event_id && <span title={event.supersedes_event_id}>SUPERSEDES</span>}
                  </div>
                </div>
              </article>
            ))}
            {incident.timeline.length === 0 && <div className="incident-empty">{text('durable timeline 当前为空。', 'Durable timeline is empty.')}</div>}
          </div>
        </section>

        <aside className="incident-sources">
          <div className="incident-section-head">
            <div><small>SOURCE CORROBORATION</small><strong>{text('来源独立性', 'SOURCE DIVERSITY')}</strong></div>
            <span>{incident.incident.source_diversity_count} independent keys</span>
          </div>
          <div className="incident-source-list">
            {incident.sources.map((source) => (
              <article key={source.source_link_id}>
                <span className={`incident-source-role role-${source.source_role}`} />
                <div><small>{source.source_role} · {source.source_family}</small><strong>{source.source_id}</strong><em>{source.upstream_source ?? text('直接来源', 'direct source')}</em></div>
                <div><small>INDEPENDENCE KEY</small><strong className="mono">{source.independence_key}</strong><span>rev {source.created_revision}</span></div>
              </article>
            ))}
            {incident.sources.length === 0 && <div className="incident-empty">{text('当前没有 durable source link。', 'No durable source links.')}</div>}
          </div>
        </aside>
      </div>
    </section>
  )
}

function typedRefLabel(ref: string) {
  const prefix = ref.split(':', 1)[0] || 'ref'
  return prefix.replaceAll('-', ' ').toUpperCase()
}

export function IncidentArchiveRail({
  items,
  loading,
  error,
  activeId,
  onSelect,
}: {
  items: Awaited<ReturnType<typeof listIncidents>>['items']
  loading: boolean
  error: boolean
  activeId: string
  onSelect: (incidentId: string) => void
}) {
  const { text } = useI18n()
  return (
    <section className="incident-archive-rail">
      <div className="incident-archive-head">
        <div><small>DURABLE INCIDENTS</small><strong>{text('事件档案', 'INCIDENT ARCHIVE')}</strong></div>
        <span>{items.length}</span>
      </div>
      {loading ? (
        <div className="incident-archive-state">{text('解析 Incident 索引…', 'RESOLVING INCIDENT INDEX…')}</div>
      ) : error ? (
        <div className="incident-archive-state error-block" role="alert">{text('Incident read 读取失败。', 'Incident read failed.')}</div>
      ) : items.length === 0 ? (
        <div className="incident-archive-state">
          <Radar size={18} />
          <strong>{text('暂无已确认事件', 'NO CONFIRMED INCIDENTS')}</strong>
          <span>{text('事件确认后，可以在这里查看演进记录和来源。', 'Confirmed incidents appear here with their timeline and sources.')}</span>
        </div>
      ) : (
        <div className="incident-archive-list">
          {items.map((item) => (
            <button key={item.incident_id} className={item.incident_id === activeId ? 'active' : ''} onClick={() => onSelect(item.incident_id)}>
              <span className={`incident-archive-state-dot state-${item.lifecycle}`} />
              <div><small>{humanize(item.incident_type)}</small><strong>{item.current_summary ?? item.incident_id}</strong><em>{item.timeline_event_count} events · {item.source_diversity_count} independent</em></div>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

export function IntelligenceArchiveBlueprint({ target }: { target?: string }) {
  const { text } = useI18n()
  const groups = ['IDENTITY & SEVERITY', 'AFFECTED & FIX', 'EXPLOIT & LIKELIHOOD', 'SOURCE & TIMELINE']
  const nodes = [
    { x: 18, y: 28, label: 'Product / Version' },
    { x: 81, y: 25, label: 'Advisory / Fix' },
    { x: 77, y: 72, label: 'Incident / Exploit' },
    { x: 22, y: 74, label: 'Research / Asset' },
  ]
  return (
    <section className="intel-blueprint">
      <div className="intel-blueprint-claims">
        {groups.map((group, index) => (
          <div key={group}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <small>{text('CLAIM 分组', 'CLAIM GROUP')}</small>
            <strong>{group}</strong>
            <i />
            <i />
          </div>
        ))}
      </div>
      <div className="intel-blueprint-graph">
        <div className="instrument-section-head">
          <div><small>{text('聚焦知识图谱', 'FOCUSED KNOWLEDGE GRAPH')}</small><strong>{text('关系邻域', 'RELATION NEIGHBORHOOD')}</strong></div>
          <span>{text('目标解析后显示 canonical edges', 'canonical edges appear here when target resolves')}</span>
        </div>
        <div className="intel-blueprint-graph-stage">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {nodes.map((node) => <path key={node.label} d={`M 50 50 Q 50 42 ${node.x} ${node.y}`} />)}
          </svg>
          <div className="intel-blueprint-core">
            <Fingerprint size={22} />
            <strong>{target ?? 'CANONICAL OBJECT'}</strong>
            <small>VULNERABILITY</small>
          </div>
          {nodes.map((node) => (
            <div
              key={node.label}
              className="intel-blueprint-node"
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <GitBranch size={12} />
              <span><small>{text('关系槽位', 'RELATION SLOT')}</small><strong>{node.label}</strong></span>
            </div>
          ))}
          <div className="intel-blueprint-caption">TARGET → CLAIM → RELATION → EVIDENCE</div>
        </div>
      </div>
    </section>
  )
}

export function HotWorkingSetPanel({ item }: { item: HotBug }) {
  const { text } = useI18n()
  return (
    <section className="hot-dossier">
      <div className="hot-dossier-head">
        <div>
          <small>{text('HOT WORKING SET · 尚未 promotion', 'HOT WORKING SET · NOT YET PROMOTED')}</small>
          <strong>{item.cve_id ?? item.external_object_id}</strong>
          <p>{text(
            '对象已被 Data Plane 捕获并进入 Redis Hot Layer；canonical Knowledge 等待 promotion / retention policy 推进至 Evidence Core。',
            'The Data Plane has captured this object into the Redis Hot Layer. Canonical Knowledge remains pending until promotion / retention policy advances it into the Evidence Core.',
          )}</p>
        </div>
        <span className={`hot-status ${item.pinned ? 'pinned' : item.active ? 'active' : ''}`}>{item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : 'HOT'}</span>
      </div>
      <div className="hot-dossier-grid">
        <HotFact label="SOURCE" value={item.source_id} />
        <HotFact label="REVISION" value={item.external_revision ?? 'content revision'} mono />
        <HotFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
        <HotFact label="STATUS" value={item.status ?? '—'} />
        <HotFact label="TTL" value={item.ttl_seconds != null ? `${Math.round(item.ttl_seconds / 60)} min` : item.pinned ? 'persisted' : '—'} />
        <HotFact label="FETCHED" value={formatDate(item.fetched_at)} />
      </div>
      {item.title && <div className="hot-text"><small>{text('标题', 'TITLE')}</small><strong>{item.title}</strong></div>}
      {item.description && <div className="hot-text"><small>{text('描述', 'DESCRIPTION')}</small><p>{item.description}</p></div>}
      <div className="hot-signal-row">
        <div><small>{text('变化字段', 'CHANGED FIELDS')}</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : text('无', 'none')}</span></div>
        <div><small>{text('优先级信号', 'PRIORITY SIGNALS')}</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : text('无', 'none')}</span></div>
      </div>
    </section>
  )
}

function HotFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="hot-fact"><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

export function ObjectFacetField({ obj }: { obj: Awaited<ReturnType<typeof getKnowledgeObject>> }) {
  const { text } = useI18n()
  const identifiers = Object.entries(obj.external_identifiers)
  const properties = Object.entries(obj.properties).filter(([, value]) => value != null).slice(0, 10)
  return (
    <section className="object-facet-field">
      <div className="enrichment-head">
        <div><small>{text('规范对象切面', 'CANONICAL OBJECT FACETS')}</small><strong>{obj.object_type.toUpperCase()}</strong></div>
        <span>{text(`${identifiers.length} 个 identifier namespace · ${properties.length} 个可见属性`, `${identifiers.length} identifier namespaces · ${properties.length} visible properties`)}</span>
      </div>
      <div className="object-facet-body">
        <div className="object-identifier-field">
          {identifiers.map(([namespace, values]) => (
            <div key={namespace}><small>{namespace}</small><strong>{values.join(' · ')}</strong></div>
          ))}
          {identifiers.length === 0 && <div><small>IDENTIFIERS</small><strong>{text('无持久化标识', 'none persisted')}</strong></div>}
        </div>
        <div className="object-property-field">
          {properties.map(([key, value]) => (
            <div key={key}><small>{humanize(key)}</small><strong>{formatValue(value)}</strong></div>
          ))}
        </div>
      </div>
    </section>
  )
}

export function DocumentIndexDossier({
  document,
  loading,
  error,
}: {
  document: Awaited<ReturnType<typeof getDocumentByObject>> | null
  loading: boolean
  error: string | null
}) {
  const { text } = useI18n()
  if (loading) {
    return <section className="document-index-dossier is-loading"><FileSearch size={18} /><span>{text('解析文档索引…', 'RESOLVING DOCUMENT INDEX…')}</span></section>
  }
  if (error || !document) {
    return <section className="document-index-dossier is-error"><FileSearch size={18} /><span>{error ?? text('文档索引读取失败', 'Document index read failed')}</span></section>
  }
  const revision = document.current_revision
  const indexed = Object.entries(document.index_status_counts).sort((a, b) => b[1] - a[1])
  return (
    <section className="document-index-dossier">
      <div className="document-index-head">
        <div>
          <small>MANAGED DOCUMENT / INDEX PROVENANCE</small>
          <strong>{revision?.title ?? document.external_object_id}</strong>
          <span className="mono">{document.document_id}</span>
        </div>
        <div>
          <small>{text('来源', 'SOURCE')}</small>
          <strong>{document.source_id}</strong>
          <span>{revision ? `${revision.parser_name}@${revision.parser_version}` : text('无 revision', 'no revision')}</span>
        </div>
      </div>
      <div className="document-index-measures">
        <div><small>CHUNKS</small><strong>{document.chunk_count}</strong><span>{text('正文不在 Product read 中暴露', 'content withheld from Product read')}</span></div>
        <div><small>EMBEDDED</small><strong>{document.embedded_chunk_count}</strong><span>{document.embedding_models.join(' · ') || text('未记录 embedding model', 'no embedding model recorded')}</span></div>
        <div><small>INDEX STATE</small><strong>{indexed.map(([status, count]) => `${count} ${status}`).join(' · ') || '—'}</strong><span>{text('持久 chunk 状态', 'persisted chunk state')}</span></div>
        <div><small>SECTIONS</small><strong>{document.sections.length}</strong><span>{document.sections.slice(0, 3).join(' · ') || '—'}</span></div>
      </div>
      <div className="document-index-provenance">
        <div>
          <small>CURRENT REVISION</small>
          <strong className="mono">{revision?.document_revision_id ?? '—'}</strong>
          <span>{revision?.external_revision ?? revision?.content_hash.slice(0, 16) ?? '—'}</span>
        </div>
        <div>
          <small>OBSERVATION</small>
          <strong className="mono">{revision?.observation_id ?? '—'}</strong>
          <span>{revision?.updated_at ? formatDate(revision.updated_at) : revision?.created_at ? formatDate(revision.created_at) : '—'}</span>
        </div>
        <div>
          <small>INSIGHT CANDIDATE</small>
          <strong>{document.insight?.promotion_state ?? '—'}</strong>
          <span>{document.insight ? `${humanize(document.insight.change_type)} · ${humanize(document.insight.evidence_maturity)}` : text('未持久化 InsightCandidate', 'no persisted InsightCandidate')}</span>
        </div>
      </div>
      {document.canonical_url && <a className="document-canonical-link" href={document.canonical_url} target="_blank" rel="noreferrer">{text('打开规范文档来源', 'OPEN CANONICAL DOCUMENT SOURCE')} <ExternalLink size={12} /></a>}
    </section>
  )
}

export function ClaimGroup({ title, claims, onEvidence }: { title: string; claims: KnowledgeClaim[]; onEvidence: (ref: string) => void }) {
  return (
    <article className="claim-group">
      <div className="claim-group-title"><span>{title}</span><b>{claims.length}</b></div>
      <div className="claim-list">
        {claims.map((claim) => (
          <div key={claim.claim_id} className="claim-row">
            <div className="claim-copy">
              <small>{humanize(claim.predicate)}</small>
              <strong>{formatValue(claim.value)}</strong>
              <span className="mono">rev {claim.created_revision} · {claim.origin}</span>
            </div>
            <EvidenceCapsules evidence={claim.evidence} onEvidence={onEvidence} />
          </div>
        ))}
      </div>
    </article>
  )
}
