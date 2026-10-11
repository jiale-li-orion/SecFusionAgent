import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Search } from 'lucide-react'
import type { WorldFormation, WorldStory } from '../../lib/api/world'
import { searchHotWorldCve } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { Link } from 'react-router-dom'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '../ui/accordion'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Item, ItemContent, ItemTitle, ItemDescription, ItemActions } from '../ui/item'
import { Badge } from '../ui/badge'
import { Skeleton } from '../ui/skeleton'
import { projectHot } from '../../lib/worldHotPresentation'

export function WorldHotField({ stories, focusedId, total, failed, pending, page, pageSize, onPage, onFocus, onRetry }: { stories: WorldStory[]; focusedId: string | undefined; total: number | undefined; failed: boolean; pending: boolean; page: number; pageSize: number; onPage: (page: number) => void; onFocus: (s: WorldStory) => void; onRetry: () => void }) {
  const { text } = useI18n()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const resultsRef = useRef<HTMLDivElement>(null)
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250); return () => window.clearTimeout(timer) }, [search])
  const fullCve = /^CVE-\d{4}-\d{4,}$/i.test(debouncedSearch) ? debouncedSearch.toUpperCase() : null
  const exactSearch = fullCve !== null && search.trim().toUpperCase() === fullCve
  const remote = useQuery({ queryKey: ['world-hot-cve', fullCve], queryFn: () => searchHotWorldCve(fullCve!), enabled: Boolean(fullCve), retry: false })
  const localItems = stories.filter(s => `${s.facts.cve_id ?? ''} ${s.headline} ${s.excerpt} ${s.source_name}`.toLowerCase().includes(search.toLowerCase()))
  const items = exactSearch ? (remote.data?.items ?? []).map(projectHot) : localItems
  const pages = Math.max(1, Math.ceil((total ?? 0) / pageSize))
  const browsablePages = Math.min(pages, Math.floor(4096 / pageSize) + 1)
  const rankingBounded = pages > browsablePages
  useEffect(() => { if (resultsRef.current) resultsRef.current.scrollTop = 0 }, [page, exactSearch, fullCve])
  return <div className="world-hot-field">
    <p className="world-field-intro">{total === undefined ? text('正在读取热区', 'Reading the working set') : text(`热区驻留 ${total.toLocaleString()} 条漏洞记录`, `${total.toLocaleString()} vulnerability records resident`)}</p>
    <label className="relative block"><Search className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground"/><Input className="pl-9" aria-label={text('搜索热区漏洞', 'Search Hot vulnerabilities')} placeholder={text('完整 CVE 查全部；关键词筛选本页', 'Full CVE searches all; keywords filter this page')} value={search} onChange={e => setSearch(e.target.value)}/></label>
    {exactSearch && remote.isFetching && <p className="world-field-note" role="status">{text('正在整个热区查找该 CVE…', 'Searching the full working set for this CVE…')}</p>}
    {exactSearch && remote.isError && <p className="world-field-note" role="alert">{text('热区检索失败。', 'Hot search failed.')} <button onClick={() => void remote.refetch()}>{text('重试', 'Retry')}</button></p>}
    <div className="world-hot-results" ref={resultsRef}>
      <div className="world-hot-results-head"><small>{exactSearch ? text('全驻留池 · 精确匹配', 'FULL RESIDENT POOL · EXACT MATCH') : text('热区索引 · 按活跃度排序', 'HOT INDEX · ACTIVITY RANKED')}</small><strong>{exactSearch ? fullCve : text(`第 ${page + 1} 页`, `Page ${page + 1}`)}</strong><span>{exactSearch ? `${items.length} ${text('条来源记录', 'source records')}` : `${Math.min(page * pageSize + 1, total ?? 0)}–${Math.min((page + 1) * pageSize, total ?? 0)} / ${total ?? '—'}`}</span></div>
      <div className="divide-y divide-border">{items.map(s => <Item asChild key={s.story_id} className="w-full rounded-none border-0 px-2 py-4 data-[selected=true]:bg-accent"><button data-selected={s.story_id === focusedId} aria-pressed={s.story_id === focusedId} className="text-left" onClick={() => onFocus(s)}><ItemContent className="min-w-0 gap-2"><ItemTitle className="[overflow-wrap:anywhere]">{typeof s.facts.cve_id === 'string' ? s.facts.cve_id : s.headline}</ItemTitle>{(s.excerpt || s.headline !== s.facts.cve_id) && <ItemDescription className="text-xs leading-relaxed">{s.excerpt || s.headline}</ItemDescription>}<span className="text-xs text-muted-foreground">{s.source_name}</span></ItemContent><ItemActions><ArrowRight size={16}/></ItemActions></button></Item>)}</div>
    </div>
    {!exactSearch && <div className="world-field-pagination"><Button variant="outline" size="icon" disabled={page === 0 || pending} onClick={() => onPage(page - 1)} aria-label={text('上一页漏洞', 'Previous vulnerability page')}><ArrowLeft size={16} /></Button><span>{page + 1} / {browsablePages}{rankingBounded && ` · ${text('排行窗口', 'ranked window')}`}</span><Button variant="outline" size="icon" disabled={page >= browsablePages - 1 || pending} onClick={() => onPage(page + 1)} aria-label={text('下一页漏洞', 'Next vulnerability page')}><ArrowRight size={16} /></Button></div>}
    <p className="world-field-note">{exactSearch ? text('完整 CVE 查询覆盖整个驻留热区；结果仍是缓存记录。', 'Full CVE lookup covers the resident Hot pool; results remain cache records.') : text('逐页浏览当前排行；普通关键词只筛选本页。Hot 记录不等于已写入的持久知识。', 'Browse the current ranking; ordinary words filter this page. Hot records are not durable Knowledge.')}{!exactSearch && rankingBounded && ` ${text(`排行最多翻到第 ${browsablePages} 页；完整 CVE 编号仍可查询整个驻留池。`, `Ranking browsing ends at page ${browsablePages}; exact CVE lookup still covers the full resident pool.`)}`}</p>
    {failed && !exactSearch && <p role="alert">{text('热区读取失败', 'Working set read failed')} <button onClick={onRetry}>{text('重新读取', 'Retry')}</button></p>}
    {pending && !exactSearch && <p role="status">{text('读取本页漏洞…', 'Loading this page…')}</p>}
    {!items.length && (exactSearch ? !remote.isFetching && !remote.isError : !failed && !pending) && <p role="status">{exactSearch ? text('整个热区没有该 CVE 的驻留记录', 'This CVE is not resident in the Hot pool') : text('本页没有匹配记录', 'No records match on this page')}</p>}
  </div>
}

const processors: Record<string, [string, string]> = {
  'managed-document-semantic': ['材料语义关联', 'Document semantic linking'],
  'github-structured-normalizer': ['代码变更索引', 'Development indexing'],
  'normative-semantic': ['标准条款关联', 'Normative linking'],
  'github-reference-graph': ['代码引用关联', 'Repository references'],
  'research-exact-cve-bridge': ['研究与漏洞关联', 'Research / vulnerability linking'],
  'shodan-internetdb-asset-enrichment': ['公网资产关联', 'Internet asset linking'],
  'github-advisory-enrichment': ['安全公告关联', 'Security advisory linking'],
  'first-epss-enrichment': ['利用概率补充', 'Exploit probability'],
  'cisa-kev-enrichment': ['已知利用补充', 'Known exploitation'],
  'osv-enrichment': ['受影响版本补充', 'Affected versions'],
  'redhat-csaf-vex-enrichment': ['适用性与修复补充', 'Applicability and remediation'],
}
export function WorldFormationField({ formation, failed, onRetry }: { formation: WorldFormation | undefined; failed: boolean; onRetry: () => void }) {
  const { text, language } = useI18n()
  if (failed) return <div className="p-6" role="alert"><p>{text('处理记录暂时不可用。', 'Processing history is unavailable.')}</p><Button variant="outline" className="mt-4" onClick={onRetry}>{text('重新读取', 'Retry')}</Button></div>
  if (!formation) return <div className="space-y-5 p-6" role="status" aria-label={text('读取记录中', 'Loading records')}>{[0,1,2].map(i => <Skeleton key={i} className="h-16 w-full"/>)}</div>
  return <div className="px-6 pb-6">
    {!formation.processing.length && <p className="py-8 text-sm text-muted-foreground">{text('暂无处理记录。新的材料完成处理后会出现在这里。', 'No processing records yet. Newly processed material will appear here.')}</p>}
    <Accordion type="single" collapsible>{formation.processing.map(p => {
      const alias = processors[p.processor_name]
      const objects = p.affected_objects ?? []
      const countsKnown = p.results_complete !== false && p.claim_count !== undefined && p.relation_count !== undefined && p.commit_count !== undefined && p.object_count !== undefined && p.affected_objects !== undefined
      const committed = p.commit_status === 'committed' || Boolean(p.committed_at)
      return <AccordionItem value={p.run_id} key={p.run_id}>
        <AccordionTrigger className="items-start py-5 hover:no-underline"><span className="grid min-w-0 gap-2 text-left"><span className="text-base font-semibold break-words">{objects[0]?.label ?? p.external_object_id ?? p.source_name ?? text('来源材料', 'Source material')}</span><span className="text-sm font-normal text-muted-foreground">{committed && !countsKnown ? text('已提交，结果明细待补全', 'Committed; result details pending') : committed ? text(`形成 ${p.claim_count ?? 0} 条事实、${p.relation_count ?? 0} 条关联`, `${p.claim_count ?? 0} facts and ${p.relation_count ?? 0} relationships retained`) : alias ? text(...alias) : text('材料处理', 'Material processing')}</span><span className="flex flex-wrap items-center gap-2 text-xs font-normal text-muted-foreground"><span>{new Date(p.started_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span><Badge variant="secondary">{committed ? text('已留存', 'Retained') : ['running', 'started'].includes(p.status) ? text('处理中', 'Processing') : p.status === 'success' ? text('无新增提交', 'No new commit') : text('处理未成功', 'Unsuccessful')}</Badge></span></span></AccordionTrigger>
        <AccordionContent className="space-y-4"><p className="text-muted-foreground">{p.source_name}{alias && ` · ${text(...alias)}`}</p>{objects.length > 0 && <div className="flex flex-wrap gap-2">{objects.map(object => <Button key={object.object_id} variant="outline" size="sm" asChild><Link to={`/intelligence?object=${encodeURIComponent(object.object_id)}`}>{object.label}<ArrowRight size={14}/></Link></Button>)}</div>}<p>{committed && !countsKnown ? text('存在对应知识提交，明细尚不完整。', 'A knowledge commit is linked; its details are not yet complete.') : committed ? text(`${p.commit_count ?? 1} 次知识提交，直接写入 ${p.object_count ?? 0} 个对象，影响 ${objects.length} 个对象。`, `${p.commit_count ?? 1} knowledge commits; ${p.object_count ?? 0} objects directly written, ${objects.length} objects affected.`) : text('这次处理尚未形成新的知识提交。', 'This run has not produced a new knowledge commit.')}</p>{p.results_complete === false && <p className="text-muted-foreground">{text('结果尚未完整收齐。', 'Results are not yet complete.')}</p>}<details><summary className="cursor-pointer text-muted-foreground">{text('查看处理坐标', 'Processing coordinates')}</summary><pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-xs">{JSON.stringify(p, null, 2)}</pre></details></AccordionContent>
      </AccordionItem>
    })}</Accordion>
  </div>
}
