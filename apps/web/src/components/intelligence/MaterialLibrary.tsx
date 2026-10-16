import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import type { WorldStory } from '../../lib/api/world'
import { getMaterialLibrary } from '../../lib/api/library'
import { clusterMaterialPage, LIBRARY_PAGE_SIZE } from '../../lib/materialLibraryPresentation'
import { materialLibraryDate } from '../../lib/libraryPresentation'
import { useI18n } from '../../lib/i18n'
import { DevelopingField } from '../ui/developing-field'
import { Button } from '../ui/button'
import { SourceIdentity } from '../ui/source-identity'
import { dateLabel } from './feedPresentation'
import './library-explorers.css'

export function MaterialLibrary({ onSelect }: { onSelect: (story: WorldStory) => void }) {
  const { text, language } = useI18n()
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''
  const source = params.get('librarySource') ?? ''
  const subject = params.get('subject') ?? ''
  const query = params.get('libraryQuery') ?? ''
  const rawOffset = Number(params.get('libraryOffset') ?? 0)
  const offset = Number.isInteger(rawOffset) && rawOffset >= 0 && rawOffset <= 1_000_000 ? rawOffset : 0
  const asOf = params.get('libraryAsOf') ?? undefined
  const [subjectPage, setSubjectPage] = useState(0)
  const [selectedTheme, setSelectedTheme] = useState('')
  const [selectedStory, setSelectedStory] = useState('')
  const library = useQuery({ queryKey: ['material-library', category, source, subject, query, offset, asOf], queryFn: ({ signal }) => getMaterialLibrary({ limit: LIBRARY_PAGE_SIZE, offset, asOf, category, source, subject, query }, signal), staleTime: 30_000 })
  const data = library.data
  const contentClusters = useMemo(() => clusterMaterialPage(data?.items ?? [], data?.subjects ?? []), [data])
  const independent = contentClusters.filter(item => item.items.length === 1).flatMap(item => item.items)
  const clusters = contentClusters.filter(item => item.items.length > 1)
  if (independent.length) clusters.push({ id: 'independent', zh: '独立资料', en: 'Independent material', items: independent, terms: [] })
  const cluster = clusters.find(item => item.id === selectedTheme) ?? clusters[0]
  const story = cluster?.items.find(item => item.story_id === selectedStory) ?? cluster?.items[0]
  const storyDate = story ? materialLibraryDate(story) : null
  const index = cluster?.items.findIndex(item => item.story_id === story?.story_id) ?? 0
  const subjectPages = Math.max(1, Math.ceil((data?.subjects.length ?? 0) / 6))
  const currentSubjectPage = Math.min(subjectPage, subjectPages - 1)
  const visibleSubjects = data?.subjects.slice(currentSubjectPage * 6, currentSubjectPage * 6 + 6) ?? []
  function resetSelection() { setSelectedTheme(''); setSelectedStory('') }
  function filter(key: string, value: string) {
    resetSelection()
    setParams(current => { const next = new URLSearchParams(current); next.delete('libraryOffset'); next.delete('libraryAsOf'); if (value) next.set(key, value); else next.delete(key); return next })
  }
  function clearFilters() { resetSelection(); setParams({ channel: 'library' }) }
  function page(offset: number) { resetSelection(); setParams(current => { const next = new URLSearchParams(current); next.set('libraryOffset', String(offset)); if (data?.as_of) next.set('libraryAsOf', data.as_of); return next }) }
  const pagination = data && data.total > LIBRARY_PAGE_SIZE && <nav className="library-corpus-pagination" aria-label={text('资料分页', 'Material pages')}><Button variant="ghost" disabled={!offset || library.isFetching} onClick={() => page(Math.max(0, offset - LIBRARY_PAGE_SIZE))}>{text('上一页资料', 'Previous materials')}</Button><span>{Math.floor(offset / LIBRARY_PAGE_SIZE) + 1} / {Math.ceil(data.total / LIBRARY_PAGE_SIZE)}</span><Button variant="ghost" disabled={data.next_offset === null || library.isFetching} onClick={() => page(data.next_offset!)}>{text('下一页资料', 'Next materials')}</Button></nav>
  return <section className="material-library" aria-label={text('资料主题图', 'Material themes')} data-develop-scope>
    <header className="library-intro"><div><span className="library-eyebrow">{text('资料库', 'Material library')}</span><h2>{text('沿主题，读懂安全研究', 'Explore the security corpus')}</h2></div>{data && <p className="library-corpus-total"><strong>{data.corpus_total.toLocaleString()}</strong>{text('份公开留存资料', 'public retained materials')}</p>}</header>
    <div className="library-catalog-controls">
      <label>{text('类型', 'Type')}<select aria-label={text('资料类型', 'Material type')} value={category} onChange={event => filter('category', event.target.value)}><option value="">{text('全部类型', 'All types')}</option>{data?.categories.map(item => <option key={item.key} value={item.key}>{text(item.label, item.label_en)} · {item.count}</option>)}</select></label>
      <label>{text('来源', 'Source')}<select aria-label={text('资料来源', 'Material source')} value={source} onChange={event => filter('librarySource', event.target.value)}><option value="">{text('全部来源', 'All sources')}</option>{data?.sources.map(item => <option key={item.key} value={item.key}>{item.label} · {item.count}</option>)}</select></label>
      <LibrarySearch key={query} query={query} onSearch={value => filter('libraryQuery', value)}/>
    </div>
    {library.isPending && <div className="library-empty library-loading" role="status">{text('正在读取资料库…', 'Loading the material library…')}</div>}
    {library.isError && <p role="alert" className="library-notice">{text('资料暂时无法读取。', 'Material could not be loaded.')}<Button variant="ghost" onClick={() => void library.refetch()}>{text('重试', 'Retry')}</Button></p>}
    {data && <>
      <div className="library-topic-heading"><span>{text('细分主题 · 全库数量', 'Subjects · corpus counts')}</span>{subject && <Button variant="ghost" onClick={() => filter('subject', '')}>{text('全部主题', 'All subjects')}</Button>}</div>
      <div className="material-atlas" aria-label={text('按细分主题筛选全库', 'Filter the corpus by subject')}>
        <DevelopingField variant="library" className="material-diffusion"/>
        {visibleSubjects.map((item, position) => <button className={`material-cluster cluster-position-${position}`} key={item.key} aria-pressed={subject === item.key} onClick={() => filter('subject', subject === item.key ? '' : item.key)}><span>{String(currentSubjectPage * 6 + position + 1).padStart(2, '0')}</span><strong>{text(item.label, item.label_en)}</strong><small>{text(`${item.count} 份资料`, `${item.count} materials`)}</small></button>)}
      </div>
      {subjectPages > 1 && <nav className="material-atlas-pager" aria-label={text('主题分页', 'Theme pages')}><Button variant="ghost" disabled={currentSubjectPage === 0} onClick={() => setSubjectPage(currentSubjectPage - 1)}>{text('上一组主题', 'Previous subjects')}</Button><span>{currentSubjectPage + 1} / {subjectPages}</span><Button variant="ghost" disabled={currentSubjectPage === subjectPages - 1} onClick={() => setSubjectPage(currentSubjectPage + 1)}>{text('更多细分主题', 'More subjects')}</Button></nav>}
      <div className="library-result-heading"><div><h3>{subject ? text(data.subjects.find(item => item.key === subject)?.label ?? subject, data.subjects.find(item => item.key === subject)?.label_en ?? subject) : text('全部资料', 'All materials')}</h3><p>{text(`共 ${data.total.toLocaleString()} 份 · 本页 ${data.items.length} 份`, `${data.total.toLocaleString()} matches · ${data.items.length} on this page`)}</p></div>{pagination}{(category || source || subject || query) && <Button variant="ghost" onClick={clearFilters}>{text('清除筛选', 'Clear filters')}</Button>}</div>
      {!data.items.length && <div className="library-empty"><p>{text('没有符合这些条件的资料。', 'No materials match these filters.')}</p></div>}
    </>}
    {cluster && story && <>
      <div className="library-page-clusters"><label htmlFor="library-page-cluster">{text('本页内容关联', 'Related material on this page')}</label><select id="library-page-cluster" value={cluster.id} onChange={event => { setSelectedTheme(event.target.value); setSelectedStory('') }}>{clusters.map((item, position) => <option value={item.id} key={item.id}>{position + 1}. {text(item.zh, item.en)} · {item.items.length}</option>)}</select></div>
      <section className="material-reading" aria-label={text(cluster.zh, cluster.en)}>
        <aside className="material-theme-caption"><h3>{text(cluster.zh, cluster.en)}</h3><p>{cluster.id === 'independent' ? text('这些资料各有主题，可逐份阅读。', 'Explore these individual materials in turn.') : text(`${cluster.items.length} 份相关资料 · ${new Set(cluster.items.map(item => item.source_id)).size} 个来源`, `${cluster.items.length} related materials · ${new Set(cluster.items.map(item => item.source_id)).size} sources`)}</p><div className="material-pager"><Button size="icon" variant="ghost" aria-label={text('上一份资料', 'Previous material')} disabled={index <= 0} onClick={() => setSelectedStory(cluster.items[index - 1].story_id)}>‹</Button><span aria-live="polite">{index + 1} / {cluster.items.length}</span><Button size="icon" variant="ghost" aria-label={text('下一份资料', 'Next material')} disabled={index >= cluster.items.length - 1} onClick={() => setSelectedStory(cluster.items[index + 1].story_id)}>›</Button></div></aside>
        <article className="material-article" key={story.story_id}><SourceIdentity source={story.source_name ?? story.source_id} url={story.external_ref}/><h3><button onClick={() => onSelect(story)}>{story.headline}</button></h3>{story.excerpt && <p>{story.excerpt}</p>}<footer><span>{storyDate?.published ? text('来源发布', 'Published') : text('系统发现', 'Observed')} · {storyDate?.dateOnly ? storyDate.value : dateLabel(storyDate?.value, language)}</span><Button variant="outline" onClick={() => onSelect(story)}>{text('阅读资料', 'Read material')}</Button></footer></article>
      </section>
    </>}
    {data && <div className="library-scope"><details><summary>{text('主题与分组说明', 'About subjects and groups')}</summary><p>{text('主题按标题与正文片段匹配，可交叉归类；数量覆盖公开可用资料库。本页内容关联比较当前 48 份以内资料的词语相似度。翻页继续读取其余资料。', 'Subjects match titles and retained passages and may overlap. Counts cover the public usable corpus. Similarity groups compare up to 48 materials on the current page; use pagination to explore the rest.')}</p></details></div>}
  </section>
}

function LibrarySearch({ query, onSearch }: { query: string; onSearch: (value: string) => void }) {
  const { text } = useI18n()
  const [draft, setDraft] = useState(query)
  return <form onSubmit={event => { event.preventDefault(); onSearch(draft.trim()) }}><label className="sr-only" htmlFor="library-corpus-search">{text('检索资料库', 'Search the material library')}</label><input id="library-corpus-search" value={draft} onChange={event => setDraft(event.target.value)} placeholder={text('检索标题与正文片段', 'Search titles and retained passages')}/><Button variant="ghost" type="submit">{text('检索', 'Search')}</Button></form>
}
