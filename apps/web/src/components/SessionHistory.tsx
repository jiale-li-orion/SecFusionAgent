import { useInfiniteQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { getQuestionSession } from '../lib/api'
import { useI18n } from '../lib/i18n'

const profiles: Record<string, string> = { lookup: 'DIRECT', retrieve: 'RETRIEVE', verify_version_fix: 'VERIFY', watch_incident: 'WATCH' }

export function SessionHistory({ sessionId }: { sessionId: string }) {
  const { text } = useI18n()
  const [currentParams] = useSearchParams()
  const query = useInfiniteQuery({
    queryKey: ['question-session', sessionId, 'pages'],
    queryFn: ({ pageParam, signal }) => getQuestionSession(sessionId, pageParam, signal),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: last => last.next_before_turn ?? undefined,
  })
  const turns = query.data?.pages.slice().reverse().flatMap(page => page.turns) ?? []
  return <details className="session-history">
    <summary>{text('会话记录', 'CONVERSATION HISTORY')} · {turns.length}{query.hasNextPage ? '+' : ''}</summary>
    {query.isLoading && <p role="status">{text('加载会话记录…', 'Loading conversation…')}</p>}
    {query.isError && <div role="alert"><p>{text('会话记录读取失败。', 'Conversation history read failed.')}</p><button onClick={() => void query.refetch()}>{text('重试', 'RETRY')}</button></div>}
    {query.hasNextPage && <button onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}>{query.isFetchingNextPage ? text('读取中…', 'Loading…') : text('更早回合', 'Earlier turns')}</button>}
    {query.isFetchNextPageError && <button onClick={() => void query.fetchNextPage()}>{text('重试更早回合', 'Retry earlier turns')}</button>}
    <ol>{turns.map(turn => {
      const params = new URLSearchParams({ session: sessionId, turn: String(turn.turn_index), profile: profiles[turn.task_kind] ?? 'INVESTIGATE' })
      ;['cve', 'object', 'targetLabel'].forEach(key => { const value = currentParams.get(key); if (value) params.set(key, value) })
      if (turn.decision_ref) params.set('decision', turn.decision_ref)
      if (turn.investigation_ref) params.set('case', turn.investigation_ref.replace(/^case:/, ''))
      return <li key={turn.turn_index}><small>{text('回合', 'TURN')} {turn.turn_index} · {new Date(turn.created_at).toLocaleString()}</small><p>{turn.question}</p><Link to={`/start?${params.toString()}`}>{turn.decision_ref ? text('查看研判', 'OPEN DECISION') : text('查看调查', 'OPEN INVESTIGATION')}</Link></li>
    })}</ol>
  </details>
}
