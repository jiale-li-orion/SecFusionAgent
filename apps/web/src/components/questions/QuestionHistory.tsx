import { useInfiniteQuery } from '@tanstack/react-query'
import { ChevronRight, MessageSquarePlus, ShieldCheck } from 'lucide-react'
import { Button } from '../ui/button'
import { Link } from 'react-router-dom'
import { listAccountConversations } from '../../lib/api/investigations'
import { useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'

export function QuestionHistory({ sessionId, onSelect, onNew }: {
  sessionId: string | null
  onSelect: () => void
  onNew: () => void
}) {
  const { text, language } = useI18n()
  const { authenticated } = useAuth()
  const conversations = useInfiniteQuery({
    queryKey: ['account-conversations', 'pages'],
    queryFn: ({ pageParam, signal }) => listAccountConversations(20, signal, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: last => last.next_cursor ?? undefined,
    enabled: authenticated,
    retry: false,
  })
  const items = conversations.data?.pages.flatMap(page => page.items) ?? []
  return <div className="qa-history">
    <Button className="qa-history-new" onClick={onNew}><MessageSquarePlus size={18} />{text('开始新对话', 'Start a new conversation')}</Button>
    {!authenticated && <div className="qa-history-empty"><p>{text('登录后，你的对话会在这里保存。', 'Sign in to keep your conversations here.')}</p><Link to="/auth?returnTo=%2Fstart" onClick={onSelect}>{text('登录账户', 'Sign in')}<ChevronRight size={14} /></Link></div>}
    {authenticated && conversations.isLoading && <p className="qa-muted" role="status">{text('正在读取对话…', 'Loading conversations…')}</p>}
    {conversations.isError && <div className="qa-error"><span>{text('暂时无法读取历史对话。', 'History is temporarily unavailable.')}</span><button onClick={() => void conversations.refetch()}>{text('重试', 'Retry')}</button></div>}
    {authenticated && !conversations.isLoading && !conversations.isError && !items.length && <p className="qa-history-empty">{text('从第一个问题开始。下次回来，可以接着聊。', 'Start with your first question. Pick up here whenever you return.')}</p>}
    <nav className="qa-session-list" aria-label={text('已保存的对话', 'Saved conversations')}>{items.map((item, index) => {
      const day = new Date(item.updated_at).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'long', day: 'numeric' })
      const previousDay = index > 0 ? new Date(items[index - 1].updated_at).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'long', day: 'numeric' }) : ''
      const current = item.session_id === sessionId
      const params = new URLSearchParams({ session: item.session_id, turn: String(item.latest_turn.turn_index) })
      return <div key={item.session_id}>
        {day !== previousDay && <h3>{day}</h3>}
        <Link to={`/start?${params}`} className={current ? 'current' : ''} aria-current={current ? 'page' : undefined} onClick={onSelect}>
          <span>{item.latest_turn.question}</span><ChevronRight size={15} />
        </Link>
      </div>
    })}</nav>
    {conversations.hasNextPage && <button className="qa-load-more" onClick={() => void conversations.fetchNextPage()} disabled={conversations.isFetchingNextPage}>{conversations.isFetchingNextPage ? text('正在读取…', 'Loading…') : text('更早的对话', 'Earlier conversations')}</button>}
    {conversations.isFetchNextPageError && <button className="qa-retry" onClick={() => void conversations.fetchNextPage()}>{text('重试读取更早对话', 'Retry earlier conversations')}</button>}
    {authenticated && <p className="qa-history-note"><ShieldCheck size={15} />{text('你的对话与调查，仅自己可见。', 'Your conversations and investigations are private.')}</p>}
  </div>
}
