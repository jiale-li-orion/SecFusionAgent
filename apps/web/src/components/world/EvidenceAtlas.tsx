import { HeroArtifact } from '../instrument/HeroArtifact'
import { ProductGlyph } from '../instrument/ProductGlyph'
import { SourceArtwork } from '../instrument/SourceArtwork'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, ArrowUpRight, type LucideIcon } from 'lucide-react'
import type { WorldOverview, WorldStory, WorldKnowledgeChange } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'

type Direction = { key: string; zh: string; en: string; icon: LucideIcon; path: string }

/** Material placement is spatial composition, not a depiction of runtime traffic. */
export function EvidenceAtlas({ directions, stories, hotStories, focusedId, onSource, onFocus, onHot, onHotSelect, changes, total }: { directions: Direction[]; overview?: WorldOverview; stories: WorldStory[]; hotStories: WorldStory[]; focusedId?: string | null; onSource: (key: string) => void; onFocus: (story: WorldStory) => void; onHot: () => void; onHotSelect: (story: WorldStory) => void; changes: WorldKnowledgeChange[]; total?: number }) {
  const { text } = useI18n()
  const reduced = useReducedMotion()
  const materials = stories.filter(s => s.kind !== 'HotVulnerability')
  const focused = materials.find(s => s.story_id === focusedId) ?? materials[0]
  const neighbours = materials.filter(s => s.story_id !== focused?.story_id).slice(0, 4)
  const direction = directions.find(d => d.key === focused?.category)
  return <div className="vision-atlas">
    <div className="vision-atlas-space">
      <svg className="vision-orbits" viewBox="0 0 600 520" aria-hidden="true"><defs><radialGradient id="world-material-light"><stop stopColor="#93b4bc" stopOpacity=".18"/><stop offset="1" stopColor="#93b4bc" stopOpacity="0"/></radialGradient></defs><ellipse cx="310" cy="275" rx="275" ry="210" fill="url(#world-material-light)"/><g fill="none" stroke="#9db4bc" strokeOpacity=".12"><ellipse cx="310" cy="275" rx="235" ry="135" transform="rotate(-18 310 275)"/><ellipse cx="310" cy="275" rx="285" ry="180" transform="rotate(-18 310 275)"/><path d="M35 410 565 160M120 70 465 485"/></g></svg>
      {focused && <motion.button key={focused.story_id} className={`vision-material-focus category-${focused.category}`} initial={reduced ? false : {opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.35}} onClick={() => onSource(focused.category)} aria-label={text('查看这份材料的来源', 'Inspect the source of this material')}><HeroArtifact kind={focused.category}/><span><ProductGlyph kind={focused.category} size={18}/>{direction ? text(direction.zh,direction.en) : focused.category}<ArrowUpRight size={14}/></span><small>{direction?.path}</small></motion.button>}
      <div className="vision-material-satellites">{neighbours.map((s,i) => <button key={s.story_id} className={`vision-material-neighbour material-position-${i}`} onClick={() => onFocus(s)}><span className="vision-neighbour-art"><SourceArtwork category={s.category} index={i+1}/></span><span className="vision-neighbour-copy"><small>{s.source_name?.split(' · ')[0] ?? s.category}</small><strong>{s.headline}</strong></span><ArrowUpRight size={13}/></button>)}</div>
    </div>
    <div className="vision-world-measures"><button onClick={onHot}><span>{text('热区驻留', 'Hot residency')}</span><strong>{total === undefined ? '—' : total.toLocaleString()}</strong></button><span>{changes[0] ? text('最近知识留存', 'Latest knowledge commit')+' · '+new Date(changes[0].committed_at).toLocaleTimeString() : text('读取知识留存记录', 'Reading knowledge commits')}</span></div>
    {hotStories.length > 0 && <div className="vision-hot-preview"><div className="vision-hot-preview-head"><div><small>LIVE / HOT WORKING SET</small><strong>{text('此刻变热的漏洞', 'Vulnerabilities gaining attention')}</strong><span>{text('当前排名预览，缓存记录不等于持久知识', 'Current ranking preview; cache records are not durable knowledge')}</span></div><button onClick={onHot}>{text('浏览热区', 'Browse Hot')}<ArrowRight size={14} /></button></div><div className="vision-hot-preview-list">{hotStories.slice(0, 4).map((story, index) => <button key={story.story_id} onClick={() => onHotSelect(story)}><small>{String(index + 1).padStart(2, '0')} / {story.source_name ?? story.source_id}</small><strong>{typeof story.facts.cve_id === 'string' ? story.facts.cve_id : story.headline}</strong><span>{story.headline}</span><ArrowUpRight size={14} /></button>)}</div></div>}
  </div>
}
