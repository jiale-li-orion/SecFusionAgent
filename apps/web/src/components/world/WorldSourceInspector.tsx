import { useQuery } from '@tanstack/react-query'
import { X, ArrowUpRight } from 'lucide-react'
import { getWorldOverview, type WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { SourceSeal } from '../instrument/SourceSeal'

export function WorldSourceInspector({ category, label, path, materials, onClose }: { category: string; label: string; path: string; materials: WorldStory[]; onClose: () => void }) {
  const { text, language } = useI18n()
  const query = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 30_000 })
  const sources = query.data?.sources.filter(s => s.measurement_category === category) ?? []
  const healthy = sources.filter(s => s.health === 'healthy').length
  const degraded = sources.filter(s => s.health === 'degraded').length
  const blocked = sources.filter(s => s.health === 'blocked').length
  const time = (value: string) => new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')
  return <aside className="ew-inspector" aria-label={text('来源追溯', 'Source inspection')}>
    <div className="ew-inspector-head"><span>{text('来源方向', 'Source direction')}</span><button onClick={onClose} aria-label={text('关闭来源追溯', 'Close source inspection')}><X size={18} /></button></div>
    <h3>{label}</h3><p>{path}</p>
    {query.isPending && <p role="status">{text('正在读取来源的最近观察。', 'Reading the latest source observations.')}</p>}
    {query.isError && <button onClick={() => void query.refetch()}>{text('重新读取来源', 'Retry source read')}</button>}
    {query.data && <div className="ew-source-health-summary"><strong>{text(`${sources.length} 个实际来源`, `${sources.length} configured sources`)}</strong><span>{text(`${healthy} 健康 · ${degraded} 降级 · ${blocked} 阻塞`, `${healthy} healthy · ${degraded} degraded · ${blocked} blocked`)}</span></div>}
    <div className="ew-source-readings">{sources.map(s => <div className="ew-source-reading" key={s.source_id}>
      <SourceSeal category={category} name={s.source_name ?? s.source_id}/>
      <div><strong>{s.source_name ?? s.source_id}</strong>
        <span>{s.last_success_at ? text('最近成功：', 'Last success: ') + time(s.last_success_at) : text('尚无成功采集记录', 'No successful collection recorded')}</span>
        {s.next_due_at && <span>{text('下次计划：', 'Next due: ')}{time(s.next_due_at)}</span>}
        {s.latest_error_code && <em>{text('最近错误：', 'Latest error: ')}{s.latest_error_code}</em>}
      </div>
      <small className={`source-health-${s.health}`}>{s.health === 'healthy' ? text('健康', 'Healthy') : s.health === 'degraded' ? text('降级', 'Degraded') : s.health === 'blocked' ? text('阻塞', 'Blocked') : s.health}</small>
    </div>)}</div>
    {!sources.length && materials.filter(s => s.category === category && s.evidence).slice(0, 3).map(s => <p key={s.story_id}><strong>{s.source_name ?? s.source_id}</strong><span>{text('已留存观察：', 'Retained observation: ')} {s.headline}</span><small>{new Date(s.observed_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}</small></p>)}
    <a href={`${import.meta.env.BASE_URL}observatory`}>{text('进入运行观测', 'Open operations')}<ArrowUpRight size={15} /></a>
  </aside>
}
