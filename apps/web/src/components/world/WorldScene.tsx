import { useRef, useState } from 'react'
import { Activity, ArrowRight, BookOpen, Braces, Bug, Fingerprint, Globe2, Radio, Scale, Shield, X } from '../ui/icons'
import type { WorldFormation, WorldOverview, WorldStory, WorldKnowledgeChange } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { EvidenceAtlas } from './EvidenceAtlas'
import { WorldSourceInspector } from './WorldSourceInspector'
import { WorldHotField, WorldFormationField } from './WorldActivityField'
import { WorldStoryCard } from './WorldStoryCard'
import { Button } from '../ui/button'
import { Tabs, TabsList, TabsTrigger } from '../ui/tabs'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../ui/sheet'
import { UiThemeProvider } from '../ui/theme'
import { useMediaQuery } from '../../lib/useMediaQuery'
import './world.css'

const categories = [
  { key: 'vulnerability', zh: '漏洞', en: 'Vulnerabilities', icon: Bug, path: 'Bug Stream' },
  { key: 'development', zh: '代码', en: 'Code', icon: Braces, path: 'Development Index' },
  { key: 'academic', zh: '研究', en: 'Research', icon: BookOpen, path: 'Insight Corpus' },
  { key: 'vendor', zh: '厂商', en: 'Vendors', icon: Shield, path: 'Insight Corpus' },
  { key: 'independent', zh: '独立情报', en: 'Independent', icon: Radio, path: 'Insight Corpus' },
  { key: 'normative', zh: '标准', en: 'Standards', icon: Scale, path: 'Insight Corpus' },
  { key: 'assets', zh: '资产', en: 'Assets', icon: Globe2, path: 'Asset Observation' },
  { key: 'incidents', zh: '事件', en: 'Incidents', icon: Fingerprint, path: 'Incident Watch' },
]

type Props = {
  changes: WorldKnowledgeChange[]; changesPending: boolean; changesFailed: boolean; onChangesRetry: () => void
  stories: WorldStory[]; hotStories: WorldStory[]; focusedId: string | null; pending: boolean; failed: boolean; candidatePending: boolean; candidateFailed: boolean
  onFocus: (story: WorldStory) => void; onHotFromAtlas: (story: WorldStory) => void; onOpen: (story: WorldStory) => void
  onInvestigate: (story: WorldStory) => void; onRetry: () => void; onCandidateRetry: () => void
  view: string; onView: (view: string) => void; overview: WorldOverview | undefined; overviewFailed: boolean; onOverviewRetry: () => void
  formation: WorldFormation | undefined; formationFailed: boolean; onFormationRetry: () => void
  hotTotal: number | undefined; hotFailed: boolean; hotPending: boolean; hotPage: number; hotPageSize: number; onHotPage: (page: number) => void
  region: string | null; onRegion: (region: string | null) => void; onHotRetry: () => void
}

export function WorldScene(props: Props) {
  const { stories, hotStories, focusedId, pending, failed, candidatePending, candidateFailed, onFocus, onHotFromAtlas, onOpen, onInvestigate, onRetry, onCandidateRetry, view, onView, overview, overviewFailed, onOverviewRetry, formation, formationFailed, onFormationRetry, hotTotal, hotFailed, hotPending, hotPage, hotPageSize, onHotPage, region, onRegion, onHotRetry, changes, changesPending, changesFailed, onChangesRetry } = props
  const { text, language } = useI18n()
  const formationTrigger = useRef<HTMLButtonElement>(null)
  const compact = useMediaQuery('(max-width: 850px)')
  const [showSource, setShowSource] = useState(Boolean(region))
  const direction = categories.find(c => c.key === region)
  const sourceView = view === 'stories' || view === 'sources' || !['hot', 'formation'].includes(view)
  const available = view === 'hot' ? stories.filter(s => s.kind === 'HotVulnerability') : stories.filter(s => s.kind !== 'HotVulnerability' || region === 'vulnerability')
  const visible = region && sourceView ? available.filter(s => s.category === region) : available
  const focused = visible.find(s => s.story_id === focusedId) ?? visible[0] ?? null
  const latestResult = formation?.processing.find(run => run.commit_status === 'committed' && run.affected_objects?.length)
  const recentResult = latestResult?.results_complete && latestResult.claim_count !== undefined && latestResult.relation_count !== undefined
    ? text(`${latestResult.affected_objects![0].label} · ${latestResult.claim_count} 条事实、${latestResult.relation_count} 条关联已留存`, `${latestResult.affected_objects![0].label} · ${latestResult.claim_count} facts and ${latestResult.relation_count} relationships retained`) : null
  const metrics = overview?.windows['24h']
  const readFailed = view === 'hot' ? hotFailed : region === 'incidents' ? candidateFailed : failed
  const readPending = view === 'hot' ? hotPending : region === 'incidents' ? candidatePending : pending
  const retry = view === 'hot' ? onHotRetry : region === 'incidents' ? onCandidateRetry : onRetry
  function selectSource(key: string) {
    onRegion(region === key && sourceView ? null : key)
    setShowSource(region !== key || !sourceView)
  }
  function selectStory(story: WorldStory) { onFocus(story); setShowSource(false) }

  return <section className="world-page" aria-label={text('安全情报世界', 'Security intelligence world')}>
    <header className="world-heading">
      <div><p className="world-eyebrow">THE INTELLIGENCE WORLD</p><h1>{text('看见变化，发现关联。', 'See change. Find connections.')}</h1><p>{text('从八类来源出发，探索正在发生的安全变化。', 'Explore emerging security changes across eight source domains.')}</p></div>
      <div className="world-sync"><span className={overview ? 'world-status-dot' : 'world-status-dot is-unavailable'} />{overview ? <span>{text('最近更新', 'Updated')}<time dateTime={overview.generated_at}>{new Date(overview.generated_at).toLocaleTimeString(language === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' })}</time></span> : <span>{overviewFailed ? text('状态暂不可用', 'Status unavailable') : text('读取世界状态', 'Reading world state')}</span>}{overviewFailed && <button onClick={onOverviewRetry}>{text('重试', 'Retry')}</button>}</div>
    </header>

    <UiThemeProvider theme="dark"><div className="world-stage ui-night dark">
      <div className="world-stage-top"><span className="world-map-label"><Globe2 size={16} />{text('正在观察的世界', 'World in focus')}</span><Tabs value={view === 'hot' ? 'hot' : 'stories'} onValueChange={value => { onView(value); setShowSource(false) }}><TabsList><TabsTrigger value="stories">{text('浏览来源', 'Explore sources')}</TabsTrigger><TabsTrigger value="hot">{text('查看热点', 'Hot objects')}</TabsTrigger></TabsList></Tabs></div>

      <div className={`world-content  ${showSource && direction && sourceView ? 'world-content-inspecting' : ''}`}>
        <div className="world-main">
          {view !== 'hot' ? <EvidenceAtlas directions={categories} overview={overview} stories={visible} focusedId={focused?.story_id} region={region} onSource={selectSource} onFocus={selectStory} /> : <WorldHotField stories={hotStories} focusedId={focused?.story_id} total={hotTotal} failed={hotFailed} pending={hotPending} page={hotPage} pageSize={hotPageSize} onPage={onHotPage} onFocus={selectStory} onRetry={onHotRetry} />}
        </div>
        <div className="world-focus-panel" aria-live="polite">
          {showSource && direction && sourceView && !compact ? <WorldSourceInspector category={direction.key} label={text(direction.zh, direction.en)} path={direction.path} materials={stories} onClose={() => setShowSource(false)} onFocus={selectStory} />
            : focused ? <WorldStoryCard story={focused} onOpen={onOpen} onInvestigate={onInvestigate} />
            : <div className="world-empty" role={readFailed ? 'alert' : 'status'}><Radio size={24} /><h2>{readFailed ? text('暂时无法读取动态', 'Signals are unavailable') : readPending ? text('正在读取世界动态', 'Reading world signals') : text('等待新的变化', 'Awaiting new signals')}</h2><p>{text('来源状态与已留存的材料可以独立浏览。', 'Source status and retained material remain available to explore.')}</p>{readFailed && <button className="world-text-action" onClick={retry}>{text('重新读取', 'Retry')}</button>}</div>}
        </div>
      </div>
      <div className="world-scene-caption"><span>{direction && sourceView ? <><span className="world-caption-dot" />{text('已聚焦', 'Focused on')} {text(direction.zh, direction.en)}<button onClick={() => { onRegion(null); setShowSource(false) }} aria-label={text('清除来源筛选', 'Clear source filter')}><X size={13} /></button></> : text('选择来源或光点，展开它的故事', 'Select a source or a node to explore its story')}</span><small>{text('连线表示材料所属来源', 'Connections indicate source provenance')}</small></div>
    </div>

    <Sheet open={compact && showSource && Boolean(direction) && sourceView} onOpenChange={open => setShowSource(open)}><SheetContent side="bottom" className="world-source-sheet ui-night dark" onCloseAutoFocus={event => { event.preventDefault(); document.querySelector<HTMLButtonElement>(`[data-source="${region}"]`)?.focus() }}><SheetHeader><SheetTitle>{direction ? text(direction.zh, direction.en) : text('来源', 'Sources')}</SheetTitle><SheetDescription>{text('浏览这个方向的来源和已收录材料。', 'Explore sources and retained material in this domain.')}</SheetDescription></SheetHeader>{direction && <WorldSourceInspector category={direction.key} label={text(direction.zh, direction.en)} path={direction.path} materials={stories} onClose={() => setShowSource(false)} onFocus={selectStory} embedded/>}</SheetContent></Sheet>
    </UiThemeProvider>
    <section className="world-recent-knowledge"><div><Activity size={18}/><span><strong>{text('最近形成的知识', 'Recent knowledge')}</strong><small>{changesPending ? text('读取中…', 'Loading…') : changesFailed ? text('暂时无法读取提交', 'Commits unavailable') : recentResult ?? (changes.length ? text(`最近 ${changes.length} 次提交，查看对象与关联的变化`, `Explore objects and relationships across ${changes.length} recent commits`) : text('当前暂无新的知识提交', 'No recent knowledge commits'))}</small></span></div><Button ref={formationTrigger} variant="ghost" onClick={() => onView('formation')}>{text('查看变化', 'View changes')}<ArrowRight size={16}/></Button></section>
    <Sheet open={view === 'formation'} onOpenChange={open => { if (!open) onView('stories') }}><SheetContent className="world-formation-sheet" onCloseAutoFocus={event => { event.preventDefault(); formationTrigger.current?.focus() }}><SheetHeader><SheetTitle>{text('最近形成的知识', 'Recent knowledge')}</SheetTitle><SheetDescription>{text('查看处理了哪些材料、形成了哪些对象和关联。', 'See which material was processed and which objects and relationships were retained.')}</SheetDescription></SheetHeader><WorldFormationField formation={formation} failed={formationFailed} onRetry={onFormationRetry}/>{changesFailed && <Button variant="ghost" onClick={onChangesRetry}>{text('重新读取知识提交', 'Retry knowledge commits')}</Button>}</SheetContent></Sheet>

    <div className="world-bottom-row">
      <section className="world-measurements" aria-label={text('过去二十四小时', 'Past 24 hours')}><div><small>{text('过去 24 小时', 'PAST 24 HOURS')}</small><strong>{text('变化正在被看见', 'Change, observed')}</strong></div><dl><div><dt>{text('新变化', 'Fresh changes')}</dt><dd>{metrics?.fresh_external_changes.toLocaleString() ?? '—'}</dd></div><div><dt>{text('知识写入', 'Knowledge writes')}</dt><dd>{metrics?.canonical_writes.toLocaleString() ?? '—'}</dd></div><div><dt>{text('热区驻留', 'Hot residents')}</dt><dd>{hotTotal?.toLocaleString() ?? '—'}</dd></div></dl></section>
      <section className="world-hot-preview" aria-label={text('热点预览', 'Hot preview')}><div><span>{text('热区速览', 'HOT PREVIEW')}</span><button onClick={() => onView('hot')}>{text('查看全部', 'View all')}<ArrowRight size={14} /></button></div>{hotStories.length ? hotStories.slice(0, 2).map(story => <button key={story.story_id} onClick={() => onHotFromAtlas(story)}><Bug size={15} /><strong>{typeof story.facts.cve_id === 'string' ? story.facts.cve_id : story.headline}</strong><span>{story.source_name ?? story.source_id}</span><ArrowRight size={14} /></button>) : <p>{hotFailed ? text('热区暂不可用', 'Hot records unavailable') : hotPending ? text('读取热点中', 'Reading Hot records') : text('当前没有热区记录', 'No resident Hot records')}</p>}</section>
    </div>
  </section>
}
