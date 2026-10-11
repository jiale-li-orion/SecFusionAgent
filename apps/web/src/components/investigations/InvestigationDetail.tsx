import { useEffect, useState } from 'react'
import {
  ArrowUpRight,
  BadgeCheck,
  CircleAlert,
  FileQuestion,
  FileText,
  History,
  Link2,
  MessageSquare,
  OctagonX,
  SearchCheck,
  Workflow,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { InvestigationReport } from './InvestigationReport'
import {
  cancelInvestigation,
  type InvestigationFinding,
  type InvestigationView,
  type ProductRuntimeEvent,
} from '../../lib/api/investigations'
import {
  displayUnknowns,
  investigationStatusLabel,
  investigationStopMessage,
  runtimeActorLabel,
  runtimeEventSummary,
  type CaseStateFocus,
} from '../../lib/investigationPresentation'
import { useI18n } from '../../lib/i18n'

export function InvestigationDetail({
  investigation: item,
  sessionId,
  events,
  streamState,
  activityLoading,
  activityFailed,
  retryActivity,
  view,
  onView,
  focus,
  onFocus,
  onEvent,
  onEvidence,
  onChanged,
}: {
  investigation: InvestigationView
  sessionId: string | null
  events: ProductRuntimeEvent[]
  streamState: string
  activityLoading: boolean
  activityFailed: boolean
  retryActivity: () => void
  view: string
  onView: (view: string) => void
  focus: CaseStateFocus | null
  onFocus: (focus: CaseStateFocus) => void
  onEvent: (event: ProductRuntimeEvent) => void
  onEvidence: (ref: string) => void
  onChanged: () => void
}) {
  const { text, language } = useI18n()
  const [cancelBusy, setCancelBusy] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const unknowns = displayUnknowns(item)
  const busy = ['submitted', 'queued', 'running', 'waiting_dependency'].includes(item.current_activity.task_status ?? '')
  const active = ['created', 'active', 'waiting'].includes(item.status)
  const updated = new Date(item.updated_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const followUp = new URLSearchParams({ from: 'case', origin: `case:${item.case_id}`, originTitle: item.goal })
  if (sessionId) followUp.set('session', sessionId)
  else {
    if (item.target_object_ids[0]) followUp.set('object', item.target_object_ids[0])
    followUp.set('question', text(`继续调查：${item.goal}`, `Follow up on: ${item.goal}`))
  }
  useEffect(() => {
    if (view !== 'findings' || !focus) return
    const frame = requestAnimationFrame(() => document.getElementById(`research-${focus}`)?.scrollIntoView({ block: 'start' }))
    return () => cancelAnimationFrame(frame)
  }, [view, focus])
  async function cancel() {
    if (cancelBusy || !item.can_cancel) return
    setCancelBusy(true)
    setCancelError('')
    try {
      await cancelInvestigation(item.case_id, item.revision)
      onChanged()
    } catch (error) {
      setCancelError(error instanceof Error ? error.message : text('取消失败，请重试。', 'Cancellation failed. Please retry.'))
    } finally {
      setCancelBusy(false)
    }
  }
  const groups: Array<{ id: CaseStateFocus; label: string; items: InvestigationFinding[]; icon: typeof BadgeCheck; empty: string }> = [
    {
      id: 'confirmed',
      label: text('已确认的发现', 'Confirmed findings'),
      items: item.confirmed_findings,
      icon: BadgeCheck,
      empty: text('暂时没有已确认的发现。', 'No confirmed findings yet.'),
    },
    {
      id: 'conflicts',
      label: text('来源之间的分歧', 'Conflicting sources'),
      items: item.conflicts,
      icon: CircleAlert,
      empty: text('当前没有记录来源冲突。', 'No source conflicts recorded.'),
    },
    {
      id: 'unknowns',
      label: text('还不能确定的事', 'Open questions'),
      items: unknowns,
      icon: FileQuestion,
      empty: text('当前没有记录未决问题。', 'No open questions recorded.'),
    },
  ]
  return (
    <div className="research-detail">
      <header className="research-detail-heading">
        <div className="research-detail-meta">
          <Badge variant="secondary" className={`research-status status-${item.status}`}>
            {investigationStatusLabel(item.status, text)}
          </Badge>
          <span>
            {text('更新于', 'Updated')} {updated}
          </span>
        </div>
        <h1>{item.goal}</h1>
        <div className="research-detail-actions">
          <Button asChild>
            <Link to={`/start?${followUp}`}>
              <MessageSquare size={16} />
              {busy ? text('查看对话', 'Open conversation') : text('继续追问', 'Continue in chat')}
            </Link>
          </Button>
          {item.can_cancel && (
            <Button variant="ghost" className="research-cancel" disabled={cancelBusy} onClick={() => void cancel()}>
              <OctagonX size={15} />
              {cancelBusy ? text('正在取消…', 'Cancelling…') : text('停止调查', 'Stop investigation')}
            </Button>
          )}
          <span className="research-saved">
            <History size={14} />
            {text('证据与进展已保存', 'Evidence and progress retained')}
          </span>
        </div>
      </header>
      {cancelError && (
        <p className="research-notice" role="alert">
          {cancelError}
        </p>
      )}
      {item.status === 'failed' && (
        <div className="research-notice" role="status">
          <CircleAlert size={18} />
          <span>{investigationStopMessage(item.terminal_reason ?? '', text)}</span>
          <Button variant="outline" size="sm" onClick={() => onView('activity')}>
            {text('查看原因', 'View details')}
          </Button>
        </div>
      )}
      {item.status === 'waiting' && (
        <div className="research-notice">
          <History size={18} />
          <span>
            {item.current_activity.task_status === 'waiting_input'
              ? text('调查需要更多信息，你可以在原会话中补充。', 'More information is needed. Add it in the original conversation.')
              : text('正在等待证据或相关任务，进展会自动更新。', 'Waiting for evidence or related tasks. Progress updates automatically.')}
          </span>
        </div>
      )}
      <Tabs value={view} onValueChange={onView} className="research-detail-tabs">
        <TabsList variant="line" aria-label={text('调查内容', 'Investigation views')}>
          <TabsTrigger value="report">
            <FileText size={16} />
            {text('调查报告', 'Report')}
          </TabsTrigger>
          <TabsTrigger value="findings">
            <SearchCheck size={16} />
            {text('发现与待办', 'Findings & needs')}
            <span className="research-tab-count">
              {item.confirmed_findings.length + item.conflicts.length + unknowns.length + item.open_evidence_needs.length}
            </span>
          </TabsTrigger>
          <TabsTrigger value="activity">
            <Workflow size={16} />
            {text('执行过程', 'Activity')}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="report">
          {item.latest_decision ? (
            <InvestigationReport investigation={item} onEvidence={onEvidence} />
          ) : (
            <div className="research-report-pending">
              <FileText size={30} />
              <h2>{active ? text('报告正在形成', 'Building the report') : text('这次调查尚未形成报告', 'No report was produced')}</h2>
              <p>
                {active
                  ? text(
                      '调查会先收集并核验证据；已有发现可以随时查看。',
                      'Evidence is being collected and checked. You can read the available findings now.',
                    )
                  : text(
                      '已有发现和执行记录仍然保留，你可以补充线索后继续探索。',
                      'Findings and execution history are retained. Add a lead to continue exploring.',
                    )}
              </p>
              <Button variant="outline" onClick={() => onFocus('confirmed')}>
                {text('查看已有发现', 'Read findings')}
                <ArrowUpRight size={15} />
              </Button>
            </div>
          )}
        </TabsContent>
        <TabsContent value="findings">
          <div className="research-findings">
            <nav className="research-finding-jump" aria-label={text('发现分类', 'Finding categories')}>
              {groups.map((group) => (
                <Button key={group.id} variant="ghost" size="sm" onClick={() => onFocus(group.id)}>
                  {group.label}
                  <span>{group.items.length}</span>
                </Button>
              ))}
              <Button variant="ghost" size="sm" onClick={() => onFocus('needs')}>
                {text('待补证据', 'Evidence needs')}
                <span>{item.open_evidence_needs.length}</span>
              </Button>
            </nav>
            {groups.map(({ id, label, items, icon: Icon, empty }) => (
              <section key={id} id={`research-${id}`} className={`research-finding-group group-${id} ${focus === id ? 'is-focused' : ''}`}>
                <header>
                  <Icon size={19} />
                  <h2>{label}</h2>
                  <span>{items.length}</span>
                </header>
                {items.length ? (
                  items.map((finding, index) => (
                    <article key={`${finding.proposition}:${index}`}>
                      <p>{finding.proposition}</p>
                      <FindingEvidence refs={finding.evidence_refs} onEvidence={onEvidence} />
                    </article>
                  ))
                ) : (
                  <p className="research-muted">{empty}</p>
                )}
              </section>
            ))}
            <section id="research-needs" className={`research-finding-group ${focus === 'needs' ? 'is-focused' : ''}`}>
              <header>
                <SearchCheck size={19} />
                <h2>{text('下一步需要的证据', 'Evidence still needed')}</h2>
                <span>{item.open_evidence_needs.length}</span>
              </header>
              {item.open_evidence_needs.length ? (
                item.open_evidence_needs.map((need) => (
                  <article key={need.need_id}>
                    <p>{need.question}</p>
                    <small>{need.purpose}</small>
                    <details>
                      <summary>{text('证据要求', 'Evidence requirements')}</summary>
                      <p>{need.required_source_roles.join(' · ') || '—'}</p>
                      <small>
                        {text('优先级', 'Priority')} {need.priority} · {need.status}
                      </small>
                    </details>
                  </article>
                ))
              ) : (
                <p className="research-muted">{text('当前没有开放的补证需求。', 'No open evidence requests.')}</p>
              )}
            </section>
          </div>
        </TabsContent>
        <TabsContent value="activity">
          <div className="research-activity">
            <header className="research-activity-heading">
              <div>
                <h2>{text('调查是怎样推进的', 'How the investigation progressed')}</h2>
                <p>{text('沿时间查看真实的任务、发现和证据变化。', 'Follow the actual tasks, findings and evidence changes over time.')}</p>
              </div>
              <span className={`research-stream stream-${streamState}`}>
                <i />
                {streamState === 'live'
                  ? text('已连接', 'Connected')
                  : streamState === 'retrying'
                    ? text('正在重连', 'Reconnecting')
                    : text('连接中', 'Connecting')}
              </span>
            </header>
            {activityFailed && (
              <div className="research-notice" role="alert">
                <span>
                  {text('历史事件读取失败，当前过程可能不完整。', 'Event history could not be loaded. This view may be incomplete.')}
                </span>
                <Button variant="outline" size="sm" onClick={retryActivity}>
                  {text('重试', 'Retry')}
                </Button>
              </div>
            )}
            {activityLoading && (
              <p className="research-muted" role="status">
                {text('正在读取执行记录…', 'Loading execution history…')}
              </p>
            )}
            {!events.length && !activityLoading && (
              <p className="research-muted">{text('当前还没有执行记录。', 'No execution records yet.')}</p>
            )}
            <ol className="research-timeline">
              {events.map((event) => (
                <li key={event.event_id}>
                  <span className={`research-event-dot event-${event.event_type}`} />
                  <div className="research-event">
                    <div className="research-event-meta">
                      <span>{runtimeActorLabel(event.role_id ?? event.actor, text)}</span>
                      <time dateTime={event.occurred_at}>
                        {new Date(event.occurred_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </time>
                    </div>
                    <p>{runtimeEventSummary(event, text)}</p>
                    <div className="research-event-actions">
                      {[
                        'finding_added',
                        'finding_changed',
                        'conflict_changed',
                        'unknown_changed',
                        'evidence_need_changed',
                        'decision_ready',
                        'completed',
                      ].includes(event.event_type) && (
                        <Button variant="ghost" size="sm" onClick={() => onEvent(event)}>
                          {text('查看对应内容', 'Related findings')}
                          <ArrowUpRight size={13} />
                        </Button>
                      )}
                      {event.task_run_id && (
                        <Button asChild variant="ghost" size="sm">
                          <Link to={`/agents?${new URLSearchParams({ run: event.task_run_id, from: 'case', caseRef: item.case_id })}`}>
                            {text('任务详情', 'Task details')}
                            <ArrowUpRight size={13} />
                          </Link>
                        </Button>
                      )}
                    </div>
                    <FindingEvidence refs={event.evidence_refs} onEvidence={onEvidence} />
                    <details>
                      <summary>{text('事件详情', 'Event details')}</summary>
                      <code>
                        {event.technical_type} · {event.event_id}
                      </code>
                    </details>
                  </div>
                </li>
              ))}
            </ol>
            <details className="research-coordinates">
              <summary>{text('调查标识与运行信息', 'Investigation and runtime details')}</summary>
              <dl>
                <dt>Case</dt>
                <dd>{item.case_id}</dd>
                <dt>{text('版本', 'Revision')}</dt>
                <dd>{item.revision}</dd>
                <dt>{text('运行状态', 'Task state')}</dt>
                <dd>{item.current_activity.task_status ?? '—'}</dd>
                <dt>{text('终止原因', 'Stop reason')}</dt>
                <dd>{item.terminal_reason ?? '—'}</dd>
              </dl>
            </details>
          </div>
        </TabsContent>
      </Tabs>
      {item.target_object_ids.length > 0 && (
        <details className="research-targets">
          <summary>{text(`相关对象 · ${item.target_object_ids.length}`, `Related objects · ${item.target_object_ids.length}`)}</summary>
          {item.target_object_ids.map((id, index) => (
            <Button asChild variant="outline" size="sm" key={id}>
              <Link to={`/intelligence?${new URLSearchParams({ object: id, from: 'case', caseRef: item.case_id })}`} title={id}>
                {text(`对象档案 ${index + 1}`, `Object ${index + 1}`)}
                <ArrowUpRight size={14} />
              </Link>
            </Button>
          ))}
        </details>
      )}
    </div>
  )
}

function FindingEvidence({ refs, onEvidence }: { refs: string[]; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const unique = [...new Set(refs)]
  return (
    unique.length > 0 && (
      <div className="research-evidence-links">
        {(expanded ? unique : unique.slice(0, 3)).map((ref, index) => (
          <Button variant="outline" size="sm" key={ref} onClick={() => onEvidence(ref)} title={ref}>
            <Link2 size={12} />
            {text('证据', 'Evidence')} {index + 1}
          </Button>
        ))}
        {unique.length > 3 && (
          <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
            {expanded ? text('收起', 'Show less') : text(`其余 ${unique.length - 3} 条`, `${unique.length - 3} more`)}
          </Button>
        )}
      </div>
    )
  )
}
