import { useState, type ReactNode } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bookmark } from "@phosphor-icons/react/dist/csr/Bookmark"
import { MinusCircle as CircleMinus } from "@phosphor-icons/react/dist/csr/MinusCircle"
import { DotsThree as MoreHorizontal } from "@phosphor-icons/react/dist/csr/DotsThree"
import { ArrowsClockwise as RefreshCw } from "@phosphor-icons/react/dist/csr/ArrowsClockwise"
import { SlidersHorizontal as Settings2 } from "@phosphor-icons/react/dist/csr/SlidersHorizontal"
import { Sparkle as Sparkles } from "@phosphor-icons/react/dist/csr/Sparkle"
import { ThumbsUp } from "@phosphor-icons/react/dist/csr/ThumbsUp"
import { X } from "@phosphor-icons/react/dist/csr/X"
import { Link, useSearchParams } from 'react-router-dom'
import { getIntelligencePreferences, getIntelligenceFeed, saveIntelligenceActivityFeedback, saveIntelligencePreferences, type FollowedIntelligenceObject, type IntelligenceRecommendation } from '../../lib/api/recommendations'
import { useI18n } from '../../lib/i18n'
import { Item, ItemContent } from '../ui/item'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuRadioGroup, DropdownMenuRadioItem } from '../ui/dropdown-menu'
import { ChevronDown } from '../ui/icons'
import { Button } from '../ui/button'
import { dateLabel, latestObservedAt, presentationTitle } from './feedPresentation'
import { SourceIdentity } from '../ui/source-identity'
import { readableObjectTitle } from '../../lib/source-identity'

export function PersonalizedIntelligence({ following = false, onOpen }: { following?: boolean; onOpen: (objectId: string, evidence?: string) => void; publicFeed?: ReactNode }) {
  const { text, language } = useI18n()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  function objectLink(id: string) { const next = new URLSearchParams(); next.set('channel', following ? 'following' : 'recommended'); if (params.get('category')) next.set('category', params.get('category')!); next.set('object', id); return `/intelligence?${next}` }
  const [ignored, setIgnored] = useState<{ objectId: string; label: string } | null>(null)
  const [window, setWindow] = useState<'30d' | 'all'>('30d')
  const windowLabel = window === '30d' ? text('最近 30 天', 'Last 30 days') : text('包含更早', 'Include older')
  const preferences = useQuery({ queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences, retry: false })
  const configured = Boolean(preferences.data?.keywords.length || preferences.data?.target_object_ids.length)
  const mode = following ? 'following' : 'recommended'
  const recommendations = useInfiniteQuery({ queryKey: ['intelligence-feed', mode, window], initialPageParam: undefined as string | undefined, queryFn: ({ pageParam }) => getIntelligenceFeed(mode, window, pageParam), getNextPageParam: page => page.next_cursor ?? undefined, enabled: Boolean(preferences.data), retry: false })
  const unfollow = useMutation({ mutationFn: (objectId: string) => saveIntelligencePreferences({ keywords: preferences.data?.keywords ?? [], target_object_ids: (preferences.data?.target_object_ids ?? []).filter(id => id !== objectId) }), onSuccess: async data => { queryClient.setQueryData(['intelligence-preferences'], data); await queryClient.invalidateQueries({ queryKey: ['intelligence-feed'] }); await queryClient.invalidateQueries({ queryKey: ['intelligence-recommendations'] }) } })
  const feedback = useMutation({
    mutationFn: ({ objectId, value }: { objectId: string; value: 'interested' | 'ignored' | 'neutral'; label?: string }) => saveIntelligenceActivityFeedback(objectId, value),
    onSuccess: (_, variables) => {
      if (variables.value === 'ignored') setIgnored({ objectId: variables.objectId, label: variables.label ?? text('这条情报', 'This intelligence') })
      else if (ignored?.objectId === variables.objectId) setIgnored(null)
      return queryClient.invalidateQueries({ queryKey: ['intelligence-feed'] })
    },
  })
  const items = recommendations.data?.pages.flatMap(page => page.items) ?? []
  if (preferences.isPending) return <div className="intel-feed-empty" role="status">{text('正在读取你的关注…', 'Loading your interests…')}</div>
  if (preferences.isError) return <div className="intel-feed-empty" role="alert"><p>{text('暂时无法读取你的关注设置。', 'Your interests are temporarily unavailable.')}</p><button onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</button></div>
  return <section className="intel-personalized" aria-label={following ? text('关注情报', 'Following') : text('为你推荐', 'For you')}>
    {configured && <div className="intel-following-strip"><div><Bookmark size={17}/><strong>{text('我的关注', 'Your interests')}</strong><Link to="/workspace/profile"><Settings2 size={14}/>{text('管理', 'Manage')}</Link></div><div className="intel-interest-chips">{preferences.data?.keywords.map(keyword => <span key={keyword}>#{keyword}</span>)}{preferences.data?.target_objects.map(obj => <span key={obj.object_id}><button onClick={() => onOpen(obj.object_id)}>{readableLabel(obj.label, text('关注对象', 'Followed object'))}</button><Link to={`${objectLink(obj.object_id)}&view=graph`} aria-label={text(`查看 ${obj.label} 的关联`, `Connections for ${obj.label}`)}>{text('关联', 'Connections')}</Link><button disabled={unfollow.isPending} aria-label={text(`取消关注 ${obj.label}`, `Unfollow ${obj.label}`)} onClick={() => unfollow.mutate(obj.object_id)}><X size={12}/></button></span>)}</div></div>}
    {!configured && <div className="intel-signin-row"><span>{text('选择关注，定制你的推荐', 'Choose your interests to personalize your feed')}</span><Button size="sm" asChild><Link to="/workspace/profile">{text('设置关注', 'Set interests')}</Link></Button></div>}
    {(!following || configured) && <>
      <div className="intel-stream-label"><span>{following ? text('关注动态 · 按内容时间排序', 'Following · newest first') : text('为你推荐', 'Recommended for you')}</span><div className="flex items-center gap-2 text-xs"><span>{text('时间范围', 'Period')}</span><DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="sm" className="font-normal" aria-label={`${text('时间范围：', 'Period: ')}${windowLabel}`}>{windowLabel}<ChevronDown size={14}/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuRadioGroup value={window} onValueChange={value => { if (value === '30d' || value === 'all') setWindow(value) }}><DropdownMenuRadioItem value="30d">{text('最近 30 天', 'Last 30 days')}</DropdownMenuRadioItem><DropdownMenuRadioItem value="all">{text('包含更早', 'Include older')}</DropdownMenuRadioItem></DropdownMenuRadioGroup></DropdownMenuContent></DropdownMenu></div><button disabled={recommendations.isFetching} onClick={() => void recommendations.refetch()}><RefreshCw size={13} className={recommendations.isFetching ? 'intel-spinning' : ''}/>{text('刷新', 'Refresh')}</button></div>
      {recommendations.isPending && <p className="intel-feed-empty" role="status">{text('正在查找相关情报…', 'Finding related intelligence…')}</p>}
      {recommendations.isError && <p className="intel-feed-error" role="alert">{text('推荐读取失败，请刷新重试。', 'Recommendations could not be loaded. Refresh to retry.')}</p>}
      {!recommendations.isPending && !recommendations.isError && !items.length && <div className="intel-feed-empty"><Bookmark size={28}/><h3>{text('暂时没有匹配的情报', 'No matching intelligence yet')}</h3><p>{text('新的相关内容收录后会出现在这里。也可以调整你的关注。', 'New relevant material will appear here. You can also update your interests.')}</p><Link to="/workspace/profile">{text('管理关注', 'Manage interests')}</Link></div>}
      <div className="intel-reading-feed">{items.map(item => {
        const observed = item.activity_at ?? item.published_at ?? item.observed_at ?? latestObservedAt(item.evidence)
        const origin = item.evidence.find(ref => ref.evidence_ref === item.activity_evidence_ref) ?? item.evidence.find(ref => ref.evidence_ref === item.timestamp_evidence_ref) ?? item.evidence[0]
        const title = presentationTitle(item.title || readableObjectTitle(item.label, origin?.canonical_url, origin?.source_id))
        const summary = item.summary?.replace(/\s+/g, ' ').trim()
        const reason = item.reasons[0]
        return <Item asChild key={item.activity_id} className="rounded-none border-0 border-b border-border px-0 py-6 sm:py-7"><article>
          <ItemContent className="min-w-0 gap-3">
            <h2 className="m-0 text-lg font-semibold leading-snug tracking-tight [overflow-wrap:anywhere] sm:text-xl"><Link className="transition-colors hover:text-primary focus-visible:underline" to={objectLink(item.object_id)}>{title}</Link></h2>
            <div className="intel-reading-byline"><SourceIdentity source={origin?.source_id} url={origin?.canonical_url}/><span>{objectTypeLabel(item.object_type, text)}</span>{observed && <time dateTime={observed}>{item.activity_at && item.published_at && item.activity_at !== item.published_at ? text('更新于 ', 'Updated ') : item.published_at ? '' : text('发现于 ', 'Observed ')}{dateLabel(observed, language)}</time>}</div>
            {summary && <p className="intel-reading-summary">{item.preview_origin === 'retained_excerpt' && <span className="mr-2 text-xs text-muted-foreground">{text('原文摘录', 'Source excerpt')}</span>}{summary}</p>}
            {reason && <p className="intel-reading-reason"><Sparkles size={13}/>{recommendationReason(reason, text, preferences.data?.target_objects ?? [])}</p>}
            <div className="flex items-center justify-between gap-2 pt-1">
              <Button variant="ghost" size="sm" className="-ml-3 text-muted-foreground" aria-pressed={item.feedback === 'interested'} disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: item.activity_id, value: item.feedback === 'interested' ? 'neutral' : 'interested' })}><ThumbsUp size={14} className={item.feedback === 'interested' ? 'fill-primary/15 text-primary' : ''}/>{item.feedback === 'interested' ? text('已感兴趣', 'Interested') : text('感兴趣', 'Interested')}</Button>
              <div className="flex items-center gap-1"><Button variant="ghost" size="sm" className="min-h-11 pr-1" onClick={() => onOpen(item.object_id, item.preview_evidence_refs?.[0] ?? origin?.evidence_ref)}>{text('查看来源', 'Sources')}</Button><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={text(`更多操作：${title}`, `More actions for ${title}`)}><MoreHorizontal size={18}/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem disabled={feedback.isPending} onSelect={() => feedback.mutate({ objectId: item.activity_id, value: 'ignored', label: title })}><CircleMinus size={15}/>{text('忽略这条动态', 'Ignore this update')}</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div>
            </div>
          </ItemContent>
        </article></Item>
      })}</div>
      {!recommendations.isPending && !recommendations.isError && recommendations.hasNextPage && <button className="intel-load-more" disabled={recommendations.isFetching} onClick={() => void recommendations.fetchNextPage()}>{text('继续阅读', 'Read more')}</button>}
    </>}
    {unfollow.isError && <p role="alert">{text('取消关注失败，请重试。', 'Could not unfollow. Please retry.')}</p>}
    {feedback.isError && <p className="intel-feed-error" role="alert">{text('反馈未保存，请重试。', 'Feedback was not saved. Please retry.')}</p>}
    {ignored && <p className="intel-feedback-notice" role="status">{text(`已忽略「${ignored.label}」`, `Ignored “${ignored.label}”`)}<button disabled={feedback.isPending} onClick={() => feedback.mutate({ objectId: ignored.objectId, value: 'neutral' })}>{text('撤销', 'Undo')}</button></p>}
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
