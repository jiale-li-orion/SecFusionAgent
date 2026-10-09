import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Bookmark, Check, Search, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { searchIntelligence } from '../../lib/api/intelligence'
import {
  getIntelligencePreferences,
  getIntelligenceRecommendations,
  saveIntelligencePreferences,
  saveIntelligenceRecommendationFeedback,
  type FollowedIntelligenceObject,
  type IntelligenceRecommendation,
} from '../../lib/api/recommendations'
import { useI18n } from '../../lib/i18n'
import { ProductGlyph } from '../instrument/ProductGlyph'

type PreferenceDraft = { keywordText: string; objects: FollowedIntelligenceObject[] }

export function PersonalizedIntelligence() {
  const { text } = useI18n()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<PreferenceDraft | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [objectQuery, setObjectQuery] = useState('')
  const [saved, setSaved] = useState(false)
  const [ignored, setIgnored] = useState<{ objectId: string; label: string } | null>(null)
  const [visibleLimit, setVisibleLimit] = useState(6)
  const preferences = useQuery({
    queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences, retry: false,
  })
  const current = draft ?? {
    keywordText: preferences.data?.keywords.join('，') ?? '',
    objects: preferences.data?.target_objects ?? [],
  }
  const keywords = [...new Set(current.keywordText.split(/[,，;；\n]+/).map((item) => item.trim()).filter(Boolean))]
  const objectSearch = useQuery({
    queryKey: ['recommendation-object-search', objectQuery],
    queryFn: () => searchIntelligence(objectQuery, 6),
    enabled: objectQuery.length >= 2, retry: false, staleTime: 30_000,
  })
  const recommendations = useQuery({
    queryKey: ['intelligence-recommendations', visibleLimit], queryFn: () => getIntelligenceRecommendations(visibleLimit),
    enabled: Boolean(preferences.data), retry: false,
  })
  const save = useMutation({
    mutationFn: () => saveIntelligencePreferences({
      keywords, target_object_ids: current.objects.map((item) => item.object_id),
    }),
    onSuccess: (profile) => {
      queryClient.setQueryData(['intelligence-preferences'], profile)
      setDraft(null)
      setSaved(true)
      setVisibleLimit(6)
      void queryClient.invalidateQueries({ queryKey: ['intelligence-recommendations'] })
    },
  })
  const feedback = useMutation({
    mutationFn: ({ objectId, value }: { objectId: string; value: 'interested' | 'ignored' | 'neutral'; label?: string }) =>
      saveIntelligenceRecommendationFeedback(objectId, value),
    onSuccess: (_, variables) => {
      if (variables.value === 'ignored') setIgnored({ objectId: variables.objectId, label: variables.label ?? text('这条情报', 'This intelligence') })
      else if (ignored?.objectId === variables.objectId) setIgnored(null)
      return queryClient.invalidateQueries({ queryKey: ['intelligence-recommendations'] })
    },
  })
  function edit(next: PreferenceDraft) {
    setDraft(next)
    setSaved(false)
  }
  const configured = Boolean(preferences.data?.keywords.length || preferences.data?.target_object_ids.length)
  const items = recommendations.data?.items ?? []
  const limitExceeded = keywords.length > 20 || current.objects.length > 20
  const keywordTooLong = keywords.some((keyword) => keyword.length > 128)

  return <section className="personalized-intelligence" aria-label={text('我的关注情报', 'Intelligence for you')}>
    <header>
      <div><small>{text('我的关注', 'YOUR INTERESTS')}</small><h2>{text('与你有关的情报', 'Intelligence that matters to you')}</h2></div>
      <p>{text('告诉我们你使用的技术和关心的对象。推荐会说明匹配原因，并保留查看来源的入口。', 'Tell us which technologies and objects you care about. Each recommendation explains the match and links to its sources.')}</p>
    </header>
    {preferences.isPending ? <p role="status">{text('读取你的关注设置…', 'Loading your interests…')}</p>
      : preferences.isError ? <p role="alert">{text('关注设置暂时不可读。', 'Your interests are temporarily unavailable.')} <button type="button" onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</button></p>
      : <div className="recommendation-preferences">
        <form onSubmit={(event) => { event.preventDefault(); if (!limitExceeded && !keywordTooLong) save.mutate() }}>
          <label htmlFor="recommendation-keywords">{text('关注的关键词或技术', 'Keywords or technologies you follow')}</label>
          <textarea id="recommendation-keywords" rows={2} maxLength={2000} value={current.keywordText} disabled={save.isPending}
            placeholder={text('例如：vLLM、LangChain、提示词注入；用逗号或换行分隔', 'For example: vLLM, LangChain, prompt injection. Separate entries with commas or new lines.')}
            onChange={(event) => edit({ ...current, keywordText: event.target.value })} />
          <p>{text('只使用你保存的关注内容与反馈来筛选情报。最多 20 个关键词、20 个对象。', 'Saved interests and feedback shape your recommendations. Up to 20 keywords and 20 objects.')}</p>
          <div className="recommendation-object-chips" aria-label={text('已选择的关注对象', 'Selected objects')}>
            {current.objects.map((item) => <span key={item.object_id}>
              {readableLabel(item.label, text('已选对象', 'Selected object'))}
              <button type="button" disabled={save.isPending} aria-label={text('移除关注对象', 'Remove followed object')}
                onClick={() => edit({ ...current, objects: current.objects.filter((obj) => obj.object_id !== item.object_id) })}><X size={13} /></button>
            </span>)}
          </div>
          {limitExceeded && <p role="alert">{text('请将关键词与对象分别减少至 20 个以内。', 'Limit keywords and objects to 20 entries each.')}</p>}
          {keywordTooLong && <p role="alert">{text('每个关键词最多 128 个字符，请缩短后保存。', 'Each keyword can contain up to 128 characters. Shorten long entries before saving.')}</p>}
          <button type="submit" className="ew-primary" disabled={save.isPending || limitExceeded || keywordTooLong}>
            {save.isPending ? text('正在保存…', 'Saving…') : text('保存关注并查看推荐', 'Save interests and see recommendations')}<ArrowRight size={15} />
          </button>
          {saved && <p role="status"><Check size={14} />{text('关注设置已保存。', 'Your interests are saved.')}</p>}
          {save.isError && <p role="alert">{text('关注设置未保存，请重试。', 'Your interests were not saved. Please retry.')}</p>}
        </form>
        <div className="recommendation-object-search">
          <form onSubmit={(event) => { event.preventDefault(); setObjectQuery(searchInput.trim()) }}>
            <label htmlFor="recommendation-object-query">{text('关注对象或资产', 'Follow an object or asset')}</label>
            <div><input id="recommendation-object-query" value={searchInput} maxLength={256}
              placeholder={text('搜索项目、漏洞、技术、域名或地址', 'Search a project, vulnerability, technology, domain or address')}
              onChange={(event) => setSearchInput(event.target.value)} />
              <button type="submit" disabled={searchInput.trim().length < 2 || objectSearch.isFetching}><Search size={15} />{text('查找', 'Search')}</button></div>
          </form>
          <p>{text('从已收录的对象中选择，保存后开始关注。', 'Choose from retained objects, then save to follow them.')}</p>
          {objectSearch.isFetching && <p role="status">{text('正在查找…', 'Searching…')}</p>}
          {objectSearch.isError && <p role="alert">{text('对象查找暂时失败。', 'Object search is temporarily unavailable.')} <button type="button" onClick={() => void objectSearch.refetch()}>{text('重试', 'Retry')}</button></p>}
          <div className="recommendation-object-options">{objectSearch.data?.items.map((item) => {
            const selected = current.objects.some((obj) => obj.object_id === item.object_id)
            return <button key={item.object_id} type="button" disabled={selected || save.isPending || current.objects.length >= 20}
              onClick={() => edit({ ...current, objects: [...current.objects, item] })}>
              <strong>{readableLabel(item.label, text('情报对象', 'Intelligence object'))}</strong>
              <small>{objectTypeLabel(item.object_type, text)}</small>{selected ? <Check size={15} /> : <Bookmark size={15} />}
            </button>
          })}</div>
          {objectSearch.data && !objectSearch.data.items.length && <p>{text('未找到匹配对象，可以先保存相关关键词。', 'No matching objects found. You can follow related keywords first.')}</p>}
        </div>
      </div>}
    {preferences.data && <div className="recommendation-results">
      <header><div><h3>{text('为你推荐', 'Recommended for you')}</h3>
        {items.length > 0 && <small>{text(`当前显示 ${items.length} 条有证据的匹配情报`, `Showing ${items.length} evidence-backed matches`)}</small>}</div>
        <button type="button" disabled={recommendations.isFetching} onClick={() => void recommendations.refetch()}>{text('刷新推荐', 'Refresh recommendations')}</button></header>
      {recommendations.isPending ? <p role="status">{text('正在查找相关情报…', 'Finding related intelligence…')}</p>
        : recommendations.isError ? <p role="alert">{text('推荐暂时不可读，请稍后刷新。', 'Recommendations are temporarily unavailable. Refresh to retry.')}</p>
        : items.length === 0 ? <p>{configured
          ? text('目前没有匹配你的关注内容的情报。可以调整关键词，或关注其他对象。', 'No retained intelligence matches your interests yet. Adjust your keywords or follow another object.')
          : text('先添加一个关注关键词或对象，保存后即可查看相关情报。', 'Add a keyword or object and save your interests to see related intelligence.')}</p>
          : items.map((item, index) => <article key={item.object_id} className="recommendation-card">
            <div className="recommendation-card-head">
              <span className="recommendation-card-seal"><ProductGlyph kind={item.object_type} size={46} /></span>
              <div><small>{objectTypeLabel(item.object_type, text)}{item.feedback === 'interested' && ` · ${text('你感兴趣', 'Interested')}`}</small>
                <h4><Link to={dossierUrl(item.object_id)}>{readableLabel(item.label, text('情报对象', 'Intelligence object'))}</Link></h4></div>
              <span className="recommendation-card-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
            </div>
            <ul className="recommendation-reasons">{item.reasons.map((reason, index) => <li key={`${reason.kind}:${index}`}>
              <span>{recommendationReason(reason, text, preferences.data?.target_objects ?? [])}</span>
              {reason.evidence_refs[0] && <Link to={`${dossierUrl(item.object_id)}&evidence=${encodeURIComponent(reason.evidence_refs[0])}`}>
                {text('查看依据', 'Inspect evidence')}<ArrowRight size={11} />
              </Link>}
            </li>)}</ul>
            <div className="recommendation-evidence">{item.evidence.slice(0, 3).map((evidence, index) => <Link key={evidence.evidence_ref}
              to={`${dossierUrl(item.object_id)}&evidence=${encodeURIComponent(evidence.evidence_ref)}`}>
              {sourceLabel(evidence.canonical_url, index, text)}
            </Link>)}</div>
            <div className="recommendation-feedback">
              <Link to={dossierUrl(item.object_id)}>{text('打开档案', 'Open dossier')}<ArrowRight size={14} /></Link>
              <button type="button" aria-pressed={item.feedback === 'interested'} disabled={feedback.isPending}
                onClick={() => feedback.mutate({ objectId: item.object_id, value: item.feedback === 'interested' ? 'neutral' : 'interested' })}>
                {item.feedback === 'interested' ? text('取消感兴趣', 'Clear interest') : text('感兴趣', 'Interested')}
              </button>
              <button type="button" disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: item.object_id, value: 'ignored', label: readableLabel(item.label, text('这条情报', 'This intelligence')) })}>{text('忽略', 'Ignore')}</button>
            </div>
          </article>)}
      {!recommendations.isPending && !recommendations.isError && items.length === visibleLimit && visibleLimit < 24 &&
        <button className="recommendation-more" type="button" disabled={recommendations.isFetching}
          onClick={() => setVisibleLimit((limit) => Math.min(limit + 6, 24))}>
          <span>{recommendations.isFetching ? text('正在读取更多情报…', 'Loading more intelligence…') : text('继续浏览相关情报', 'Explore more relevant intelligence')}</span>
          <ArrowRight size={16} />
        </button>}
      {feedback.isError && <p role="alert">{text('反馈未保存，请重试。', 'Feedback was not saved. Please retry.')}</p>}
      {ignored && <p className="recommendation-undo" role="status">{text(`已忽略「${ignored.label}」`, `Ignored “${ignored.label}”`)} <button disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: ignored.objectId, value: 'neutral' })}>{text('撤销', 'Undo')}</button></p>}
    </div>}
  </section>
}

function dossierUrl(objectId: string) { return `/intelligence?${new URLSearchParams({ object: objectId }).toString()}` }
function readableLabel(label: string, fallback: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(label) ? fallback : label
}
function objectTypeLabel(kind: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = {
    Vulnerability: ['漏洞', 'Vulnerability'], InternetAsset: ['互联网资产', 'Internet asset'],
    Repository: ['项目仓库', 'Repository'], Repo: ['项目仓库', 'Repository'],
    ResearchWork: ['研究论文', 'Research'], Document: ['来源资料', 'Document'],
    Product: ['产品', 'Product'], Package: ['软件包', 'Package'], SoftwareVersion: ['软件版本', 'Software version'],
    NormativeDocument: ['规范文档', 'Standard'], Incident: ['安全事件', 'Incident'],
    Commit: ['代码变更', 'Code change'], PullRequest: ['合并请求', 'Pull request'],
  }
  return text(...(labels[kind] ?? ['情报对象', 'Intelligence object']))
}
function recommendationReason(reason: IntelligenceRecommendation['reasons'][number], text: (zh: string, en: string) => string, followed: FollowedIntelligenceObject[]) {
  if (reason.kind === 'keyword') return text(`匹配你的关注词「${reason.value}」`, `Matches your keyword “${reason.value}”`)
  if (reason.kind === 'followed_object') return text('这是你关注的对象', 'You follow this object')
  if (reason.kind === 'related_object') {
    const target = followed.find((item) => item.object_id === reason.value)
    return target
      ? text(`已有证据记录它与「${readableLabel(target.label, '关注对象')}」的关系`, `Retained evidence links it to “${readableLabel(target.label, 'a followed object')}”`)
      : text('与你关注的对象存在已留证关系', 'Retained evidence links it to an object you follow')
  }
  return text('你曾将这条情报标为感兴趣', 'You marked this intelligence as interesting')
}
function sourceLabel(url: string | null, index: number, text: (zh: string, en: string) => string) {
  if (url) {
    try { return text(`来源：${new URL(url).hostname.replace(/^www\./, '')}`, `Source: ${new URL(url).hostname.replace(/^www\./, '')}`) } catch { /* Use the evidence position when a source has no web URL. */ }
  }
  return text(`来源证据 ${index + 1}`, `Source evidence ${index + 1}`)
}
