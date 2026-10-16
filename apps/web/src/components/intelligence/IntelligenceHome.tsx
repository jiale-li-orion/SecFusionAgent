import { Bookmark, Search, TrendingUp } from '../ui/icons'
import { Link, useLocation } from 'react-router-dom'
import type { IncidentSummary } from '../../lib/api'
import { safeAccountReturnTo, useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs'
import { IntelligenceIndex, type IntelligenceIndexProps } from './IntelligenceIndex'
import { PersonalizedIntelligence } from './PersonalizedIntelligence'
import { EventLibrary } from './EventLibrary'
import { MaterialLibrary } from './MaterialLibrary'
import { PublicBriefings } from './PublicBriefings'

export type IntelligenceChannel = 'recommended' | 'following' | 'events' | 'library'
export function IntelligenceHome({ channel, onChannel, onOpen, incidents, incidentsLoading, incidentsError, onIncident, onRetryIncidents, onRetryCandidates, ...indexProps }: IntelligenceIndexProps & {
  channel: IntelligenceChannel; onChannel: (channel: IntelligenceChannel) => void
  onOpen: (objectId: string, evidence?: string) => void
  incidents: IncidentSummary[]; incidentsLoading: boolean; incidentsError: boolean
  onIncident: (incidentId: string) => void; onRetryIncidents: () => void
  onRetryCandidates: () => void
}) {
  const auth = useAuth()
  const { text } = useI18n()
  const publicFeed = <IntelligenceIndex {...indexProps}/>
  return <Tabs value={channel} onValueChange={value => onChannel(value as IntelligenceChannel)} className="intel-channel-tabs">
    <nav className="intel-channel-nav" aria-label={text('情报频道', 'Intelligence channels')}>
      <TabsList variant="line">{([{ key: 'recommended', zh: '推荐', en: 'For you' }, { key: 'following', zh: '关注', en: 'Following' }, { key: 'events', zh: '事件库', en: 'Events' }, { key: 'library', zh: '资料库', en: 'Library' }] as const).map(item => <TabsTrigger key={item.key} value={item.key}>{text(item.zh, item.en)}</TabsTrigger>)}</TabsList>
      <Link to="/workspace/profile"><Bookmark size={14}/>{text('管理关注', 'Manage interests')}</Link>
    </nav>
    <TabsContent value={channel}><div className={`intel-home-grid intel-channel-${channel} ${auth.authenticated ? '' : 'is-public'}`}>
      <div className="intel-home-stream">
        {channel === 'recommended' && <PublicBriefings/>}
        {(channel === 'recommended' || channel === 'following') && (auth.authenticated
          ? <PersonalizedIntelligence following={channel === 'following'} onOpen={onOpen} publicFeed={publicFeed}/>
          : <><IntelligenceSignIn/>{channel === 'recommended' ? publicFeed : <div className="intel-feed-empty"><Bookmark size={28}/><h2>{text('你的关注，在这里汇聚', 'Your interests come together here')}</h2><p>{text('登录后查看保存的关注对象，以及有证据关联的新内容。', 'Sign in to see saved interests and new material connected by evidence.')}</p><button onClick={() => onChannel('recommended')}>{text('先浏览公开情报', 'Explore public intelligence')}</button></div>}</>)}
        {channel === 'library' && <MaterialLibrary onSelect={indexProps.onSelect}/>}
        {channel === 'events' && <EventLibrary incidents={incidents} candidates={indexProps.candidates} loading={incidentsLoading} candidatesLoading={indexProps.candidateLoading} error={incidentsError} candidateError={indexProps.candidateError} onRetry={onRetryIncidents} onRetryCandidates={onRetryCandidates} onIncident={onIncident} onCandidate={indexProps.onCandidateSelect}/>}

      </div>
      {(channel === 'recommended' || channel === 'following') && <aside className="intel-home-aside">
        <section className="intel-side-card intel-source-overview"><h2>{text('当前来源', 'In the collection')}</h2><div>{[...new Set(indexProps.stories.map(story => story.source_name?.split(' · ')[0] || story.source_id).filter(Boolean))].slice(0, 6).map(source => <Badge key={source} variant="secondary">{source}</Badge>)}</div><Link to="/intelligence?channel=library">{text('浏览资料库', 'Explore the library')}</Link></section>
        <section className="intel-side-card"><header><h2><TrendingUp size={17}/>{text('漏洞观察', 'Vulnerability watch')}</h2><Link aria-label={text('在资料库查看漏洞', 'Browse vulnerabilities')} to="/intelligence?channel=library&category=vulnerability">{text('浏览漏洞', 'Browse')}</Link></header>{indexProps.hotLoading && <p role="status">{text('读取中…', 'Loading…')}</p>}{indexProps.hotError && <p>{text('暂时无法读取。', 'Temporarily unavailable.')}</p>}{indexProps.hot.slice(0, 4).map((item, index) => <button className="intel-watch-item" key={`${item.source_id}:${item.external_object_id}`} onClick={() => indexProps.onHotSelect(item)}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{item.cve_id ?? item.external_object_id}</strong><p>{item.title || item.source_name || item.source_id}</p></div></button>)}{!indexProps.hotLoading && !indexProps.hotError && !indexProps.hot.length && <p>{text('当前没有热区漏洞。', 'No vulnerabilities in the current hot set.')}</p>}</section>
        <Link className="intel-workspace-link" to="/workspace"><Search size={17}/><div><strong>{text('继续我的调查', 'Continue your investigations')}</strong><span>{text('会话、调查与工作记录', 'Conversations, investigations and work')}</span></div></Link>
      </aside>}
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
    {!auth.loading && (auth.error ? <Button size="sm" variant="ghost" onClick={() => void auth.refresh()}>{text('重试', 'Retry')}</Button> : <Button size="sm" asChild><Link to={`/auth?${new URLSearchParams({ returnTo })}`}>{text('登录', 'Sign in')}</Link></Button>)}
  </div>
}
