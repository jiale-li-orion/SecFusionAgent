import { useQuery } from '@tanstack/react-query'
import { X, ArrowRight, ArrowUpRight, Radio } from 'lucide-react'
import { getWorldOverview, type WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'

export function WorldSourceInspector({ category, label, path, materials, onClose, onFocus }: { category: string; label: string; path: string; materials: WorldStory[]; onClose: () => void; onFocus: (story: WorldStory) => void }) {
  const { text, language } = useI18n()
  const query = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 30_000 })
  const sources = query.data?.sources.filter(s => s.measurement_category === category) ?? []
  const healthy = sources.filter(s => s.health === 'healthy').length
  const recent = materials.filter(s => s.category === category).slice(0, 3)
  const time = (value: string) => new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  return <aside className="world-source-inspector" aria-label={text('来源详情', 'Source details')}>
    <div className="world-inspector-heading"><span className="world-panel-kicker"><Radio size={14} />{text('来源焦点', 'SOURCE IN FOCUS')}</span><button onClick={onClose} aria-label={text('关闭来源详情', 'Close source details')}><X size={17} /></button></div>
    <h2>{label}<span>{query.data ? text(`${sources.length} 个来源`, `${sources.length} ${sources.length === 1 ? 'source' : 'sources'}`) : '—'}</span></h2>
    {query.data && <p className="world-source-summary">{text(`${healthy} 个健康来源`, `${healthy} healthy sources`)}<span> / {sources.length}</span></p>}
    {query.isPending && <p role="status">{text('正在读取来源状态', 'Reading source status')}</p>}
    {query.isError && <p role="alert">{text('来源状态暂不可用', 'Source status unavailable')} <button className="world-text-action" onClick={() => void query.refetch()}>{text('重试', 'Retry')}</button></p>}
    <div className="world-source-readings">{sources.slice(0, 5).map(s => <div className="world-source-reading" key={s.source_id}><span className={`world-source-health is-${s.health}`} /><div><strong>{s.source_name ?? s.source_id}</strong><small>{s.last_success_at ? text('最近采集 ', 'Last collected ') + time(s.last_success_at) : text('暂无成功采集', 'No successful collection')}</small></div><span>{s.health === 'healthy' ? text('健康', 'Healthy') : s.health === 'degraded' ? text('降级', 'Degraded') : s.health === 'blocked' ? text('阻塞', 'Blocked') : s.health}</span></div>)}</div>
    {query.data && !sources.length && <p>{text('此方向尚未配置来源。', 'No sources are configured in this domain.')}</p>}
    {recent.length > 0 && <div className="world-source-materials"><h3>{text('这个方向的动态', 'Signals from this domain')}</h3>{recent.map(story => <button key={story.story_id} onClick={() => onFocus(story)}><strong>{story.headline}</strong><ArrowRight size={14} /></button>)}</div>}
    <details className="world-source-technical"><summary>{text('全部来源与采集详情', 'All sources & collection details')}</summary><p>{path}</p>{sources.map(s => <div key={s.source_id}><strong>{s.source_name ?? s.source_id}</strong><p>{s.last_success_at ? text('最近成功：', 'Last success: ') + time(s.last_success_at) : text('尚无成功采集记录', 'No successful collection recorded')}</p>{s.next_due_at && <p>{text('下次计划：', 'Next due: ')}{time(s.next_due_at)}</p>}{s.latest_error_code && <p>{text('最近错误：', 'Latest error: ')}{s.latest_error_code}</p>}</div>)}<a href={`${import.meta.env.BASE_URL}observatory`}>{text('进入运行观测', 'Open operations')}<ArrowUpRight size={14} /></a></details>
  </aside>
}
