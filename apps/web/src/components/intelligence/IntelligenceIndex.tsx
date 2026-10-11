import { useSearchParams } from 'react-router-dom'
import { ArrowUpRight, BookOpen, Code2, FileText, Globe, Radar, ShieldAlert, Building2, Scale, Server } from '../ui/icons'
import type { HotBug, WorldIncidentCandidate, WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { dateLabel } from './feedPresentation'
import { ToggleGroup, ToggleGroupItem } from '../ui/toggle-group'
import { SourceIdentity } from '../ui/source-identity'

const kinds = [
  { key: 'academic', zh: '研究', en: 'Research', icon: BookOpen },
  { key: 'development', zh: '开发', en: 'Development', icon: Code2 },
  { key: 'vulnerability', zh: '漏洞', en: 'Vulnerabilities', icon: ShieldAlert },
  { key: 'vendor', zh: '厂商', en: 'Vendors', icon: Building2 },
  { key: 'normative', zh: '标准', en: 'Standards', icon: Scale },
  { key: 'independent', zh: '独立情报', en: 'Independent', icon: Globe },
  { key: 'assets', zh: '资产', en: 'Assets', icon: Server },
  { key: 'incidents', zh: '事件', en: 'Incidents', icon: Radar },
]

export type IntelligenceIndexProps = {
  stories: WorldStory[]; hot: HotBug[]; hotTotal: number
  candidates: WorldIncidentCandidate[]; candidateTotal: number
  loading: boolean; hotLoading: boolean; candidateLoading: boolean
  error: string | null; hotError: string | null; candidateError: string | null
  onSelect: (story: WorldStory) => void
  onHotSelect: (item: HotBug) => void
  onCandidateSelect: (item: WorldIncidentCandidate) => void
}

export function IntelligenceIndex({ stories, hot, hotTotal, candidates, candidateTotal, loading, hotLoading, candidateLoading, error, hotError, candidateError, onSelect, onHotSelect, onCandidateSelect, library = false }: IntelligenceIndexProps & { library?: boolean }) {
  const { text, language } = useI18n()
  const [params, setParams] = useSearchParams()
  const category = params.get('category')
  function setCategory(value: string | null) {
    setParams(current => { const next = new URLSearchParams(current); if (value) next.set('category', value); else next.delete('category'); return next })
  }
  const currentCategory = library ? category : null
  const isHot = currentCategory === 'vulnerability'
  const isCandidate = currentCategory === 'incidents'
  const items = stories.filter(story => (story.object_id || story.incident_id) && (!currentCategory || story.category === currentCategory))
  const busy = isHot ? hotLoading : isCandidate ? candidateLoading : loading
  const failure = isHot ? hotError : isCandidate ? candidateError : error
  const count = isHot ? hot.length : isCandidate ? candidates.length : items.length
  return <section className="intel-collection" aria-label={text(library ? '情报资料库' : '公开发现', library ? 'Intelligence library' : 'Public discovery')}>
    {library && <div className="overflow-x-auto py-3"><ToggleGroup type="single" value={category ?? 'all'} onValueChange={value => { if (value) setCategory(value === 'all' ? null : value) }} spacing={1} aria-label={text('资料类型', 'Material type')}><ToggleGroupItem value="all">{text('全部', 'All')}</ToggleGroupItem>{kinds.map(item => <ToggleGroupItem value={item.key} key={item.key}>{text(item.zh, item.en)}</ToggleGroupItem>)}</ToggleGroup></div>}
    <div className="intel-stream-label"><span>{isHot ? text('漏洞观测', 'Vulnerability observations') : isCandidate ? text('待确认的事件线索', 'Incident signals awaiting confirmation') : library ? text('最近收录', 'Recently retained') : text('公开发现', 'Public discovery')}</span><small>{busy ? text('读取中…', 'Loading…') : text(`${count} 条内容`, `${count} items`)}{isHot && ` / ${hotTotal.toLocaleString()}`}{isCandidate && ` / ${candidateTotal}`}</small></div>
    {busy && !count && <div className="intel-feed-empty" role="status">{text('正在读取最新情报…', 'Loading intelligence…')}</div>}
    {failure && <p className="intel-feed-error" role="alert">{failure}</p>}
    {!busy && !failure && !count && <div className="intel-feed-empty"><FileText size={28}/><h3>{text('这里还没有收录内容', 'No material here yet')}</h3><p>{text('试试其他类型，或在上方搜索具体论文、项目与漏洞。', 'Try another type, or search for a paper, project or vulnerability above.')}</p></div>}
    <div className="intel-stream">
      {isHot ? hot.map(item => <article className="intel-feed-card" key={`${item.source_id}:${item.external_object_id}`}>
        <div className="intel-card-meta"><ShieldAlert size={16}/><span>{item.source_name ?? item.source_id}</span><span className="intel-state-label">{text('热区观测', 'Hot observation')}</span></div>
        <h2><button onClick={() => onHotSelect(item)}>{item.title || item.cve_id || item.external_object_id}</button></h2>
        {item.description && <p className="intel-card-excerpt">{item.description}</p>}
        <footer><span>{text('系统读取于', 'Read by system')} {dateLabel(item.fetched_at, language)}</span><button onClick={() => onHotSelect(item)}>{text('查看漏洞', 'View vulnerability')}<ArrowUpRight size={15}/></button></footer>
      </article>) : isCandidate ? candidates.map(item => <article className="intel-feed-card" key={item.candidate_id}>
        <div className="intel-card-meta"><Radar size={16}/><span>{item.source_name ?? item.source_id}</span><span className="intel-state-label">{text('候选线索', 'Candidate signal')}</span></div>
        <h2><button onClick={() => onCandidateSelect(item)}>{item.headline}</button></h2>
        {item.summary && <p className="intel-card-excerpt">{item.summary}</p>}
        <div className="intel-source-chips"><span>{text(`${item.independent_source_count} 个独立来源`, `${item.independent_source_count} independent sources`)}</span><span>{text(`${item.signal_count} 条信号`, `${item.signal_count} signals`)}</span></div>
        <footer><span>{text('发现于', 'Observed')} {dateLabel(item.observed_at, language)}</span><button onClick={() => onCandidateSelect(item)}>{text('查看线索', 'Inspect signal')}<ArrowUpRight size={15}/></button></footer>
      </article>) : items.map(story => {
        const kind = kinds.find(item => item.key === story.category)
        const Icon = kind?.icon ?? FileText
        return <article className="intel-feed-card" key={story.story_id}>
          <div className="intel-publisher-row"><SourceIdentity source={story.source_name ?? story.source_id} url={story.external_ref}/><span><Icon size={13}/>{kind ? text(kind.zh, kind.en) : text('资料', 'Material')}</span></div>
          <h2><button onClick={() => onSelect(story)}>{story.headline}</button></h2>
          {story.excerpt && <p className="intel-card-excerpt">{story.excerpt}</p>}
          <footer><span>{story.published_at ? text('发布于', 'Published') : text('发现于', 'Observed')} {dateLabel(story.published_at ?? story.observed_at, language)}</span><div>{story.external_ref && <a href={story.external_ref} target="_blank" rel="noreferrer">{text('原文', 'Source')}<ArrowUpRight size={13}/></a>}<button onClick={() => onSelect(story)}>{text('阅读档案', 'Read dossier')}<ArrowUpRight size={15}/></button></div></footer>
        </article>
      })}
    </div>
  </section>
}
