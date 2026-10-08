import { BrandMark, ProductGlyph } from '../instrument/ProductGlyph'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, ArrowUpRight, Check, Link2, Search } from 'lucide-react'
import type { WorldFormation, WorldStory } from '../../lib/api/world'
import { searchHotWorldCve } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { projectHot } from '../../lib/worldHotPresentation'

export function WorldHotField({ stories, focusedId, total, failed, onFocus, onRetry }: { stories: WorldStory[]; focusedId: string | undefined; total: number | undefined; failed: boolean; onFocus: (s: WorldStory) => void; onRetry: () => void }) {
  const { text } = useI18n()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(0)
  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250); return () => window.clearTimeout(timer) }, [search])
  const fullCve = /^CVE-\d{4}-\d{4,}$/i.test(debouncedSearch) ? debouncedSearch.toUpperCase() : null
  const exactSearch = fullCve !== null && search.trim().toUpperCase() === fullCve
  const remote = useQuery({ queryKey: ['world-hot-cve', fullCve], queryFn: () => searchHotWorldCve(fullCve!), enabled: Boolean(fullCve), retry: false })
  const localItems = stories.filter(s => s.kind === 'HotVulnerability' && `${s.headline} ${s.excerpt}`.toLowerCase().includes(search.toLowerCase()))
  const items = exactSearch ? (remote.data?.items ?? []).map(projectHot) : localItems
  const pages = Math.max(1, Math.ceil(items.length / 8))
  const current = Math.min(page, pages - 1)
  const visible = items.slice(current * 8, current * 8 + 8)
  return <div className="ew-hot-field">
    <p className="ew-field-intro">{total === undefined ? text('正在读取热区', 'Reading the working set') : text(`热区驻留 ${total.toLocaleString()} 条漏洞记录`, `${total.toLocaleString()} vulnerability records resident`)}</p>
    <label className="ew-hot-search"><Search size={15} /><input aria-label={text('搜索热区漏洞', 'Search Hot vulnerabilities')} placeholder={text('完整 CVE 查整个热区；其他词筛选当前窗口', 'Full CVE searches all Hot; other terms filter this window')} value={search} onChange={e => { setSearch(e.target.value); setPage(0) }} /></label>
    {exactSearch && remote.isFetching && <p className="ew-field-note" role="status">{text('正在整个热区查找该 CVE…', 'Searching the full working set for this CVE…')}</p>}
    {exactSearch && remote.isError && <p className="ew-field-note" role="alert">{text('热区检索失败。', 'Hot search failed.')} <button onClick={() => void remote.refetch()}>{text('重试', 'Retry')}</button></p>}
    {exactSearch ? <div className="ew-hot-results">
      <div className="ew-hot-results-head"><small>{text('全驻留池 · 精确匹配', 'FULL RESIDENT POOL · EXACT MATCH')}</small><strong>{fullCve}</strong><span>{items.length} {text('条来源记录', 'source records')}</span></div>
      {items.map(s => <button key={s.story_id} className={s.story_id === focusedId ? 'selected' : ''} onClick={() => onFocus(s)}><ProductGlyph kind="vulnerability" size={25} /><span><small>{s.source_name}</small><strong>{s.headline}</strong><em>{s.excerpt || text('打开这条来源记录', 'Open this source record')}</em></span><ArrowUpRight size={15} /></button>)}
    </div> : <div className="ew-hot-orbit">
      <svg viewBox="0 0 500 500" aria-hidden="true"><ellipse cx="250" cy="250" rx="205" ry="178" /><ellipse cx="250" cy="250" rx="150" ry="205" transform="rotate(30 250 250)" /><circle cx="250" cy="250" r="72" /></svg>
      <div className="ew-hot-core"><ProductGlyph kind="vulnerability" size={40} /><strong>{text('热区', 'Hot')}</strong><small>{text('点击漏洞查看原文', 'Select a vulnerability')}</small></div>
      {visible.map((s, i) => { const a = (i * 45 - 90) * Math.PI / 180; return <button key={s.story_id} className={`ew-hot-node ${s.story_id === focusedId ? 'selected' : ''}`} style={{ left: `${50 + Math.cos(a) * 37}%`, top: `${50 + Math.sin(a) * 38}%` }} onClick={() => onFocus(s)} aria-label={text(`查看漏洞：${s.headline}`, `Read vulnerability: ${s.headline}`)}><i /><strong>{s.headline}</strong><span>{s.facts.pinned ? text('已固定缓存', 'Cache pinned') : s.facts.active ? text('工作流使用中', 'In workflow') : text('近期更新', 'Recently updated')}</span></button> })}
    </div>}
    {!exactSearch && <div className="ew-field-pagination"><button disabled={current === 0} onClick={() => setPage(current - 1)} aria-label={text('上一组漏洞', 'Previous vulnerabilities')}><ArrowLeft size={16} /></button><span>{current + 1} / {pages}</span><button disabled={current >= pages - 1} onClick={() => setPage(current + 1)} aria-label={text('下一组漏洞', 'Next vulnerabilities')}><ArrowRight size={16} /></button></div>}
    <p className="ew-field-note">{exactSearch ? text('已按完整 CVE 编号查询整个驻留热区；结果仍是 Hot 缓存，不代表已写入持久知识。', 'Exact CVE lookup covers the resident Hot pool; results remain cache entries, not durable Knowledge.') : text(`本次载入排名靠前的 ${stories.filter(s => s.kind === 'HotVulnerability').length} 条；输入完整 CVE 编号可查整个热区。`, `Loaded ${stories.filter(s => s.kind === 'HotVulnerability').length} ranked records; enter a full CVE ID to search the entire Hot pool.`)}</p>
    {((failed && !exactSearch) || (!items.length && !remote.isFetching && !remote.isError)) && <p role="status">{failed && !exactSearch ? <>{text('热区读取失败', 'Working set read failed')} <button onClick={onRetry}>{text('重新读取', 'Retry')}</button></> : exactSearch ? text('整个热区没有该 CVE 的驻留记录', 'This CVE is not resident in the Hot pool') : text('本次载入窗口没有匹配记录', 'No loaded records match')}</p>}
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
export function WorldFormationField({ formation }: { formation: WorldFormation | undefined }) {
  const { text, language } = useI18n()
  const [selected, setSelected] = useState<string | null>(null)
  const running = formation?.processing.filter(p => ['running', 'started'].includes(p.status)) ?? []
  const items = formation?.processing.slice(0, 5) ?? []
  const current = formation?.processing.find(p => p.run_id === selected)
  return <div className="ew-formation-field">
    <p className="ew-field-intro">{!formation ? text('正在读取富化记录', 'Reading processing records') : running.length ? text(`${running.length} 个富化处理正在运行`, `${running.length} enrichment processors running`) : text('当前没有运行中的富化处理', 'No enrichment processing is running now')}</p>
    <div className="ew-formation-axis"><span>{text('来源材料', 'Source material')}</span><ArrowRight size={16} /><span>{text('提取 · 关联', 'Extract · link')}</span><ArrowRight size={16} /><span>{text('知识留存', 'Retained knowledge')}</span></div>
    <div className="ew-processing-field">{items.map(p => { const alias = processors[p.processor_name]; return <button key={p.run_id} className={selected === p.run_id ? 'selected' : ''} onClick={() => setSelected(selected === p.run_id ? null : p.run_id)}><span className="ew-processing-glyph">{p.committed_at ? <Check size={18} /> : <Link2 size={18} />}</span><span><strong>{alias ? text(...alias) : text('情报富化', 'Intelligence enrichment')}</strong><small>{p.source_name ?? text('处理记录', 'Processing record')} · {new Date(p.started_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</small></span><em>{p.committed_at ? text('已写入知识', 'Knowledge committed') : p.status === 'success' ? text('处理完成', 'Processed') : ['running', 'started'].includes(p.status) ? text('运行中', 'Running') : text('处理未成功', 'Unsuccessful')}</em></button> })}</div>
    {current && <div className="ew-processing-detail"><p>{current.external_object_id ?? current.processor_name}</p><p>{current.committed_at ? text('本次处理有对应的知识提交。', 'This processing run has a linked knowledge commit.') : text('这条处理记录尚无对应的知识提交。', 'No knowledge commit is linked to this processing record.')}</p><details><summary>{text('技术坐标', 'Technical coordinates')}</summary><pre>{JSON.stringify(current, null, 2)}</pre></details></div>}
    <p className="ew-field-note">{text('显示最近的实际处理记录。点击查看该次处理的知识提交与坐标。', 'Recent actual processing records. Select one to inspect its linked commit and coordinates.')}</p>
  </div>
}

export function WorldSourcesField({ sources, directions, stories, onSource }: { sources: import('../../lib/api/world').WorldOverview['sources'] | undefined; directions: Array<{ key: string; zh: string; en: string; icon: import('lucide-react').LucideIcon; path: string }>; stories: WorldStory[]; onSource: (category: string) => void }) {
  const { text } = useI18n()
  return <div className="ew-source-field">
    <p className="ew-field-intro">{text('系统正在观察的八个方向', 'Eight directions the system observes')}</p>
    <div className="ew-hot-orbit ew-source-orbit"><svg viewBox="0 0 500 500" aria-hidden="true"><ellipse cx="250" cy="250" rx="205" ry="178" /><ellipse cx="250" cy="250" rx="150" ry="205" transform="rotate(30 250 250)" /><circle cx="250" cy="250" r="72" />{directions.map((d, i) => { const a = (i * 45 - 90) * Math.PI / 180; return <path key={d.key} d={`M${250 + Math.cos(a) * 75} ${250 + Math.sin(a) * 75}L${250 + Math.cos(a) * 170} ${250 + Math.sin(a) * 170}`} /> })}</svg>
      <div className="ew-hot-core"><BrandMark size={42} /><strong>{text('流入', 'Ingress')}</strong><small>{text('来源与留存路径', 'Sources and retention paths')}</small></div>
      {directions.map((d, i) => { const a = (i * 45 - 90) * Math.PI / 180; const group = sources?.filter(s => s.measurement_category === d.key) ?? []; const material = stories.find(s => s.category === d.key); return <button className="ew-source-node" key={d.key} onClick={() => onSource(d.key)} style={{ left: `${50 + Math.cos(a) * 38}%`, top: `${50 + Math.sin(a) * 38}%` }}><ProductGlyph kind={d.key} size={34} /><strong>{text(d.zh, d.en)}</strong><span>{group[0]?.source_name?.split(' · ')[0] ?? material?.source_name ?? text('按需来源', 'On-demand sources')}</span><small>{d.path}</small></button> })}
    </div>
    <p className="ew-field-note">{text('点击一个方向查看实际来源、最近采集时间与处理路径。连线表示来源路径，采集与写入以测量和处理记录为准。', 'Select a direction for actual sources, collection times and processing paths. Lines show source routes; processing records establish activity.')}</p>
  </div>
}
