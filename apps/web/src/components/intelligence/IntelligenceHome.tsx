import { ArrowRight, ArrowUpRight, Bookmark, Radio, Search, TrendingUp } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import type { IncidentSummary } from '../../lib/api'
import { safeAccountReturnTo, useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { IntelligenceIndex, type IntelligenceIndexProps } from './IntelligenceIndex'
import { PersonalizedIntelligence } from './PersonalizedIntelligence'
import { HotIntelligenceFeed } from './HotIntelligenceFeed'
import { dateLabel } from './feedPresentation'

export type IntelligenceChannel = 'recommended' | 'following' | 'hot' | 'events' | 'library'
export function IntelligenceHome({ channel, onChannel, onOpen, incidents, incidentsLoading, incidentsError, onIncident, onRetryIncidents, ...indexProps }: IntelligenceIndexProps & {
  channel: IntelligenceChannel; onChannel: (channel: IntelligenceChannel) => void
  onOpen: (objectId: string, evidence?: string) => void
  incidents: IncidentSummary[]; incidentsLoading: boolean; incidentsError: boolean
  onIncident: (incidentId: string) => void; onRetryIncidents: () => void
}) {
  const auth = useAuth()
  const { text, language } = useI18n()
  const publicFeed = <IntelligenceIndex {...indexProps}/>
  return <Tabs value={channel} onValueChange={value => onChannel(value as IntelligenceChannel)} className="intel-channel-tabs">
    <nav className="intel-channel-nav" aria-label={text('情报频道', 'Intelligence channels')}>
      <TabsList variant="line">{([{ key: 'recommended', zh: '推荐', en: 'For you' }, { key: 'following', zh: '关注', en: 'Following' }, { key: 'hot', zh: '热点', en: 'Hot' }, { key: 'events', zh: '事件', en: 'Events' }, { key: 'library', zh: '资料库', en: 'Library' }] as const).map(item => <TabsTrigger key={item.key} value={item.key}>{text(item.zh, item.en)}</TabsTrigger>)}</TabsList>
      <Link to="/workspace/profile"><Bookmark size={14}/>{text('管理关注', 'Manage interests')}</Link>
    </nav>
    <TabsContent value={channel}><div className={`intel-home-grid intel-channel-${channel} ${auth.authenticated ? '' : 'is-public'}`}>
      <div className="intel-home-stream">
        {(channel === 'recommended' || channel === 'following') && (auth.authenticated
          ? <PersonalizedIntelligence following={channel === 'following'} onOpen={onOpen} publicFeed={publicFeed}/>
          : <><IntelligenceSignIn/>{channel === 'recommended' ? publicFeed : <div className="intel-feed-empty"><Bookmark size={28}/><h2>{text('你的关注，在这里汇聚', 'Your interests come together here')}</h2><p>{text('登录后查看保存的关注对象，以及有证据关联的新内容。', 'Sign in to see saved interests and new material connected by evidence.')}</p><button onClick={() => onChannel('recommended')}>{text('先浏览公开情报', 'Explore public intelligence')}<ArrowRight size={15}/></button></div>}</>)}
        {channel === 'hot' && <HotIntelligenceFeed onOpen={indexProps.onHotSelect}/>}
        {channel === 'library' && <IntelligenceIndex {...indexProps} library/>}
        {channel === 'events' && <section className="intel-event-feed">
          <div className="intel-stream-label"><span>{text('已建立的事件档案', 'Retained event dossiers')}</span><small>{incidents.length}</small></div>
          {incidentsLoading && <p className="intel-feed-empty" role="status">{text('读取事件档案…', 'Loading events…')}</p>}
          {incidentsError && <p className="intel-feed-error" role="alert">{text('事件档案暂不可用。', 'Events are temporarily unavailable.')}<button onClick={onRetryIncidents}>{text('重试', 'Retry')}</button></p>}
          {!incidentsLoading && !incidentsError && !incidents.length && <div className="intel-feed-empty"><Radio size={28}/><h2>{text('已确认事件会出现在这里', 'Confirmed events appear here')}</h2><p>{text('下方是正在观察的线索；候选线索尚不代表已确认的安全事件。', 'Signals being watched appear below. A candidate signal is not a confirmed security event.')}</p></div>}
          <div className="intel-stream">{incidents.map(incident => <article key={incident.incident_id} className="intel-feed-card intel-event-card"><div className="intel-card-meta"><Radio size={16}/><span>{text('事件档案', 'Event dossier')}</span><span className="intel-state-label">{incident.lifecycle}</span></div><h2><button onClick={() => onIncident(incident.incident_id)}>{incident.current_summary || incident.incident_type.replaceAll('_', ' ')}</button></h2><div className="intel-event-counts"><span><b>{incident.timeline_event_count}</b>{text('条演化记录', 'timeline records')}</span><span><b>{incident.source_diversity_count}</b>{text('个独立来源', 'independent sources')}</span></div><footer><span>{text('更新于', 'Updated')} {dateLabel(incident.updated_at, language)}</span><button onClick={() => onIncident(incident.incident_id)}>{text('查看事件演化', 'Explore evolution')}<ArrowUpRight size={15}/></button></footer></article>)}</div>
          <div className="intel-stream-label intel-signals-heading"><span>{text('正在观察的线索', 'Signals under observation')}</span><small>{indexProps.candidateTotal}</small></div>
          {indexProps.candidateLoading && <p role="status">{text('读取线索…', 'Loading signals…')}</p>}
          {indexProps.candidateError && <p className="intel-feed-error" role="alert">{indexProps.candidateError}</p>}
          {!indexProps.candidateLoading && !indexProps.candidateError && !indexProps.candidates.length && <p className="intel-feed-empty">{text('当前没有待观察的事件线索。', 'There are no event signals to inspect right now.')}</p>}
          <div className="intel-stream">{indexProps.candidates.slice(0, 16).map(candidate => <article key={candidate.candidate_id} className="intel-feed-card"><div className="intel-card-meta"><span className="intel-state-label">{text('候选线索', 'Candidate signal')}</span><span>{candidate.source_name ?? candidate.source_id}</span></div><h2><button onClick={() => indexProps.onCandidateSelect(candidate)}>{candidate.headline}</button></h2>{candidate.summary && <p className="intel-card-excerpt">{candidate.summary}</p>}<footer><span>{text(`${candidate.independent_source_count} 个独立来源`, `${candidate.independent_source_count} independent sources`)}</span><button onClick={() => indexProps.onCandidateSelect(candidate)}>{text('查看线索', 'Inspect signal')}<ArrowUpRight size={15}/></button></footer></article>)}</div>
        </section>}
      </div>
      <aside className="intel-home-aside">
        <section className="intel-side-card intel-source-overview"><h2>{text('当前来源', 'In the collection')}</h2><div>{[...new Set(indexProps.stories.map(story => story.source_name?.split(' · ')[0] || story.source_id).filter(Boolean))].slice(0, 6).map(source => <Badge key={source} variant="secondary">{source}</Badge>)}</div><Link to="/intelligence?channel=library">{text('浏览资料库', 'Explore the library')}<ArrowUpRight size={14}/></Link></section>
        <section className="intel-side-card"><header><h2><TrendingUp size={17}/>{text('漏洞观察', 'Vulnerability watch')}</h2><Link aria-label={text('在资料库查看漏洞', 'Browse vulnerabilities')} to="/intelligence?channel=library&category=vulnerability"><ArrowUpRight size={16}/></Link></header>{indexProps.hotLoading && <p role="status">{text('读取中…', 'Loading…')}</p>}{indexProps.hotError && <p>{text('暂时无法读取。', 'Temporarily unavailable.')}</p>}{indexProps.hot.slice(0, 4).map((item, index) => <button className="intel-watch-item" key={`${item.source_id}:${item.external_object_id}`} onClick={() => indexProps.onHotSelect(item)}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{item.cve_id ?? item.external_object_id}</strong><p>{item.title || item.source_name || item.source_id}</p></div></button>)}{!indexProps.hotLoading && !indexProps.hotError && !indexProps.hot.length && <p>{text('当前没有热区漏洞。', 'No vulnerabilities in the current hot set.')}</p>}</section>
        <Link className="intel-workspace-link" to="/workspace"><Search size={17}/><div><strong>{text('继续我的调查', 'Continue your investigations')}</strong><span>{text('会话、调查与工作记录', 'Conversations, investigations and work')}</span></div><ArrowUpRight size={16}/></Link>
      </aside>
    </div></TabsContent>
  </Tabs>
}

function IntelligenceSignIn() {
  const auth = useAuth()
  const location = useLocation()
  const { text } = useI18n()
  const returnTo = safeAccountReturnTo(`${location.pathname}${location.search}`)
  return <div className="intel-signin-row">
    <span>{auth.loading ? text('确认账户中…', 'Checking your account…') : auth.error ? text('暂时无法确认账户', 'Account check unavailable') : text('登录，获取与你有关的情报', 'Sign in for a feed that follows your interests')}</span>
    {!auth.loading && (auth.error ? <Button size="sm" variant="ghost" onClick={() => void auth.refresh()}>{text('重试', 'Retry')}</Button> : <Button size="sm" asChild><Link to={`/auth?${new URLSearchParams({ returnTo })}`}>{text('登录', 'Sign in')}<ArrowRight size={13}/></Link></Button>)}
  </div>
}
