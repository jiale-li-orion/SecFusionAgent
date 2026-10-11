import { useQuery } from '@tanstack/react-query'
import { X, ArrowRight } from '../ui/icons'
import { Link } from 'react-router-dom'
import { getWorldOverview, type WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { Item, ItemContent, ItemTitle, ItemDescription, ItemActions } from '../ui/item'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../ui/accordion'
import { Skeleton } from '../ui/skeleton'

export function WorldSourceInspector({ category, label, path, materials, onClose, onFocus, embedded = false }: { embedded?: boolean; category: string; label: string; path: string; materials: WorldStory[]; onClose: () => void; onFocus: (story: WorldStory) => void }) {
  const { text, language } = useI18n()
  const query = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 30_000 })
  const sources = query.data?.sources.filter(s => s.measurement_category === category) ?? []
  const healthy = sources.filter(s => s.health === 'healthy').length
  const recent = materials.filter(s => s.category === category).slice(0, 3)
  const time = (value: string) => new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  const health = (value: string) => value === 'healthy' ? text('健康', 'Healthy') : value === 'degraded' ? text('降级', 'Degraded') : value === 'blocked' ? text('阻塞', 'Blocked') : value
  return <aside className="world-source-inspector text-foreground" aria-label={text('来源详情', 'Source details')}>
    {!embedded && <div className="mb-5 flex items-center justify-between"><h2 className="text-xl font-semibold">{label}</h2><Button variant="ghost" size="icon" onClick={onClose} aria-label={text('关闭来源详情', 'Close source details')}><X size={18}/></Button></div>}
    {query.data && sources.length > 0 && <p className="mb-3 text-sm text-muted-foreground">{text(`${sources.length} 个来源 · ${healthy} 个健康`, `${sources.length} sources · ${healthy} healthy`)}</p>}
    {query.isPending && <Skeleton className="my-4 h-20"/>}
    {query.isError && <p role="alert" className="text-sm">{text('来源状态暂不可用', 'Source status unavailable')}<Button variant="ghost" size="sm" onClick={() => void query.refetch()}>{text('重试', 'Retry')}</Button></p>}
    <div className="divide-y divide-border">{sources.slice(0, 3).map(s => <Item key={s.source_id} className="rounded-none border-0 px-0 py-3"><ItemContent className="min-w-0"><ItemTitle>{s.source_name ?? s.source_id}</ItemTitle><ItemDescription className="mt-1 text-xs">{s.last_success_at ? text('最近采集 ', 'Last collected ') + time(s.last_success_at) : text('暂无成功采集', 'No successful collection')}</ItemDescription></ItemContent><ItemActions><span className="text-xs text-muted-foreground">{health(s.health)}</span></ItemActions></Item>)}</div>
    {query.data && !sources.length && <div className="space-y-3 py-4 text-sm text-muted-foreground"><p>{category === 'assets' ? text('资产按需查询，在问答中输入 IP 或域名即可开始。', 'Assets are queried on demand. Start with an IP or domain in Ask.') : text('此方向尚未配置来源。', 'No sources are configured in this domain.')}</p>{category === 'assets' && <Button variant="secondary" size="sm" asChild><Link to="/start">{text('查询资产', 'Query an asset')}<ArrowRight size={14}/></Link></Button>}</div>}
    {recent.length > 0 && <section className="mt-5 border-t border-border pt-5"><h3 className="mb-2 text-xs font-medium text-muted-foreground">{text('已收录材料', 'Retained material')}</h3>{recent.map(story => <Item asChild key={story.story_id} className="w-full rounded-none border-0 px-0 py-3"><button className="text-left" onClick={() => onFocus(story)}><ItemContent className="min-w-0"><ItemTitle className="line-clamp-2 text-sm font-normal leading-relaxed">{story.headline}</ItemTitle></ItemContent><ItemActions><ArrowRight size={15}/></ItemActions></button></Item>)}</section>}
    <Accordion type="single" collapsible className="mt-4"><AccordionItem value="source-details" className="border-0"><AccordionTrigger className="text-xs font-normal text-muted-foreground">{text('全部来源与采集详情', 'All sources & collection details')}</AccordionTrigger><AccordionContent><p className="mb-3 text-xs text-muted-foreground">{path}</p>{sources.map(s => <div className="space-y-1 border-t border-border py-3 text-xs" key={s.source_id}><strong className="text-sm font-medium">{s.source_name ?? s.source_id}</strong><p>{s.last_success_at ? text('最近成功：', 'Last success: ') + time(s.last_success_at) : text('尚无成功采集记录', 'No successful collection recorded')}</p>{s.next_due_at && <p>{text('下次计划：', 'Next due: ')}{time(s.next_due_at)}</p>}{s.latest_error_code && <p>{text('最近错误：', 'Latest error: ')}{s.latest_error_code}</p>}</div>)}<Button variant="ghost" size="sm" asChild><Link to="/observatory">{text('进入运行观测', 'Open operations')}<ArrowRight size={14}/></Link></Button></AccordionContent></AccordionItem></Accordion>
  </aside>
}
