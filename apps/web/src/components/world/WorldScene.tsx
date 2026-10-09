import { SourceArtwork } from '../instrument/SourceArtwork'
import { ProductGlyph } from '../instrument/ProductGlyph'
import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { ArrowRight, ArrowUpRight, BookOpen, Braces, Bug, Fingerprint, Globe2, Layers3, Radio, Scale, Shield, X } from 'lucide-react'
import type { WorldFormation, WorldOverview, WorldStory, WorldKnowledgeChange } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { EvidenceAtlas } from './EvidenceAtlas'
import { SpaceHeading } from '../instrument/SpaceHeading'
import { WorldSourceInspector } from './WorldSourceInspector'
import { WorldHotField, WorldFormationField, WorldSourcesField } from './WorldActivityField'

const categories = [
  { key: 'vulnerability', zh: '漏洞', en: 'Vulnerabilities', icon: Bug, path: 'Bug Stream' },
  { key: 'development', zh: '代码', en: 'Development', icon: Braces, path: 'Development Index' },
  { key: 'academic', zh: '研究', en: 'Research', icon: BookOpen, path: 'Insight Corpus' },
  { key: 'vendor', zh: '厂商', en: 'Vendors', icon: Shield, path: 'Insight Corpus' },
  { key: 'independent', zh: '独立情报', en: 'Independent', icon: Radio, path: 'Insight Corpus' },
  { key: 'normative', zh: '标准', en: 'Standards', icon: Scale, path: 'Insight Corpus' },
  { key: 'assets', zh: '资产', en: 'Assets', icon: Globe2, path: 'Asset Observation' },
  { key: 'incidents', zh: '事件', en: 'Incidents', icon: Fingerprint, path: 'Incident Watch' },
]

export function WorldScene({ stories, hotStories, focusedId, pending, failed, candidatePending, candidateFailed, onFocus, onHotFromAtlas, onOpen, onInvestigate, onRetry, onCandidateRetry, view, onView, overview, overviewFailed, onOverviewRetry, formation, formationFailed, onFormationRetry, hotTotal, hotFailed, hotPending, hotPage, hotPageSize, onHotPage, region, onRegion, onHotRetry, changes }: {
  changes: WorldKnowledgeChange[]; stories: WorldStory[]; hotStories: WorldStory[]; focusedId: string | null; pending: boolean; failed: boolean; candidatePending: boolean; candidateFailed: boolean
  onFocus: (story: WorldStory) => void; onHotFromAtlas: (story: WorldStory) => void; onOpen: (story: WorldStory) => void
  onInvestigate: (story: WorldStory) => void; onRetry: () => void; onCandidateRetry: () => void
  view: string; onView: (view: string) => void; overview: WorldOverview | undefined; overviewFailed: boolean; onOverviewRetry: () => void; formation: WorldFormation | undefined; formationFailed: boolean; onFormationRetry: () => void; hotTotal: number | undefined; hotFailed: boolean; hotPending: boolean; hotPage: number; hotPageSize: number; onHotPage: (page: number) => void; region: string | null; onRegion: (region: string | null) => void; onHotRetry: () => void
}) {
  const { text, language } = useI18n()
  const reduced = useReducedMotion()
  const [inspect, setInspect] = useState(false)
  const setRegion = onRegion
  const available = view === 'hot' ? stories.filter(s => s.kind === 'HotVulnerability') : region === 'vulnerability' ? stories : stories.filter(s => s.kind !== 'HotVulnerability')
  const regionStories = region ? available.filter(s => s.category === region) : available
  const focused = regionStories.find(s => s.story_id === focusedId) ?? regionStories[0] ?? null
  const direction = categories.find(c => c.key === region)
  const category = categories.find(c => c.key === focused?.category)
  const canOpenDossier = Boolean(focused?.object_id || focused?.incident_id || (focused?.kind === 'HotVulnerability' && focused.facts.cve_id))
  const canInvestigate = Boolean(focused?.object_id || focused?.incident_id || (focused?.kind === 'HotVulnerability' && focused.facts.cve_id))
  const regionReadFailed = region === 'incidents' ? candidateFailed : failed
  const regionReadPending = region === 'incidents' ? candidatePending : pending
  const emptyState = (() => {
    if (view === 'sources') {
      if (overviewFailed) return { title: text('来源状态暂时不可读', 'Source status is unavailable'), detail: text('来源方向仍可浏览；健康读数需要重新读取。', 'Source directions remain available; health readings need a retry.'), retry: onOverviewRetry }
      if (overview) return overview.sources.length
        ? { title: text(`正在观察 ${overview.sources.length} 个来源`, `Observing ${overview.sources.length} sources`), detail: text(`${overview.source_health.healthy} 个健康，${overview.source_health.degraded} 个降级，${overview.source_health.blocked} 个阻塞。选择方向查看每个来源。`, `${overview.source_health.healthy} healthy, ${overview.source_health.degraded} degraded, ${overview.source_health.blocked} blocked. Choose a direction to inspect its sources.`), retry: null }
        : { title: text('当前没有来源配置', 'No sources configured'), detail: text('来源方向可浏览，运行读数会在配置来源后出现。', 'Source directions remain browsable; operational readings appear after sources are configured.'), retry: null }
      return { title: text('读取来源状态', 'Reading source status'), detail: '', retry: null }
    }
    if (view === 'hot') {
      if (hotFailed) return { title: text('热区暂时不可读', 'Hot index is unavailable'), detail: text('驻留量和索引需要重新读取。', 'Residency and the index need a retry.'), retry: onHotRetry }
      if (hotPending) return { title: text('读取热区漏洞', 'Reading Hot vulnerabilities'), detail: '', retry: null }
      return { title: text('当前页没有热区漏洞', 'No Hot vulnerabilities on this page'), detail: text('可以翻页或输入完整 CVE 编号查找整个驻留热区。', 'Change page or enter a complete CVE ID to search the resident pool.'), retry: null }
    }
    if (view === 'formation') {
      if (formationFailed) return { title: text('处理记录暂时不可读', 'Processing records are unavailable'), detail: '', retry: onFormationRetry }
      if (formation) return formation.processing.length
        ? { title: text(`最近 ${formation.processing.length} 条处理记录`, `${formation.processing.length} recent processing records`), detail: text('选择右侧记录，查看处理状态和知识提交。', 'Select a run to inspect its status and knowledge commit.'), retry: null }
        : { title: text('近期没有富化处理记录', 'No recent enrichment runs'), detail: text('来源与热区仍可独立浏览。', 'Sources and Hot records remain available.'), retry: null }
      return { title: text('读取处理记录', 'Reading processing records'), detail: '', retry: null }
    }
    if (regionReadFailed) return { title: text('这个方向暂时无法读取', 'Could not read this direction'), detail: '', retry: region === 'incidents' ? onCandidateRetry : onRetry }
    if (regionReadPending) return { title: text('正在读取世界动态', 'Reading world signals'), detail: '', retry: null }
    return { title: region ? text('这个方向暂无可读材料', 'No readable material in this direction') : text('当前没有新的世界动态', 'No new world signals right now'), detail: text('来源和热区仍可独立浏览。', 'Sources and the Hot index remain available.'), retry: null }
  })()

  return <section className={`evidence-world studio-world ${inspect || region ? 'is-inspecting' : ''}`} aria-label={text('AI 安全证据世界', 'AI security evidence world')}>
    <SpaceHeading index="01" eyebrow="WORLD / EVIDENCE PLANE" title={text('证据世界', 'Evidence world')} description={text('八类来源，四路汇聚。观察信息如何进入、变热，并被留存。', 'Eight source domains. Four processing routes. Follow information into a traceable world.')}><button className="ew-inspect-toggle" onClick={() => { setInspect(!inspect); setRegion(null) }} aria-expanded={inspect}><Layers3 size={16} />{text('追溯证据', 'Trace evidence')}</button></SpaceHeading>
    <div className="ew-live-read"><p>{overview ? text(`过去 24 小时，完成 ${overview.windows['24h']?.scheduled_runs ?? 0} 次定时采集，捕获 ${overview.windows['24h']?.fresh_external_changes ?? 0} 次新变化，产生 ${overview.windows['24h']?.canonical_writes ?? 0} 次知识写入。`, `In the past 24 hours: ${overview.windows['24h']?.scheduled_runs ?? 0} scheduled acquisitions, ${overview.windows['24h']?.fresh_external_changes ?? 0} fresh changes and ${overview.windows['24h']?.canonical_writes ?? 0} knowledge writes.`) : overviewFailed ? text('来源与采集状态暂时不可读。', 'Source and acquisition status is unavailable.') : text('读取最近的采集与知识变化', 'Reading recent acquisition and knowledge changes')}</p>{overview ? <small>{text('测量于', 'Measured')} {new Date(overview.generated_at).toLocaleTimeString(language === 'zh' ? 'zh-CN' : 'en-US')}</small> : overviewFailed && <button onClick={onOverviewRetry}>{text('重试状态读取', 'Retry status read')}</button>}</div>
    <div className="ew-composition">
      <div className="ew-horizon" aria-hidden="true" />
      <div className="ew-foreground">
        <AnimatePresence mode="wait" initial={false}>
          {focused ? <motion.article key={focused.story_id} className="ew-story"
            initial={reduced ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: reduced ? 0 : .2 }}>
            <div className="vision-story-mobile-art"><SourceArtwork category={focused.category} index={0}/></div>
            <div className="ew-story-origin"><ProductGlyph kind={focused.category} size={23} /><span>{category ? text(category.zh, category.en) : text('世界信号', 'World signal')}</span><i /><span>{sourceLabel(focused)}</span></div>
            {typeof focused.facts.repo_full_name === 'string' && <p className="ew-repository">{focused.facts.repo_full_name}</p>}
            <h2>{focused.headline}</h2>
            <p className="ew-observed">{focused.published_at && <><time dateTime={focused.published_at}>{formatDate(focused.published_at, language)}</time> {text('发布', 'published')} · </>}{text('收录于', 'Observed')} <time dateTime={focused.observed_at}>{formatDate(focused.observed_at, language)}</time></p>
            {focused.kind === 'InternetAsset' && <p className="ew-asset-observation">{text(`${sourceLabel(focused)} 记录了这个地址的公网资产观察。`, `${sourceLabel(focused)} recorded an Internet asset observation for this address.`)}</p>}
            {focused.kind === 'IncidentCandidate' && <p className="ew-asset-observation">{text('事件候选信号 · 尚在关联与核验，未固定为事件档案。', 'Candidate signal · correlation and verification pending; no durable incident yet.')}</p>}
            {focused.excerpt && <div className="ew-excerpt"><span>{text('来源原文 · 保留原语言', 'From the source')}</span><blockquote>{focused.excerpt}</blockquote></div>}
            <div className="ew-actions">
              {canOpenDossier ? <button className="ew-primary" onClick={() => onOpen(focused)}>{text(focused.incident_id ? '打开事件档案' : '进入对象', focused.incident_id ? 'Open incident dossier' : 'Explore object')} <ArrowUpRight size={17} /></button>
                : <button className="ew-primary" onClick={() => { setInspect(true); setRegion(null) }}>{text('查看信号详情', 'Inspect signal details')} <ArrowUpRight size={17} /></button>}
              {canInvestigate && <button onClick={() => onInvestigate(focused)}>{focused.incident_id && !focused.object_id ? text('检索事件证据', 'Search incident evidence') : text('继续调查', 'Investigate')} <ArrowRight size={17} /></button>}
            </div>
            {focused.external_ref && <a className="ew-original" href={focused.external_ref} target="_blank" rel="noreferrer">{text('阅读完整原文', 'Read the original')}<ArrowUpRight size={13} /></a>}
          </motion.article> : <div className="ew-first-read" role="status">
            <ProductGlyph kind={view === 'formation' ? 'intelligence' : view === 'sources' ? 'world' : view === 'hot' ? 'vulnerability' : 'world'} size={38} /><h2>{emptyState.title}</h2>
            {emptyState.detail && <p>{emptyState.detail}</p>}
            {emptyState.retry && <button onClick={emptyState.retry}>{text('重新读取', 'Retry')}</button>}
            {region && <button onClick={() => setRegion(null)}>{text('回到整个世界', 'View the whole world')}<ArrowRight size={16} /></button>}
          </div>}
        </AnimatePresence>
      </div>
      <div className="ew-space-region">
      <div className="ew-field-views" aria-label={text('观察世界', 'Observe the world')}>{[{ key: 'stories', zh: '世界动态', en: 'Signals' }, { key: 'sources', zh: '来源汇聚', en: 'Sources' }, { key: 'hot', zh: '浏览热区', en: 'Hot' }, { key: 'formation', zh: '富化与留存', en: 'Processing' }].map(v => <button key={v.key} aria-pressed={view === v.key} onClick={() => onView(v.key)}>{text(v.zh, v.en)}</button>)}</div>
      {view === 'sources' ? <WorldSourcesField sources={overview?.sources} failed={overviewFailed} directions={categories} onSource={category => { setRegion(category); setInspect(false) }} onRetry={onOverviewRetry} /> : view === 'hot' ? <WorldHotField stories={hotStories} focusedId={focused?.story_id} total={hotTotal} failed={hotFailed} pending={hotPending} page={hotPage} pageSize={hotPageSize} onPage={onHotPage} onFocus={onFocus} onRetry={onHotRetry} /> : view === 'formation' ? <WorldFormationField formation={formation} failed={formationFailed} onRetry={onFormationRetry} /> : <EvidenceAtlas onHot={() => onView('hot')} onHotSelect={onHotFromAtlas} hotStories={hotStories} directions={categories} overview={overview} stories={region ? regionStories : stories} focusedId={focused?.story_id} onSource={key => { setRegion(key); setInspect(false) }} onFocus={story => { onFocus(story); setInspect(false) }} changes={changes} total={hotTotal} />}
      </div>
      {region && direction && <WorldSourceInspector category={region} label={text(direction.zh, direction.en)} path={direction.path} materials={stories} onClose={() => setRegion(null)} />}
      {inspect && !region && focused && <aside className="ew-inspector" aria-label={text('当前对象的证据来源', 'Evidence for the focused object')}>
        <div className="ew-inspector-head"><span>{text('证据来处', 'Evidence provenance')}</span><button onClick={() => setInspect(false)} aria-label={text('关闭证据追溯', 'Close evidence trace')}><X size={18} /></button></div>
        <h3>{focused.headline}</h3>
        <p>{sourceLabel(focused)} <ArrowRight size={14} /> {category?.path}</p>
        <div className="ew-provenance"><span>{text('外部来源', 'Source')}<strong>{sourceLabel(focused)}</strong></span><i /><span>{text('材料状态', 'Material status')}<strong>{focused.kind === 'IncidentCandidate' ? text('候选信号', 'Candidate signal') : focused.kind === 'HotVulnerability' ? text('热区观测', 'Hot observation') : focused.evidence?.document_revision_id ? text('原文与版本', 'Document and revision') : text('对象观察', 'Object observation')}</strong></span><i /><span>{text('当前落点', 'Current destination')}<strong>{focused.kind === 'IncidentCandidate' ? 'Incident Watch' : focused.kind === 'HotVulnerability' ? 'Hot working set' : focused.incident_id ? 'Incident' : 'Evidence · Knowledge'}</strong></span></div>
        {focused.excerpt && <blockquote>{focused.excerpt}</blockquote>}
        {focused.external_ref && <a href={focused.external_ref} target="_blank" rel="noreferrer">{text('打开来源原文', 'Open source')} <ArrowUpRight size={15} /></a>}
        <details><summary>{text('查看技术坐标', 'Technical coordinates')}</summary><pre>{JSON.stringify({ evidence: focused.evidence, facts: focused.facts, observed_at: focused.observed_at, happened_at: focused.happened_at }, null, 2)}</pre></details>
      </aside>}
    </div>
    <footer className="ew-boundary">
      <span className="ew-source-label">{text('来源 → 处理路径 → 证据世界', 'Sources → processing paths → evidence world')}</span>
      <div className="ew-directions" aria-label={text('世界的八类来源', 'Eight source directions')}>
        {categories.map(c => { return <button key={c.key} className={region === c.key ? 'active' : ''} aria-pressed={region === c.key}
          onClick={() => { setRegion(region === c.key ? null : c.key); setInspect(false) }}><ProductGlyph kind={c.key} size={20} /><span>{text(c.zh, c.en)}</span></button> })}
      </div>
      {focused && <button className="ew-current-path" onClick={() => { setInspect(true); setRegion(null) }}><span>{sourceLabel(focused)}</span><ArrowRight size={14} /><span>{category?.path}</span><ArrowRight size={14} /><strong>{focused.kind === 'IncidentCandidate' ? text('候选信号 · 尚未固定为事件', 'Candidate · no durable incident yet') : focused.kind === 'HotVulnerability' ? text('热区驻留 · 尚未据此声明知识留存', 'Hot residency') : focused.incident_id ? text('已留存事件', 'Retained incident') : text('已留存原文与对象', 'Retained material and object')}</strong><span>{text('查看来处', 'Trace this path')} <ArrowUpRight size={12} /></span></button>}
      <div className="ew-retention"><span>Evidence</span><i /><span>Knowledge</span><i /><span>Incident</span><i /><span>Insight</span><i /><span>Experience</span></div>
      {pending && stories.length > 0 && <span role="status">{text('正在更新', 'Updating')}</span>}
    </footer>
  </section>
}

function sourceLabel(story: WorldStory) {
  if (story.source_name) return story.source_name.split(' · ')[0]
  if (story.external_ref) { try { return new URL(story.external_ref).hostname } catch { /* malformed upstream URL */ } }
  return story.source_id ?? ''
}
function formatDate(value: string, language: string) {
  return new Date(value).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}
