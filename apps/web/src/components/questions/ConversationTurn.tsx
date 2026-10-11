import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, ChevronRight, ScanLine, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'
import { DecisionReport } from '../DecisionReport'
import { getDecision, getInvestigation, type QuestionSessionTurn } from '../../lib/api/investigations'
import { useI18n } from '../../lib/i18n'
import { displayUnknowns } from '../../lib/investigationPresentation'

function routeLabel(task: string, text: (zh: string, en: string) => string) {
  if (task === 'lookup') return text('事实核对', 'Fact check')
  if (task === 'retrieve') return text('证据检索', 'Evidence search')
  return text('持续调查', 'Investigation')
}

function caseStateCopy(status: string, text: (zh: string, en: string) => string) {
  if (status === 'resolved') return { headline: text('调查已形成带引用的结论', 'Investigation resolved with cited findings'), label: text('已完成', 'Resolved') }
  if (status === 'active') return { headline: text('调查正在收集与核验证据', 'Investigation is collecting and checking evidence'), label: text('运行中', 'Active') }
  if (status === 'waiting') return { headline: text('调查正在等待证据或后续指令', 'Investigation is waiting for evidence or the next instruction'), label: text('等待中', 'Waiting') }
  if (status === 'created') return { headline: text('调查已创建，等待执行', 'Investigation created and awaiting execution'), label: text('已创建', 'Created') }
  if (status === 'closed') return { headline: text('调查已关闭', 'Investigation closed'), label: text('已关闭', 'Closed') }
  if (status === 'cancelled') return { headline: text('调查已取消', 'Investigation cancelled'), label: text('已取消', 'Cancelled') }
  return { headline: text('调查已停止，请查看执行轨迹', 'Investigation stopped; inspect the execution trace'), label: text('已停止', 'Stopped') }
}

function formatTime(value: string, language: string) {
  return new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
export function ConversationTurn({ turn, active, sessionId, reasoning, onSelect, onEvidence }: { turn: QuestionSessionTurn; active: boolean; sessionId: string; reasoning: string | null; onSelect: () => void; onEvidence: (ref: string) => void }) {
  const { text, language } = useI18n()
  const decision = useQuery({ queryKey: ['question-turn-decision', turn.decision_ref], queryFn: () => getDecision(turn.decision_ref!), enabled: Boolean(turn.decision_ref), retry: false })
  const caseId = turn.investigation_ref?.replace(/^case:/, '')
  const investigation = useQuery({ queryKey: ['question-turn-case', caseId], queryFn: () => getInvestigation(caseId!), enabled: Boolean(caseId), retry: false, refetchInterval: query => ['active', 'waiting'].includes(query.state.data?.status ?? '') ? 5000 : false })
  const caseState = caseStateCopy(investigation.data?.status ?? 'created', text)
  const unknownCount = investigation.data ? displayUnknowns(investigation.data).length : 0
  return <article className={`qa-turn ${active ? 'active' : ''}`}>
    <div className="qa-question"><small>{text('你', 'YOU')} / {formatTime(turn.created_at, language)}</small><p>{turn.question}</p></div>
    <div className="qa-answer"><div className="qa-answer-meta"><span><span className="qa-assistant-avatar"><ScanLine size={17} /></span>SecFusion <small>{routeLabel(turn.task_kind, text)}</small></span><button onClick={onSelect}><Workflow size={14} />{text('查看过程', 'View process')}<ChevronRight size={13} /></button></div>
      {decision.isLoading && turn.decision_ref && <p className="qa-muted">{text('正在恢复研判…', 'Restoring decision…')}</p>}
      {decision.isError && <button className="qa-retry" onClick={() => void decision.refetch()}>{text('研判读取失败 · 重试', 'Decision failed · Retry')}</button>}
      {decision.data && <DecisionReport decision={decision.data} onEvidence={onEvidence} dialogue />}
      {reasoning && <details className="qa-reasoning"><summary>{text('本次模型推理流 · 仅当前页面保留', 'Provider reasoning · available until reload')}</summary><pre>{reasoning}</pre></details>}
      {caseId && investigation.isLoading && <p className="qa-muted">{text('正在恢复调查状态…', 'Restoring investigation state…')}</p>}
      {caseId && investigation.isError && <button className="qa-retry" onClick={() => void investigation.refetch()}>{text('调查状态读取失败 · 重试', 'Investigation status failed · Retry')}</button>}
      {investigation.data && <div className={`qa-case-result state-${investigation.data.status}`}>
        <strong>{caseState.headline}</strong>
        {!turn.decision_ref && <p>{investigation.data.latest_decision ? text('本回合没有单独归档的报告。打开调查现场可查看当前进展。', 'This turn has no separately archived report. Open the case for current progress.') : investigation.data.goal}</p>}
        <div>
          <span>{caseState.label}</span>
          <span>{investigation.data.confirmed_findings.length} {text('已确认', 'confirmed')}</span>
          {unknownCount > 0 && <span>{unknownCount} {text('尚未确认', 'unknown')}</span>}
          {investigation.data.open_evidence_needs.length > 0 && <span>{investigation.data.open_evidence_needs.length} {text('待补证据', 'open needs')}</span>}
        </div>
        <Link to={`/investigations?case=${caseId}&session=${sessionId}`}>{text('打开完整调查现场', 'Open full investigation')}<ArrowUpRight size={13} /></Link>
      </div>}
      {!turn.decision_ref && !turn.investigation_ref && <p className="qa-muted">{text('本回合没有持久研判或调查引用。', 'No durable decision or case reference for this turn.')}</p>}
    </div>
  </article>
}
