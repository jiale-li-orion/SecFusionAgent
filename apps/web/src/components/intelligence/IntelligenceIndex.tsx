import { useState } from 'react'
import { ArrowRight, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'motion/react'
import { HeroArtifact } from '../instrument/HeroArtifact'
import { ProductGlyph } from '../instrument/ProductGlyph'
import { SourceArtwork } from '../instrument/SourceArtwork'
import type { HotBug, WorldIncidentCandidate, WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'

const kinds = [
  { key: 'academic', zh: '研究', en: 'Research' },
  { key: 'development', zh: '开发', en: 'Development' },
  { key: 'vulnerability', zh: '漏洞', en: 'Vulnerabilities' },
  { key: 'vendor', zh: '厂商', en: 'Vendors' },
  { key: 'normative', zh: '标准', en: 'Standards' },
  { key: 'independent', zh: '独立情报', en: 'Independent' },
  { key: 'assets', zh: '资产', en: 'Assets' },
  { key: 'incidents', zh: '事件', en: 'Incidents' },
]

type Props = {
  stories: WorldStory[]
  hot: HotBug[]
  hotTotal: number
  candidates: WorldIncidentCandidate[]
  candidateTotal: number
  loading: boolean
  hotLoading: boolean
  candidateLoading: boolean
  error: string | null
  hotError: string | null
  candidateError: string | null
  onSelect: (story: WorldStory) => void
  onHotSelect: (item: HotBug) => void
  onCandidateSelect: (item: WorldIncidentCandidate) => void
}

function hotKey(item: HotBug): string {
  return `${item.source_id}:${item.external_object_id}`
}

export function IntelligenceIndex({ stories, hot, hotTotal, candidates, candidateTotal, loading, hotLoading, candidateLoading, error, hotError, candidateError, onSelect, onHotSelect, onCandidateSelect }: Props) {
  const { text } = useI18n()
  const reduced = useReducedMotion()
  const [category, setCategory] = useState<string | null>(null)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const isHot = category === 'vulnerability'
  const isCandidate = category === 'incidents'
  const items = stories.filter(story => (story.object_id || story.incident_id) && (!category || story.category === category))
  const hotItems = hot.filter(item => Boolean(item.cve_id ?? item.external_object_id)).slice(0, 16)
  const selected = items.find(story => story.story_id === previewId) ?? items[0]
  const selectedHot = hotItems.find(item => hotKey(item) === previewId) ?? hotItems[0]
  const selectedCandidate = candidates.find(item => item.candidate_id === previewId) ?? candidates[0]
  const kind = kinds.find(item => item.key === selected?.category)

  return <section className="vision-library">
    <div className="catalog-filters">
      <button className={!category ? 'active' : ''} aria-pressed={!category} onClick={() => setCategory(null)}>{text('全部资料', 'All material')}</button>
      {kinds.map(item => <button key={item.key} className={category === item.key ? 'active' : ''} aria-pressed={category === item.key} onClick={() => { setCategory(item.key); setPreviewId(null) }}><ProductGlyph kind={item.key} size={17} />{text(item.zh, item.en)}</button>)}
    </div>

    {isHot && selectedHot && <motion.article key={hotKey(selectedHot)} className="vision-folio vision-hot-folio" initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25 }}>
      <div className="vision-folio-copy">
        <div className="vision-material-origin"><ProductGlyph kind="vulnerability" size={22} /><span>{text('漏洞热区', 'Vulnerability hot set')}</span><i /><span>{selectedHot.source_name ?? selectedHot.source_id}</span></div>
        <div className="vision-hot-authority">{text('Hot working set · 可变观测，打开档案后检查持久证据', 'Hot working set · mutable observation; inspect durable evidence in the dossier')}</div>
        <h2>{selectedHot.cve_id ?? selectedHot.external_object_id}</h2>
        {selectedHot.title && <p className="vision-hot-title">{selectedHot.title}</p>}
        {selectedHot.description && <blockquote>{selectedHot.description}</blockquote>}
        <div className="vision-folio-actions"><button className="ew-primary" onClick={() => onHotSelect(selectedHot)}>{text('打开漏洞视图', 'Open vulnerability view')}<ArrowRight size={17} /></button>{selectedHot.canonical_url && <a href={selectedHot.canonical_url} target="_blank" rel="noreferrer">{text('来源原文', 'Original source')}<ArrowUpRight size={14} /></a>}</div>
        <time>{text('最近读取', 'Last read')} {new Date(selectedHot.updated_at ?? selectedHot.fetched_at).toLocaleDateString()}</time>
      </div>
      <div className="vision-folio-art"><HeroArtifact kind="vulnerability" /><span>HOT / VULNERABILITY</span></div>
    </motion.article>}

    {isCandidate && selectedCandidate && <motion.article key={selectedCandidate.candidate_id} className="vision-folio vision-candidate-folio" initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25 }}>
      <div className="vision-folio-copy">
        <div className="vision-material-origin"><ProductGlyph kind="incidents" size={22} /><span>{text('事件观察', 'Incident watch')}</span><i /><span>{selectedCandidate.source_name ?? selectedCandidate.source_id}</span></div>
        <div className="vision-hot-authority">{text('候选信号 · 仍需独立来源或直接证据，尚未固定为事件档案', 'Candidate signal · independent corroboration or direct evidence pending; no durable incident yet')}</div>
        <h2>{selectedCandidate.headline}</h2>
        {selectedCandidate.summary && <blockquote>{selectedCandidate.summary}</blockquote>}
        <div className="vision-folio-actions"><button className="ew-primary" onClick={() => onCandidateSelect(selectedCandidate)}>{text('查看信号来处', 'Inspect the signal')}<ArrowRight size={17} /></button>{selectedCandidate.canonical_url && <a href={selectedCandidate.canonical_url} target="_blank" rel="noreferrer">{text('来源原文', 'Original source')}<ArrowUpRight size={14} /></a>}</div>
        <time>{text('观察于', 'Observed')} {new Date(selectedCandidate.observed_at).toLocaleDateString()}</time>
      </div>
      <div className="vision-folio-art"><HeroArtifact kind="incidents" /><span>INCIDENT / WATCH</span></div>
    </motion.article>}

    {!isHot && !isCandidate && selected && <motion.article key={selected.story_id} className="vision-folio" initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25 }}>
      <div className="vision-folio-copy">
        <div className="vision-material-origin"><ProductGlyph kind={selected.category} size={22} /><span>{kind ? text(kind.zh, kind.en) : selected.category}</span><i /><span>{selected.source_name?.split(' · ')[0] ?? selected.category}</span></div>
        <h2>{selected.headline}</h2>
        {selected.excerpt && <blockquote>{selected.excerpt}</blockquote>}
        <div className="vision-folio-actions"><button className="ew-primary" onClick={() => onSelect(selected)}>{text('打开完整档案', 'Open dossier')}<ArrowRight size={17} /></button>{selected.external_ref && <a href={selected.external_ref} target="_blank" rel="noreferrer">{text('来源原文', 'Original source')}<ArrowUpRight size={14} /></a>}</div>
        <time>{text('收录于', 'Retained')} {new Date(selected.observed_at).toLocaleDateString()}</time>
      </div>
      <div className="vision-folio-art"><HeroArtifact kind={selected.category} /><span>{kind ? text(kind.zh, kind.en) : selected.category}</span></div>
    </motion.article>}

    <div className="vision-shelf-heading"><span>{isHot ? text('当前漏洞热区', 'CURRENT VULNERABILITY WINDOW') : isCandidate ? text('事件候选观察', 'INCIDENT SIGNAL WATCH') : text('在材料之间探索', 'EXPLORE THE COLLECTION')}</span><div className="vision-shelf-tools"><small>{isHot ? hotLoading ? text('读取热区…', 'Loading hot set…') : text(`${hotItems.length} 条已载入 · ${hotTotal.toLocaleString()} 条驻留`, `${hotItems.length} loaded · ${hotTotal.toLocaleString()} resident`) : isCandidate ? candidateLoading ? text('读取候选…', 'Loading candidates…') : text(`${candidates.length} 条已载入 · ${candidateTotal} 条相关候选`, `${candidates.length} loaded · ${candidateTotal} relevant candidates`) : loading ? text('读取中…', 'Loading…') : text(`${items.length} 份精选资料`, `${items.length} selected materials`)}</small>{isHot && <Link to="/?view=hot" className="vision-hot-index-link">{text('浏览热区排行', 'Browse Hot ranking')}<ArrowUpRight size={13} /></Link>}</div></div>
    {isHot ? <div className="vision-folio-shelf">{hotItems.map((item, index) => <button key={hotKey(item)} aria-pressed={selectedHot === item} onClick={() => setPreviewId(hotKey(item))} className={`vision-shelf-item ${selectedHot === item ? 'selected' : ''}`}><div><SourceArtwork category="vulnerability" index={index} /><ProductGlyph kind="vulnerability" size={18} /></div><small>{item.source_name ?? item.source_id} · HOT</small><strong>{item.cve_id ?? item.external_object_id}</strong></button>)}</div> : isCandidate ? <div className="vision-folio-shelf">{candidates.map((item, index) => <button key={item.candidate_id} aria-pressed={selectedCandidate === item} onClick={() => setPreviewId(item.candidate_id)} className={`vision-shelf-item ${selectedCandidate === item ? 'selected' : ''}`}><div><SourceArtwork category="incidents" index={index} /><ProductGlyph kind="incidents" size={18} /></div><small>{item.source_name ?? item.source_id} · {text('候选', 'CANDIDATE')}</small><strong>{item.headline}</strong></button>)}</div> : <div className="vision-folio-shelf">{items.map((story, index) => <button key={story.story_id} aria-pressed={selected?.story_id === story.story_id} onClick={() => setPreviewId(story.story_id)} className={`vision-shelf-item ${selected?.story_id === story.story_id ? 'selected' : ''}`}><div><SourceArtwork category={story.category} index={index} /><ProductGlyph kind={story.category} size={18} /></div><small>{story.source_name?.split(' · ')[0] ?? story.category}</small><strong>{story.headline}</strong></button>)}</div>}
    {isHot && hotError && <p role="alert">{hotError}</p>}
    {isCandidate && candidateError && <p role="alert">{candidateError}</p>}
    {!isHot && !isCandidate && error && <p role="alert">{error}</p>}
    {isHot && !hotLoading && !hotItems.length && !hotError && <p className="catalog-empty">{text('当前热区没有可读取的漏洞。来源恢复后会自动更新。', 'The hot set has no readable vulnerability right now. It updates when sources recover.')}</p>}
    {isCandidate && !candidateLoading && !candidates.length && !candidateError && <p className="catalog-empty">{text('当前没有可展示的安全事件候选信号。确认后的事件档案仍可通过搜索进入。', 'No presentable security incident candidates right now. Confirmed incident dossiers remain searchable.')}</p>}
    {!isHot && !isCandidate && !loading && !items.length && !error && <p className="catalog-empty">{text('当前精选窗口没有这一类的持久资料。可以搜索具体对象，或到世界页查看来源。', 'No retained material from this category is in the current selection. Search an object or inspect its sources in World.')}</p>}
  </section>
}
