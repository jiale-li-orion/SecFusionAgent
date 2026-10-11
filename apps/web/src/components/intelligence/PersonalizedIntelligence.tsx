import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Bookmark, Check, CircleMinus, RefreshCw, Settings2, Sparkles, ThumbsUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getIntelligencePreferences, getIntelligenceRecommendations, saveIntelligenceRecommendationFeedback, type FollowedIntelligenceObject, type IntelligenceRecommendation } from '../../lib/api/recommendations'
import { useI18n } from '../../lib/i18n'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { dateLabel, latestObservedAt } from './feedPresentation'
import { SourceIdentity } from '../ui/source-identity'
import { readableObjectTitle } from '../../lib/source-identity'

export function PersonalizedIntelligence({ following = false, onOpen, publicFeed }: { following?: boolean; onOpen: (objectId: string, evidence?: string) => void; publicFeed?: ReactNode }) {
  const { text, language } = useI18n()
  const queryClient = useQueryClient()
  const [ignored, setIgnored] = useState<{ objectId: string; label: string } | null>(null)
  const [visibleLimit, setVisibleLimit] = useState(12)
  const preferences = useQuery({ queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences, retry: false })
  const configured = Boolean(preferences.data?.keywords.length || preferences.data?.target_object_ids.length)
  const recommendations = useQuery({ queryKey: ['intelligence-recommendations', visibleLimit], queryFn: () => getIntelligenceRecommendations(visibleLimit), enabled: Boolean(preferences.data), retry: false })
  const feedback = useMutation({
    mutationFn: ({ objectId, value }: { objectId: string; value: 'interested' | 'ignored' | 'neutral'; label?: string }) => saveIntelligenceRecommendationFeedback(objectId, value),
    onSuccess: (_, variables) => {
      if (variables.value === 'ignored') setIgnored({ objectId: variables.objectId, label: variables.label ?? text('这条情报', 'This intelligence') })
      else if (ignored?.objectId === variables.objectId) setIgnored(null)
      return queryClient.invalidateQueries({ queryKey: ['intelligence-recommendations'] })
    },
  })
  const items = following
    ? (recommendations.data?.items ?? []).filter(item => item.reasons.some(reason => ['keyword', 'followed_object', 'related_object'].includes(reason.kind)))
      .sort((a, b) => (Date.parse(latestObservedAt(b.evidence) ?? '') || 0) - (Date.parse(latestObservedAt(a.evidence) ?? '') || 0) || a.object_id.localeCompare(b.object_id))
    : recommendations.data?.items ?? []
  if (preferences.isPending) return <div className="intel-feed-empty" role="status">{text('正在读取你的关注…', 'Loading your interests…')}</div>
  if (preferences.isError) return <div className="intel-feed-empty" role="alert"><p>{text('暂时无法读取你的关注设置。', 'Your interests are temporarily unavailable.')}</p><button onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</button></div>
  return <section className="intel-personalized" aria-label={following ? text('关注情报', 'Following') : text('为你推荐', 'For you')}>
    {!following && <div className="intel-personalized-hero"><div><span className="intel-personalized-kicker"><Sparkles size={14}/>{text('属于你的情报流', 'YOUR INTELLIGENCE FEED')}</span><h2>{text('看见与你有关的变化', 'Discover what matters to you')}</h2><p>{text('基于你关注的方向和有来源的材料，持续发现值得读的内容。', 'Follow your interests through sourced material worth reading.')}</p></div>{configured && <Link to="/workspace/profile">{text('调整关注', 'Tune your interests')}<ArrowUpRight size={14}/></Link>}</div>}
    {following && configured && <div className="intel-following-strip"><div><Bookmark size={17}/><strong>{text('我的关注', 'Your interests')}</strong><Link to="/workspace/profile"><Settings2 size={14}/>{text('管理', 'Manage')}</Link></div><div className="intel-interest-chips">{preferences.data?.keywords.map(keyword => <span key={keyword}>#{keyword}</span>)}{preferences.data?.target_objects.map(obj => <button key={obj.object_id} onClick={() => onOpen(obj.object_id)}>{readableLabel(obj.label, text('关注对象', 'Followed object'))}<ArrowUpRight size={12}/></button>)}</div></div>}
    {!configured && <div className="intel-signin-row"><span>{text('选择关注，定制你的推荐', 'Choose your interests to personalize your feed')}</span><Button size="sm" asChild><Link to="/workspace/profile">{text('设置关注', 'Set interests')}<ArrowUpRight size={13}/></Link></Button></div>}
    {(configured || items.length > 0) && <>
      <div className="intel-stream-label"><span>{following ? text('关注动态 · 按发现时间排序', 'Following · newest discoveries first') : text('为你推荐', 'Recommended for you')}</span><button disabled={recommendations.isFetching} onClick={() => void recommendations.refetch()}><RefreshCw size={13} className={recommendations.isFetching ? 'intel-spinning' : ''}/>{text('刷新', 'Refresh')}</button></div>
      {recommendations.isPending && <p className="intel-feed-empty" role="status">{text('正在查找相关情报…', 'Finding related intelligence…')}</p>}
      {recommendations.isError && <p className="intel-feed-error" role="alert">{text('推荐读取失败，请刷新重试。', 'Recommendations could not be loaded. Refresh to retry.')}</p>}
      {!recommendations.isPending && !recommendations.isError && !items.length && <div className="intel-feed-empty"><Bookmark size={28}/><h3>{text('暂时没有匹配的情报', 'No matching intelligence yet')}</h3><p>{text('新的相关内容收录后会出现在这里。也可以调整你的关注。', 'New relevant material will appear here. You can also update your interests.')}</p><Link to="/workspace/profile">{text('管理关注', 'Manage interests')}<ArrowUpRight size={14}/></Link></div>}
      <div className="intel-stream">{items.map((item, index) => {
        const observed = latestObservedAt(item.evidence)
        const sources = groupedSources(item.evidence)
        const origin = item.evidence[0]
        const title = readableObjectTitle(item.label, origin?.canonical_url, origin?.source_id)
        const quotes = item.evidence.map(ref => ref.locator?.quote).filter((quote): quote is string => typeof quote === 'string' && quote.trim().length > 35)
        const quote = (quotes.find(value => item.reasons.some(reason => reason.kind === 'keyword' && value.toLowerCase().includes(reason.value.toLowerCase()))) ?? quotes[0])?.replace(/\s+/g, ' ').trim()
        return <article key={item.object_id} className={`intel-feed-card ${index === 0 && !following ? 'is-lead' : ''}`}>
          <div className="intel-publisher-row"><SourceIdentity source={origin?.source_id} url={origin?.canonical_url}/><span>{observed && dateLabel(observed, language)}</span></div>
          <div className="intel-card-meta"><Badge variant="secondary" className="intel-type-badge">{objectTypeLabel(item.object_type, text)}</Badge><span>{text(`${sources.length} 处来源 · ${item.evidence.length} 份证据`, `${sources.length} sources · ${item.evidence.length} evidence references`)}</span>{item.feedback === 'interested' && <span className="intel-interest-mark"><Check size={12}/>{text('你感兴趣', 'Interested')}</span>}</div>
          <h2><button onClick={() => onOpen(item.object_id)}>{title}</button></h2>
          {quote && <blockquote className="intel-source-excerpt"><p>{quote}</p><span>{text('原文摘录', 'Source excerpt')}</span></blockquote>}
          <div className="intel-match-reasons">{item.reasons.slice(0, 2).map((reason, index) => <p key={`${reason.kind}:${index}`}><Sparkles size={13}/><span>{recommendationReason(reason, text, preferences.data?.target_objects ?? [])}</span></p>)}</div>
          <div className="intel-source-chips">{sources.slice(0, 3).map(source => <button key={source.key} onClick={() => onOpen(item.object_id, source.refs[0])} title={text(`查看 ${source.label} 的来源证据`, `Inspect evidence from ${source.label}`)}>{source.label}{source.refs.length > 1 && <span>{source.refs.length}</span>}<ArrowUpRight size={12}/></button>)}{sources.length > 3 && <button onClick={() => onOpen(item.object_id)}>{text(`全部 ${sources.length} 处来源`, `All ${sources.length} sources`)}</button>}</div>
          <footer><div className="intel-feedback"><button className={item.feedback === 'interested' ? 'is-interested' : ''} aria-pressed={item.feedback === 'interested'} disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: item.object_id, value: item.feedback === 'interested' ? 'neutral' : 'interested' })}><ThumbsUp size={14}/>{text('感兴趣', 'Interested')}</button><button disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: item.object_id, value: 'ignored', label: readableLabel(item.label, text('这条情报', 'This intelligence')) })}><CircleMinus size={14}/>{text('忽略', 'Ignore')}</button></div><button className="intel-read-link" onClick={() => onOpen(item.object_id)}>{text('阅读全文与证据', 'Read with evidence')}<ArrowUpRight size={14}/></button></footer>
        </article>
      })}</div>
      {!recommendations.isPending && !recommendations.isError && recommendations.data?.items.length === visibleLimit && visibleLimit < 24 && <button className="intel-load-more" disabled={recommendations.isFetching} onClick={() => setVisibleLimit(limit => Math.min(limit + 6, 24))}>{text('继续阅读', 'Read more')}<ArrowUpRight size={15}/></button>}
    </>}
    {feedback.isError && <p className="intel-feed-error" role="alert">{text('反馈未保存，请重试。', 'Feedback was not saved. Please retry.')}</p>}
    {ignored && <p className="intel-feedback-notice" role="status">{text(`已忽略「${ignored.label}」`, `Ignored “${ignored.label}”`)}<button disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: ignored.objectId, value: 'neutral' })}>{text('撤销', 'Undo')}</button></p>}
    {!following && (!configured || (!recommendations.isPending && !items.length)) && publicFeed}
  </section>
}

function readableLabel(label: string, fallback: string) { return !label.trim() || /(?:^|[:/])[0-9a-f]{24,}$/i.test(label) || /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(label) ? fallback : label }
function objectTypeLabel(kind: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = { Vulnerability: ['漏洞', 'Vulnerability'], InternetAsset: ['互联网资产', 'Internet asset'], Repository: ['项目仓库', 'Repository'], Repo: ['项目仓库', 'Repository'], ResearchWork: ['研究论文', 'Research'], Document: ['来源资料', 'Document'], Product: ['产品', 'Product'], Package: ['软件包', 'Package'], SoftwareVersion: ['软件版本', 'Software version'], NormativeDocument: ['规范文档', 'Standard'], Incident: ['安全事件', 'Incident'], Commit: ['代码变更', 'Code change'], PullRequest: ['合并请求', 'Pull request'] }
  return text(...(labels[kind] ?? ['情报对象', 'Intelligence object']))
}
function recommendationReason(reason: IntelligenceRecommendation['reasons'][number], text: (zh: string, en: string) => string, followed: FollowedIntelligenceObject[]) {
  if (reason.kind === 'keyword') return text(`与你关注的「${reason.value}」有关`, `Related to your interest in “${reason.value}”`)
  if (reason.kind === 'followed_object') return text('来自你关注的对象', 'From an object you follow')
  if (reason.kind === 'related_object') {
    const target = followed.find(item => item.object_id === reason.value)
    return target ? text(`已有证据关联到「${readableLabel(target.label, '关注对象')}」`, `Evidence connects it to “${readableLabel(target.label, 'a followed object')}”`) : text('与你关注的对象存在已留证关系', 'Evidence connects it to an object you follow')
  }
  return text('你曾将这条情报标为感兴趣', 'You marked this intelligence as interesting')
}
function groupedSources(evidence: IntelligenceRecommendation['evidence']) {
  const groups = new Map<string, { key: string; label: string; refs: string[] }>()
  for (const item of evidence) {
    let label = item.source_id || 'Source'
    if (item.canonical_url) { try { label = new URL(item.canonical_url).hostname.replace(/^www\./, '') } catch { /* Non-web sources retain their source identity. */ } }
    const existing = groups.get(label)
    if (existing) { if (!existing.refs.includes(item.evidence_ref)) existing.refs.push(item.evidence_ref) }
    else groups.set(label, { key: label, label, refs: [item.evidence_ref] })
  }
  return [...groups.values()]
}
