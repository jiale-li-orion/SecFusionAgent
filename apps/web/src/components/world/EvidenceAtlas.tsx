import { IconTile } from '../ui/icon-tile'
import type { CSSProperties } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { type LucideIcon } from '../ui/icons'
import type { WorldOverview, WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { WorldGlobe } from './WorldGlobe'
import { SourceIdentity } from '../ui/source-identity'
import { Button } from '../ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'

type Direction = { key: string; zh: string; en: string; icon: LucideIcon; path: string }
const sourcePoints = [[125, 105], [310, 58], [505, 70], [653, 160], [630, 344], [430, 408], [218, 389], [79, 269]]
const materialPoints = [[367, 230], [235, 155], [505, 322]]

/** Connections are provenance edges from actual story categories, never inferred object relationships. */
export function EvidenceAtlas({ directions, overview, stories, focusedId, region, onSource, onFocus }: { directions: Direction[]; overview?: WorldOverview; stories: WorldStory[]; focusedId?: string | null; region: string | null; onSource: (key: string) => void; onFocus: (story: WorldStory) => void }) {
  const { text } = useI18n()
  const reducedMotion = useReducedMotion()
  const selected = stories.find(s => s.story_id === focusedId) ?? stories[0]
  const unique = stories.filter((story, i, all) => all.findIndex(s => s.story_id === story.story_id) === i)
  const materials = selected ? [selected, ...unique.filter(s => s.story_id !== selected.story_id)].slice(0, 3) : []
  return <div className={`world-atlas ${region ? 'has-source-focus' : ''}`}>
    <WorldGlobe/>
    <div className="world-atlas-coordinate" aria-hidden="true"><span>{text('点击来源，查看流入的材料', 'Select a source to inspect its material')}</span><span>{text('八类来源', 'Eight domains')}</span></div>
    <svg className="world-graph" viewBox="0 0 740 460" preserveAspectRatio="none" aria-hidden="true">
      <defs><radialGradient id="world-field-glow"><stop stopColor="#91ad97" stopOpacity=".08" /><stop offset="1" stopColor="#91ad97" stopOpacity="0" /></radialGradient><linearGradient id="world-provenance-light" x1="0" x2="1"><stop stopColor="#9cb6a1" stopOpacity=".25" /><stop offset="1" stopColor="#d5c7a8" stopOpacity=".85" /></linearGradient></defs>
      <ellipse cx="370" cy="250" rx="320" ry="200" fill="url(#world-field-glow)" />
      <g className="world-orbit-lines"><ellipse cx="365" cy="236" rx="290" ry="167" transform="rotate(-13 365 236)" /><ellipse cx="365" cy="236" rx="231" ry="133" transform="rotate(-13 365 236)" /><ellipse cx="365" cy="236" rx="164" ry="96" transform="rotate(-13 365 236)" /></g>
      {materials.map((story, i) => { const sourceIndex = directions.findIndex(d => d.key === story.category); if (sourceIndex < 0) return null; const [sx, sy] = sourcePoints[sourceIndex]; const [x, y] = materialPoints[i]; const curve = `M${sx} ${sy} Q${(sx + x) / 2} ${sy - 26} ${x} ${y}`; return <g key={story.story_id} data-category={story.category} className={i === 0 ? 'world-edge is-focused' : 'world-edge'}><motion.path d={curve} initial={reducedMotion ? false : { pathLength: 0 }} animate={{ d: curve, pathLength: 1 }} transition={{ duration: reducedMotion ? 0 : .9, ease: [.16, 1, .3, 1] }} /><circle cx={sx} cy={sy} r="3" /><circle cx={x} cy={y} r={i === 0 ? 7 : 4} /></g> })}

    </svg>
    <TooltipProvider><div className="world-source-nodes" aria-label={text('选择来源方向', 'Choose a source domain')}>{directions.map((d, i) => {
      const [x, y] = sourcePoints[i]
      const count = overview?.sources.filter(source => source.measurement_category === d.key).length
      return <Tooltip key={d.key}><TooltipTrigger asChild><Button variant="ghost" className="world-source-node data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground" data-source={d.key} data-selected={region === d.key} aria-pressed={region === d.key} aria-label={text(`浏览${d.zh}来源`, `Browse ${d.en} sources`)} onClick={() => onSource(d.key)} style={{ left: `${x / 740 * 100}%`, top: `${y / 460 * 100}%` }}><IconTile compact className="world-source-symbol" tone={d.key === 'academic' ? 'violet' : d.key === 'independent' || d.key === 'assets' ? 'teal' : 'cobalt'}><d.icon size={19} weight="duotone"/></IconTile><span>{text(d.zh, d.en)}</span></Button></TooltipTrigger><TooltipContent>{d.key === 'assets' ? text('浏览按需资产观测', 'Explore on-demand asset observations') : text(`浏览材料与来源${count === undefined ? '' : ` · ${count} 个来源`}`, `Explore material and sources${count === undefined ? '' : ` · ${count} sources`}`)}</TooltipContent></Tooltip>
    })}</div></TooltipProvider>
    <div className="world-graph-nodes">{materials.map((story, i) => { const [x, y] = materialPoints[i]; const direction = directions.find(d => d.key === story.category); return <button key={story.story_id} className={`world-material-node ${i === 0 ? 'is-focused' : ''}`} style={{ '--node-x': `${x / 740 * 100}%`, '--node-y': `${y / 460 * 100}%` } as CSSProperties} aria-pressed={story.story_id === focusedId} onClick={() => onFocus(story)}><span className="world-node-mark"><SourceIdentity source={story.source_name ?? story.source_id} url={story.external_ref} compact/></span><span className="world-node-label"><small>{story.source_name?.split(' · ')[0] ?? direction?.en}</small><strong>{story.headline}</strong></span></button> })}</div>
    {!materials.length && <div className="world-map-empty"><span>{text('来源已就位', 'Sources in view')}</span><p>{text('此方向暂无可展示的动态', 'No signals to display in this direction')}</p></div>}
    {region && <button className="world-map-reset" onClick={() => onSource(region)}>{text('回到全景', 'Return to overview')}</button>}
    <div className="world-map-legend"><span><i />{text('来源', 'Source')}</span><span><i />{text('已收录材料', 'Observed material')}</span><span><i />{text('当前焦点', 'Current focus')}</span></div>
  </div>
}
