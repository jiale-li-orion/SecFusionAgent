import { useQuery } from '@tanstack/react-query'
import { X, ArrowUpRight } from 'lucide-react'
import { getWorldOverview, type WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'

export function WorldSourceInspector({ category, label, path, materials, onClose }: { category: string; label: string; path: string; materials: WorldStory[]; onClose: () => void }) {
  const { text, language } = useI18n()
  const query = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 30_000 })
  const sources = query.data?.sources.filter(s => s.measurement_category === category) ?? []
  return <aside className="ew-inspector" aria-label={text('来源追溯', 'Source inspection')}>
    <div className="ew-inspector-head"><span>{text('来源方向', 'Source direction')}</span><button onClick={onClose} aria-label={text('关闭来源追溯', 'Close source inspection')}><X size={18} /></button></div>
    <h3>{label}</h3><p>{path}</p>
    {query.isPending && <p role="status">{text('正在读取来源的最近观察。', 'Reading the latest source observations.')}</p>}
    {query.isError && <button onClick={() => void query.refetch()}>{text('重新读取来源', 'Retry source read')}</button>}
    <div className="ew-source-readings">{sources.map(s => <p key={s.source_id}><strong>{s.source_name ?? s.source_id}</strong><span>{s.last_success_at ? text('最近采集于 ', 'Last collected ') + new Date(s.last_success_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US') : text('尚无成功采集记录', 'No successful collection recorded')}</span><small>{s.latest_error_code ?? s.latest_scheduled_status ?? s.health}</small></p>)}</div>
    {!sources.length && materials.filter(s => s.category === category && s.evidence).slice(0, 3).map(s => <p key={s.story_id}><strong>{s.source_name ?? s.source_id}</strong><span>{text('已留存观察：', 'Retained observation: ')} {s.headline}</span><small>{new Date(s.observed_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}</small></p>)}
    <a href={`${import.meta.env.BASE_URL}observatory`}>{text('进入运行观测', 'Open operations')}<ArrowUpRight size={15} /></a>
  </aside>
}
