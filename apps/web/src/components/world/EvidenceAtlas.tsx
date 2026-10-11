import type { CSSProperties } from 'react'
import { ArrowUpRight, type LucideIcon } from 'lucide-react'
import type { WorldOverview, WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { WorldGlobe } from './WorldGlobe'
import { SourceIdentity } from '../ui/source-identity'

type Direction = { key: string; zh: string; en: string; icon: LucideIcon; path: string }
const sourcePoints = [[125, 105], [310, 58], [505, 70], [653, 160], [630, 344], [430, 408], [218, 389], [79, 269]]
const materialPoints = [[367, 226], [221, 143], [520, 152], [521, 328], [211, 316]]

/** Connections are provenance edges from actual story categories, never inferred object relationships. */
export function EvidenceAtlas({ directions, stories, focusedId, region, onSource, onFocus }: { directions: Direction[]; overview?: WorldOverview; stories: WorldStory[]; focusedId?: string | null; region: string | null; onSource: (key: string) => void; onFocus: (story: WorldStory) => void }) {
  const { text } = useI18n()
  const selected = stories.find(s => s.story_id === focusedId) ?? stories[0]
  const unique = stories.filter((story, i, all) => all.findIndex(s => s.story_id === story.story_id) === i)
  const materials = selected ? [selected, ...unique.filter(s => s.story_id !== selected.story_id)].slice(0, 5) : []
  return <div className={`world-atlas ${region ? 'has-source-focus' : ''}`}>
    <WorldGlobe/>
    <div className="world-atlas-coordinate" aria-hidden="true"><span>SOURCE CONSTELLATION</span><span>01 — 08</span></div>
    <svg className="world-graph" viewBox="0 0 740 460" preserveAspectRatio="none" aria-hidden="true">
      <defs><radialGradient id="world-field-glow"><stop stopColor="#4263eb" stopOpacity=".16" /><stop offset="1" stopColor="#4263eb" stopOpacity="0" /></radialGradient><linearGradient id="world-provenance-light" x1="0" x2="1"><stop stopColor="#7395ff" stopOpacity=".12" /><stop offset="1" stopColor="#84dcf5" stopOpacity=".7" /></linearGradient></defs>
      <ellipse cx="370" cy="250" rx="320" ry="200" fill="url(#world-field-glow)" />
      <g className="world-orbit-lines"><ellipse cx="365" cy="236" rx="290" ry="167" transform="rotate(-13 365 236)" /><ellipse cx="365" cy="236" rx="231" ry="133" transform="rotate(-13 365 236)" /><ellipse cx="365" cy="236" rx="164" ry="96" transform="rotate(-13 365 236)" /><path d="M58 306 662 166M150 40 575 430" /></g>
      {materials.map((story, i) => { const sourceIndex = directions.findIndex(d => d.key === story.category); if (sourceIndex < 0) return null; const [sx, sy] = sourcePoints[sourceIndex]; const [x, y] = materialPoints[i]; return <g key={story.story_id} className={i === 0 ? 'world-edge is-focused' : 'world-edge'}><path d={`M${sx} ${sy} Q${(sx + x) / 2} ${sy - 26} ${x} ${y}`} /><circle cx={sx} cy={sy} r="3" /><circle cx={x} cy={y} r={i === 0 ? 7 : 4} /></g> })}
      {directions.map((d, i) => { const [x, y] = sourcePoints[i]; const active = !region || region === d.key; return <g key={d.key} className={`world-graph-domain ${active ? 'is-active' : ''}`}><circle cx={x} cy={y} r="15" /><circle cx={x} cy={y} r="3" /><text x={x} y={y + 31} textAnchor="middle">{text(d.zh, d.en)}</text></g> })}
    </svg>
    <div className="world-graph-nodes">{materials.map((story, i) => { const [x, y] = materialPoints[i]; const direction = directions.find(d => d.key === story.category); return <button key={story.story_id} className={`world-material-node ${i === 0 ? 'is-focused' : ''}`} style={{ '--node-x': `${x / 740 * 100}%`, '--node-y': `${y / 460 * 100}%` } as CSSProperties} aria-pressed={story.story_id === focusedId} onClick={() => onFocus(story)}><span className="world-node-mark"><SourceIdentity source={story.source_name ?? story.source_id} url={story.external_ref} compact/></span><span className="world-node-label"><small>{story.source_name?.split(' · ')[0] ?? direction?.en}</small><strong>{story.headline}</strong></span><ArrowUpRight size={12} className="world-node-arrow" /></button> })}</div>
    {!materials.length && <div className="world-map-empty"><span>{text('来源已就位', 'Sources in view')}</span><p>{text('此方向暂无可展示的动态', 'No signals to display in this direction')}</p></div>}
    {region && <button className="world-map-reset" onClick={() => onSource(region)}>{text('回到全景', 'Return to overview')}<ArrowUpRight size={13} /></button>}
    <div className="world-map-legend"><span><i />{text('来源', 'Source')}</span><span><i />{text('已收录材料', 'Observed material')}</span><span><i />{text('当前焦点', 'Current focus')}</span></div>
  </div>
}
