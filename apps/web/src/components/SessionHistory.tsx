import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getQuestionSession } from '../lib/api'
import { useI18n } from '../lib/i18n'

const profiles: Record<string, string> = { lookup: 'DIRECT', retrieve: 'RETRIEVE', verify_version_fix: 'VERIFY', watch_incident: 'WATCH' }

export function SessionHistory({ sessionId }: { sessionId: string }) {
  const { text } = useI18n()
  const query = useQuery({ queryKey: ['question-session', sessionId], queryFn: () => getQuestionSession(sessionId) })
  return <details className="session-history">
    <summary>{text('会话记录', 'CONVERSATION HISTORY')} · {query.data?.turns.length ?? '…'}</summary>
    {query.isLoading && <p role="status">{text('加载会话记录…', 'Loading conversation…')}</p>}
    {query.isError && <div role="alert"><p>{text('会话记录读取失败。', 'Conversation history read failed.')}</p><button onClick={() => void query.refetch()}>{text('重试', 'RETRY')}</button></div>}
    <ol>{query.data?.turns.map(turn => {
      const params = new URLSearchParams({ session: sessionId, turn: String(turn.turn_index), profile: profiles[turn.task_kind] ?? 'INVESTIGATE', question: turn.question })
      if (turn.decision_ref) params.set('decision', turn.decision_ref)
      if (turn.investigation_ref) params.set('case', turn.investigation_ref.replace(/^case:/, ''))
      return <li key={turn.turn_index}><small>{text('回合', 'TURN')} {turn.turn_index} · {new Date(turn.created_at).toLocaleString()}</small><p>{turn.question}</p><Link to={`/start?${params.toString()}`}>{turn.decision_ref ? text('查看研判', 'OPEN DECISION') : text('查看调查', 'OPEN INVESTIGATION')}</Link></li>
    })}</ol>
  </details>
}
