import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, ChevronDown } from 'lucide-react'
import { Link } from 'react-router-dom'
import { listAccountConversations, type AccountConversation } from '../../lib/api/investigations'
import { useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'

const profiles: Record<string, string> = {
  lookup: 'DIRECT', retrieve: 'RETRIEVE', verify_version_fix: 'VERIFY', watch_incident: 'WATCH',
}

function continuationLink(conversation: AccountConversation): string {
  const turn = conversation.latest_turn
  const params = new URLSearchParams({
    session: conversation.session_id,
    turn: String(turn.turn_index),
    request: turn.request_id,
    question: turn.question,
    profile: profiles[turn.task_kind] ?? 'INVESTIGATE',
  })
  if (turn.decision_ref) params.set('decision', turn.decision_ref)
  else if (turn.investigation_ref) params.set('case', turn.investigation_ref.replace(/^case:/, ''))
  const target = turn.target_object_ids[0]
  if (target) params.set('object', target)
  return `/start?${params.toString()}`
}

export function AccountConversations({ currentSessionId }: { currentSessionId?: string }) {
  const { text, language } = useI18n()
  const { authenticated } = useAuth()
  const [expanded, setExpanded] = useState(false)
  const query = useQuery({
    queryKey: ['account-conversations'],
    queryFn: ({ signal }) => listAccountConversations(20, signal),
    enabled: authenticated,
    retry: false,
    refetchOnWindowFocus: true,
  })
  const conversations = query.data?.items ?? []
  const visible = expanded ? conversations : conversations.slice(0, 3)

  return <section className="account-conversations" aria-label={text('最近会话', 'Recent conversations')}>
    <header><h2>{text('继续之前的探索', 'Continue an earlier inquiry')}</h2><span>{text('最近会话', 'RECENT CONVERSATIONS')}</span></header>
    {query.isLoading && <p role="status">{text('正在读取你的会话…', 'Loading your conversations…')}</p>}
    {query.isError && <div className="account-conversations-error" role="alert"><p>{text('暂时无法读取会话。', 'Your conversations could not be loaded.')}</p><button type="button" onClick={() => void query.refetch()}>{text('重试', 'Retry')}</button></div>}
    {query.isSuccess && conversations.length === 0 && <p>{text('提出第一个问题，之后可以从这里继续。', 'Ask your first question, then return here to continue.')}</p>}
    {visible.length > 0 && <ol>{visible.map(conversation => {
      const current = conversation.session_id === currentSessionId
      const date = new Date(conversation.updated_at)
      return <li key={conversation.session_id}>
        <Link to={continuationLink(conversation)} aria-current={current ? 'page' : undefined}>
          <span className="account-conversation-title">{conversation.latest_turn.question}</span>
          <time dateTime={conversation.updated_at}>{date.toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time>
          <span className="account-conversation-continue">{current ? text('当前会话', 'Current') : text('继续', 'Continue')}<ArrowUpRight size={14} aria-hidden="true" /></span>
        </Link>
      </li>
    })}</ol>}
    {conversations.length > 3 && <button className="account-conversations-expand" type="button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      {expanded ? text('收起', 'Show fewer') : text(`查看其余 ${conversations.length - 3} 个会话`, `Show ${conversations.length - 3} more conversations`)}<ChevronDown size={14} aria-hidden="true" />
    </button>}
    {expanded && query.data?.has_more && <p className="account-conversations-limit">{text('显示最近 20 个会话。', 'Showing your 20 most recent conversations.')}</p>}
  </section>
}
