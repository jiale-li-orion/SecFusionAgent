import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight } from '../ui/icons'
import { getHotWorld, type HotBug } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { Item, ItemContent, ItemTitle, ItemDescription, ItemActions } from '../ui/item'
import { Skeleton } from '../ui/skeleton'
import { SourceIdentity } from '../ui/source-identity'

export function HotIntelligenceFeed({ onOpen }: { onOpen: (item: HotBug) => void }) {
  const { text } = useI18n()
  const [page, setPage] = useState(0)
  const query = useQuery({ queryKey: ['intelligence-hot-feed', page], queryFn: () => getHotWorld(20, page * 20), staleTime: 30_000 })
  const total = query.data?.resident_total
  const pages = total === undefined ? 1 : Math.max(1, Math.min(Math.ceil(total / 20), 205))
  return <section aria-label={text('热点情报', 'Hot intelligence')}>
    <p className="py-4 text-sm text-muted-foreground">{text('正在被关注的漏洞，按热区活跃度排列。', 'Vulnerabilities ranked by activity in the working set.')}</p>
    {query.isPending && <div className="space-y-5" role="status" aria-label={text('读取热点', 'Loading hot records')}>{[0,1,2].map(i => <Skeleton key={i} className="h-24"/>)}</div>}
    {query.isError && <div role="alert"><p>{text('热点暂时不可用。', 'Hot records are unavailable.')}</p><Button variant="outline" onClick={() => void query.refetch()}>{text('重试', 'Retry')}</Button></div>}
    {query.data?.items.map(item => <Item key={`${item.source_id}:${item.external_object_id}`} className="rounded-none border-0 border-b border-border px-0 py-5"><ItemContent className="min-w-0 gap-3"><ItemTitle className="max-w-full min-w-0 text-base"><button className="min-w-0 text-left [overflow-wrap:anywhere] hover:text-primary" onClick={() => onOpen(item)}>{item.cve_id ?? item.external_object_id}{item.title && item.title !== item.cve_id ? ` · ${item.title}` : ''}</button></ItemTitle><SourceIdentity source={item.source_name ?? item.source_id} url={item.canonical_url}/>{item.description && <ItemDescription>{item.description}</ItemDescription>}</ItemContent><ItemActions><Button variant="ghost" size="icon" onClick={() => onOpen(item)} aria-label={text(`查看 ${item.cve_id ?? item.external_object_id}`, `View ${item.cve_id ?? item.external_object_id}`)}><ArrowRight/></Button></ItemActions></Item>)}
    {query.data && !query.data.items.length && <p className="py-8 text-sm text-muted-foreground">{text('当前没有热区记录。', 'No records in the working set.')}</p>}
    <div className="flex items-center justify-between gap-3 py-5 text-sm text-muted-foreground"><span>{total === undefined ? '—' : text(`${total.toLocaleString()} 条热区记录`, `${total.toLocaleString()} Hot records`)}</span><div className="flex items-center gap-3"><Button variant="outline" size="icon" disabled={!page || query.isFetching} onClick={() => setPage(p => p - 1)} aria-label={text('上一页', 'Previous page')}><ArrowLeft/></Button><span>{page + 1} / {pages}</span><Button variant="outline" size="icon" disabled={page + 1 >= pages || query.isFetching || !query.data} onClick={() => setPage(p => p + 1)} aria-label={text('下一页', 'Next page')}><ArrowRight/></Button></div></div>
    {total !== undefined && total > 4100 && <p className="text-xs text-muted-foreground">{text('列表展示排名前 4100 条；通过搜索可按完整 CVE 编号查询。', 'This list covers the top 4,100 records; search by full CVE ID for an exact lookup.')}</p>}
  </section>
}
