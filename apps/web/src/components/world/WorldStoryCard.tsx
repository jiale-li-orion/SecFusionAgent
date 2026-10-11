import { useState } from 'react'
import { ArrowRight, ArrowUpRight, ChevronDown, Radio } from 'lucide-react'
import type { WorldStory } from '../../lib/api/world'
import { Button } from '../ui/button'
import { useI18n } from '../../lib/i18n'

export function WorldStoryCard({ story, onOpen, onInvestigate }: { story: WorldStory; onOpen: (story: WorldStory) => void; onInvestigate: (story: WorldStory) => void }) {
  const { text, language } = useI18n()
  const [expanded, setExpanded] = useState<string | null>(null)
  const canOpen = Boolean(story.object_id || story.incident_id || (story.kind === 'HotVulnerability' && story.facts.cve_id))
  const time = (value: string) => new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  return <article className="world-story-card">
    <span className="world-panel-kicker"><Radio size={14} />{text('当前焦点', 'IN FOCUS')}</span>
    <p className="world-story-source">{story.source_name?.split(' · ')[0] ?? story.source_id ?? text('世界动态', 'World signal')}<span>{story.kind === 'IncidentCandidate' ? text('事件候选', 'Candidate signal') : story.kind === 'HotVulnerability' ? text('热区记录', 'Hot record') : text('已收录', 'Observed')}</span></p>
    <h2>{story.headline}</h2>
    {story.excerpt && <p className="world-story-excerpt">{story.excerpt}</p>}
    <div className="world-story-time">{story.published_at && <span>{text('来源发布', 'Published')} <time dateTime={story.published_at}>{time(story.published_at)}</time></span>}<span>{text('系统发现', 'Observed')} <time dateTime={story.observed_at}>{time(story.observed_at)}</time></span></div>
    <div className="world-story-actions">{canOpen ? <Button onClick={() => onOpen(story)}>{story.incident_id ? text('查看事件', 'Explore incident') : text('查看对象', 'Explore object')}<ArrowRight size={16} /></Button> : story.external_ref ? <Button asChild><a href={story.external_ref} target="_blank" rel="noreferrer">{text('阅读原文', 'Read source')}<ArrowUpRight size={16} /></a></Button> : null}{canOpen && <Button variant="ghost" size="sm" onClick={() => onInvestigate(story)}>{story.incident_id && !story.object_id ? text('检索证据', 'Search evidence') : text('继续调查', 'Investigate')}<ArrowRight size={14} /></Button>}</div>
    <button className="world-detail-toggle" aria-expanded={expanded === story.story_id} onClick={() => setExpanded(expanded === story.story_id ? null : story.story_id)}>{text('材料与证据详情', 'Material & evidence details')}<ChevronDown size={14} /></button>
    {expanded === story.story_id && <div className="world-story-details">{story.kind === 'IncidentCandidate' && <p>{text('这个信号仍在关联与核验，尚未形成正式事件。', 'This signal is being correlated and verified; it is not a durable incident.')}</p>}{story.kind === 'HotVulnerability' && <p>{text('热区记录是当前缓存，不代表已写入持久知识。', 'A Hot record is current cache state, not a durable knowledge commit.')}</p>}{story.excerpt && <blockquote>{story.excerpt}</blockquote>}{canOpen && story.external_ref && <a href={story.external_ref} target="_blank" rel="noreferrer">{text('阅读完整原文', 'Read full source')}<ArrowUpRight size={14} /></a>}<details><summary>{text('技术坐标', 'Technical coordinates')}</summary><pre>{JSON.stringify({ evidence: story.evidence, facts: story.facts, observed_at: story.observed_at, happened_at: story.happened_at }, null, 2)}</pre></details></div>}
  </article>
}
