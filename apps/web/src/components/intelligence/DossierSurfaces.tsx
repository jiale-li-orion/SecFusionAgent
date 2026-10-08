import { BadgeCheck, BookOpenText, Boxes, ExternalLink, FileSearch, GitBranch, GitPullRequest, Package, Radar, Server } from 'lucide-react'

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
  return <section className="intel-empty-reading"><BookOpenText size={32} /><h2>{target ? text('正在打开对象', 'Opening object') : text('找到你要理解的对象。', 'Find the object you want to understand.')}</h2><p>{target ? target : text('输入论文标题、项目名、漏洞编号或资产名称，查看已有事实、关系与来源。也可以从世界动态进入一份档案。', 'Search a paper, project, vulnerability or asset to read its facts, relationships and sources.')}</p></section>
}

export function HotWorkingSetPanel({ item }: { item: HotBug }) {
  const { text } = useI18n()
  return <section className="hot-dossier">
    <div className="hot-dossier-head"><div><small>{text('热区观测', 'HOT OBSERVATION')} · {item.source_name ?? item.source_id}</small><strong>{item.title ?? item.cve_id ?? item.external_object_id}</strong><p>{formatDate(item.updated_at ?? item.fetched_at)} · {text('缓存中的上游记录', 'Cached upstream record')}</p></div><span className="hot-status">{item.pinned ? text('已固定', 'Pinned') : item.active ? text('正在使用', 'In use') : text('热区', 'Hot')}</span></div>
    {item.description && <div className="hot-text"><small>{text('来源描述', 'SOURCE DESCRIPTION')}</small><p>{item.description}</p></div>}
    {item.cvss_score != null && <p>{text('严重程度', 'Severity')} · {item.cvss_score.toFixed(1)} {item.cvss_severity}</p>}
    {item.affected_products.length > 0 && <p>{text('受影响产品', 'Affected products')} · {item.affected_products.join(' · ')}</p>}
    {item.canonical_url && <a className="document-canonical-link" href={item.canonical_url} target="_blank" rel="noreferrer">{text('阅读原始来源', 'Read original source')} <ExternalLink size={12} /></a>}
    <details className="hot-technical-coordinate"><summary>{text('观测详情与技术坐标', 'Observation details')}</summary><div><span>{text('来源', 'Source')}</span><b>{item.source_id}</b></div><div><span>{text('上游修订', 'Revision')}</span><b>{item.external_revision ?? '—'}</b></div><div><span>{text('外部对象', 'External object')}</span><b>{item.external_object_id}</b></div><div><span>{text('缓存剩余时间', 'Cache TTL')}</span><b>{item.ttl_seconds == null ? '—' : `${Math.round(item.ttl_seconds / 60)} min`}</b></div><div><span>{text('优先级信号', 'Priority signals')}</span><b>{item.priority_signals.join(' · ') || '—'}</b></div><div><span>{text('变化字段', 'Changed fields')}</span><b>{item.changed_fields.join(' · ') || '—'}</b></div><p>{text('这里保留的是热缓存记录；持久化事实会在核验任务和证据视角中呈现。', 'This is a hot cache record. Persisted facts are available through verification and evidence views.')}</p></details>
  </section>
}

export function ObjectFacetField({ obj }: { obj: Awaited<ReturnType<typeof getKnowledgeObject>> }) {
  const { text } = useI18n()
  const profile = objectFacetProfile(obj.object_type)
  const identifiers = Object.entries(obj.external_identifiers)
  const properties = orderedFacetEntries(obj.object_type, obj.properties)
  const claimFacts = obj.claims
    .filter((claim) => claim.value != null)
    .slice(0, 6)
  const evidenceCount = new Set([
    ...obj.claims.flatMap((claim) => claim.evidence.map((item) => item.evidence_ref)),
    ...obj.relations.flatMap((relation) => relation.evidence.map((item) => item.evidence_ref)),
  ]).size
  const Icon = profile.icon
  return (
    <section className={`object-facet-field object-kind-${profile.kind}`}>
      <div className="enrichment-head">
        <div><small>{text(profile.kickerZh, profile.kickerEn)}</small><strong>{profile.title}</strong></div>
        <span>{text(`${identifiers.length} 个标识命名空间 · ${obj.relations.length} 条关系`, `${identifiers.length} identifier namespaces · ${obj.relations.length} relations`)}</span>
      </div>
      <div className="object-facet-stage">
        <div className="object-facet-core">
          <span><Icon size={24} /></span>
          <div><small>{obj.object_type.toUpperCase()}</small><strong>{objectPrimaryLabel(obj)}</strong></div>
        </div>
        <p className="object-facet-summary">{text(`${obj.claims.length} 条已有事实 · ${obj.relations.length} 条关联 · ${evidenceCount} 份证据`, `${obj.claims.length} facts · ${obj.relations.length} relationships · ${evidenceCount} evidence references`)}</p>
      </div>
      <div className="object-facet-body">
        <details className="object-identifier-field object-facet-column"><summary>{text('对象标识', 'Object identifiers')}</summary><p className="mono">{obj.canonical_key}</p>{identifiers.map(([namespace, values]) => <div key={namespace}><small>{namespace}</small><strong>{values.join(' · ')}</strong></div>)}</details>
        <div className="object-property-field object-facet-column">
          <small className="object-facet-column-label">{text('对象事实', 'OBJECT FACTS')}</small>
          {properties.map(([key, value]) => (
            <div key={key}><small>{humanize(key)}</small><strong>{formatValue(value)}</strong></div>
          ))}
          {claimFacts.map((claim) => (
            <div key={claim.claim_id} className="object-claim-fact"><small>{humanize(claim.predicate)}</small><strong>{formatValue(claim.value)}</strong><em>{claim.evidence.length} evidence</em></div>
          ))}
          {properties.length === 0 && claimFacts.length === 0 && <div><small>FACTS</small><strong>{text('当前对象仅有关系或标识信息', 'identity / relation only')}</strong></div>}
        </div>
      </div>
      {obj.relations.length > 0 && (
        <div className="object-relation-preview">
          <small>{text('关系邻域预览', 'RELATION NEIGHBORHOOD')}</small>
          <div>{obj.relations.slice(0, 6).map((relation) => <span key={relation.relation_id}><b>{humanize(relation.relation_type)}</b>{relation.target.properties.display_name ? formatValue(relation.target.properties.display_name) : relation.target.canonical_key}</span>)}</div>
        </div>
      )}
    </section>
  )
}

function objectFacetProfile(objectType: string) {
  if (objectType === 'Repo') return { kind: 'development', icon: GitBranch, title: 'DEVELOPMENT INDEX', kickerZh: '开发资产档案', kickerEn: 'DEVELOPMENT DOSSIER' }
  if (objectType === 'Issue' || objectType === 'PullRequest' || objectType === 'Commit' || objectType === 'Release') return { kind: 'development', icon: GitPullRequest, title: 'CHANGE OBJECT', kickerZh: '开发变更档案', kickerEn: 'DEVELOPMENT CHANGE' }
  if (objectType === 'Document' || objectType === 'ResearchWork') return { kind: 'document', icon: BookOpenText, title: objectType === 'ResearchWork' ? 'RESEARCH CORPUS' : 'NORMATIVE / DOCUMENT', kickerZh: objectType === 'ResearchWork' ? '研究资料档案' : '文档与规范档案', kickerEn: objectType === 'ResearchWork' ? 'RESEARCH DOSSIER' : 'DOCUMENT DOSSIER' }
  if (objectType === 'InternetAsset') return { kind: 'asset', icon: Server, title: 'ASSET OBSERVATION', kickerZh: '互联网资产观测', kickerEn: 'INTERNET ASSET DOSSIER' }
  if (objectType === 'Package' || objectType === 'SoftwareVersion' || objectType === 'Product') return { kind: 'software', icon: Package, title: 'SOFTWARE IDENTITY', kickerZh: '软件与版本档案', kickerEn: 'SOFTWARE DOSSIER' }
  return { kind: 'canonical', icon: Boxes, title: 'CANONICAL OBJECT', kickerZh: '规范对象档案', kickerEn: 'CANONICAL OBJECT DOSSIER' }
}

function orderedFacetEntries(objectType: string, properties: Record<string, unknown>) {
  const priority = objectType === 'Repo'
    ? ['full_name', 'owner', 'name', 'html_url']
    : objectType === 'InternetAsset'
      ? ['ip', 'port', 'protocol', 'hostname', 'provider', 'country', 'organization']
      : objectType === 'SoftwareVersion'
        ? ['package_name', 'ecosystem', 'version']
        : objectType === 'Package'
          ? ['name', 'package_name', 'ecosystem']
          : objectType === 'Document' || objectType === 'ResearchWork'
            ? ['title', 'source_family', 'authors', 'published_at']
            : []
  const entries = Object.entries(properties).filter(([, value]) => value != null)
  return entries
    .sort(([left], [right]) => {
      const li = priority.indexOf(left)
      const ri = priority.indexOf(right)
      return (li === -1 ? 999 : li) - (ri === -1 ? 999 : ri) || left.localeCompare(right)
    })
    .slice(0, 8)
}

function objectPrimaryLabel(obj: Awaited<ReturnType<typeof getKnowledgeObject>>) {
  for (const key of ['display_name', 'title', 'full_name', 'name', 'ip', 'package_name', 'version']) {
    const value = obj.properties[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  const identifier = Object.values(obj.external_identifiers).flat()[0]
  return identifier ?? obj.canonical_key
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
          <small>{text("来源文档", "SOURCE DOCUMENT")}</small>
          <strong>{revision?.title ?? document.external_object_id}</strong>
          <span>{revision?.published_at ? formatDate(revision.published_at) : formatDate(document.created_at)}</span>
        </div>
        <div>
          <small>{text('来源', 'SOURCE')}</small>
          <strong>{document.source_id}</strong>
          <span>{revision ? `${revision.parser_name}@${revision.parser_version}` : text('无 revision', 'no revision')}</span>
        </div>
      </div>
      {document.source_excerpt && <div className="document-source-excerpt"><small>{text("正文节选", "SOURCE EXCERPT")}</small><p>{document.source_excerpt}</p></div>}
      <details className="document-index-details"><summary>{text("修订、索引与来源坐标", "Revision, index and provenance")}</summary>
      <div className="document-index-measures">
        <div><small>CHUNKS</small><strong>{document.chunk_count}</strong><span>{text('来源分段', 'Source chunks')}</span></div>
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
      <p className="mono">{document.excerpt_chunk_id} · {JSON.stringify(document.excerpt_locator)}</p></details>
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
