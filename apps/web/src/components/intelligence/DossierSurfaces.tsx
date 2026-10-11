import { BookOpenText, ExternalLink, FileSearch } from 'lucide-react'

import { getDocumentByObject, type HotBug, type IncidentDetail } from '../../lib/api'
import { formatDate, formatValue, humanize } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { IncidentEvolution } from './IncidentEvolution'

export function IncidentDossier({ incident, onEvidence }: { incident: IncidentDetail; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  return <section className="incident-dossier">
    <IncidentEvolution key={incident.incident.incident_id} incident={incident} onEvidence={onEvidence}/>
    <section className="intel-retained-sources"><header><h2>{text('已保留的来源', 'Retained sources')}</h2><span>{text(`${incident.incident.source_diversity_count} 个独立来源`, `${incident.incident.source_diversity_count} independent sources`)}</span></header><p>{text('来源链接没有独立的发现时间，不参与时间回放。', 'Source links do not have individual discovery timestamps and are not placed on the playback timeline.')}</p><div>{incident.sources.map(source => <article key={source.source_link_id}><span><FileSearch size={17}/></span><div><strong>{source.source_id}</strong><small>{source.source_family} · {source.source_role}</small><p>{source.upstream_source ?? text('直接来源', 'Direct source')}</p></div></article>)}</div>{!incident.sources.length && <p>{text('当前档案没有保留的来源链接。', 'There are no retained source links in this dossier.')}</p>}</section>
    <details className="intel-incident-details"><summary>{text('事件状态与技术详情', 'Event status and technical details')}</summary><dl><div><dt>{text('状态', 'State')}</dt><dd>{incident.incident.lifecycle}</dd></div><div><dt>{text('建立原因', 'Promotion reason')}</dt><dd>{humanize(incident.incident.promotion_reason)}</dd></div><div><dt>{text('档案建立于', 'Dossier created')}</dt><dd>{formatDate(incident.incident.created_at)}</dd></div><div><dt>{text('更新于', 'Updated')}</dt><dd>{formatDate(incident.incident.updated_at)}</dd></div></dl><p className="mono">{incident.incident.incident_id} · REV {incident.incident.current_revision}</p>{Object.entries(incident.incident.watch_state).map(([key, value]) => <p key={key}>{humanize(key)} · {formatValue(value)}</p>)}</details>
  </section>
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
