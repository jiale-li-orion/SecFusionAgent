import { RoleSigil } from '../instrument/RoleSigil'
import { ProductGlyph } from '../instrument/ProductGlyph'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'motion/react'
import { Activity, BadgeCheck, BrainCircuit, CircleAlert, CircleDot, FileWarning, Link2, MessageSquareText, OctagonX, Orbit, SearchCheck, Sparkles, TerminalSquare } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { askQuestion, cancelInvestigation, evidenceBoundObjectIds, getEvidence, type EvidenceDetail, type InvestigationFinding, type InvestigationView, type ProductRuntimeEvent, type QuestionResult, type TaskKind } from '../../lib/api'
import { displayUnknowns, eventState, investigationStopMessage, runtimeActorLabel, runtimeEventSummary, runtimeTaskLabel, type CaseStateFocus, type EventCue } from '../../lib/investigationPresentation'
import { formatValue } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { DecisionReport } from '../DecisionReport'
import { InvestigationReport } from './InvestigationReport'
import { SessionHistory } from '../SessionHistory'

const liveStatuses = new Set(['active', 'waiting'])
const busyEpisodeStatuses = new Set(['submitted', 'queued', 'running', 'waiting_input', 'waiting_dependency'])

export function CaseWorkspace({ investigation, events, eventCue, initialFocus, onEvidence, sessionId, reduceMotion, onFollowUpComplete }: { investigation: InvestigationView; events: ProductRuntimeEvent[]; eventCue: EventCue | null; initialFocus: CaseStateFocus | null; onEvidence: (ref: string) => void; sessionId: string | null; reduceMotion: boolean; onFollowUpComplete: () => void }) {
  const { text } = useI18n()
  const visibleUnknowns = displayUnknowns(investigation)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [followUp, setFollowUp] = useState('')
  const [followUpError, setFollowUpError] = useState('')
  const [targetsExpanded, setTargetsExpanded] = useState(false)
  const [conversationMount, setConversationMount] = useState<HTMLElement | null>(null)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setConversationMount(document.getElementById('case-conversation-mount')))
    return () => cancelAnimationFrame(frame)
  }, [investigation.case_id])
  const [followUpBusy, setFollowUpBusy] = useState(false)
  const [sessionTurns, setSessionTurns] = useState<Array<{ kind: 'user' | 'system'; text: string; result?: QuestionResult }>>([])
  const [cancelBusy, setCancelBusy] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const cueId = eventCue?.eventId ?? null
  const [focusSelection, setFocusSelection] = useState<{ cueId: string | null; state: CaseStateFocus | null }>({ cueId, state: initialFocus })
  const stateFocus = focusSelection.cueId === cueId ? focusSelection.state : eventCue?.state ?? focusSelection.state
  const toggleFocus = (state: CaseStateFocus) => setFocusSelection({ cueId, state: stateFocus === state ? null : state })

  const latestTaskRunId = [...events].reverse().find((event) => event.task_run_id)?.task_run_id ?? null
  const continuationKind = continuationTaskKind(investigation.current_activity.task_kind, investigation.execution_profile)
  const waitingForInput = investigation.current_activity.task_status === 'waiting_input' || investigation.terminal_reason === 'decision_requires_continuation'
  const episodeBusy = busyEpisodeStatuses.has(investigation.current_activity.task_status ?? '')
  const continuesSameCase = liveStatuses.has(investigation.case_lifecycle ?? investigation.status) && !episodeBusy
  const canSubmitFollowUp = Boolean(sessionId && !episodeBusy)

  async function sendFollowUp() {
    const question = followUp.trim()
    if (!question || !sessionId || episodeBusy || followUpBusy) return
    setFollowUpBusy(true)
    setFollowUpError('')
    try {
      const result = await askQuestion({ question, sessionId, taskKind: continuationKind })
      setSessionTurns((current) => [...current, { kind: 'user', text: question }, { kind: 'system', text: result.mode === 'completed' ? text('研判已生成', 'DECISION READY') : followUpNarrative(result, text), result }])
      setFollowUp('')
      void queryClient.invalidateQueries({ queryKey: ['question-session', sessionId] })
      onFollowUpComplete()
      if (result.mode === 'accepted' && result.investigation?.case_id && result.investigation.case_id !== investigation.case_id) {
        navigate(`/investigations?${new URLSearchParams({ case: result.investigation.case_id, session: result.session_id, from: 'case' })}`)
      }
    } catch (error) {
      setFollowUpError(error instanceof Error ? error.message : text('后续追问失败', 'Follow-up failed'))
    } finally {
      setFollowUpBusy(false)
    }
  }
  async function cancelCase() {
    if (cancelBusy || !investigation.can_cancel) return
    setCancelBusy(true)
    setCancelError('')
    try {
      await cancelInvestigation(investigation.case_id, investigation.revision)
      onFollowUpComplete()
    } catch (error) {
      setCancelError(error instanceof Error ? error.message : text('取消调查 失败', 'Cancel failed'))
    } finally {
      setCancelBusy(false)
    }
  }

  const conversation = (
      <section className="conversation-shell">
        <div className="conversation-title"><MessageSquareText size={15} /><div><small>{text('持续交互', 'CONTINUOUS INTERACTION')}</small><strong>{text('调查会话', 'INVESTIGATION SESSION')}</strong></div><span>{sessionId ? text('保留当前调查上下文', 'CONTEXT RETAINED') : text('该历史 Case 没有 Product session', 'NO PRODUCT SESSION FOR THIS HISTORICAL CASE')}</span></div>
        <div className="conversation-preview">
          {sessionId && <SessionHistory sessionId={sessionId} />}
          <div className="system-message"><ProductGlyph kind="agents" size={18} /><ProgressiveReveal text={latestNarrative(events, text)} /></div>
          {sessionTurns.map((turn, index) => <motion.div key={`${turn.kind}:${index}`} className={`session-turn turn-${turn.kind}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}><small>{turn.kind === 'user' ? 'YOU' : 'SECFUSION'}</small><p>{turn.text}</p>{turn.result?.decision && <DecisionReport decision={turn.result.decision} onEvidence={onEvidence} />}</motion.div>)}
          <div id="case-session-composer" className={`case-session-composer ${sessionId ? 'enabled' : 'disabled'}`}>
            <div className="case-injection-coordinate">
              <span className="case-injection-glyph"><TerminalSquare size={13} /></span>
              <div>
                <small>{text(continuesSameCase ? '继续当前调查' : '发起后续调查', continuesSameCase ? 'CONTINUE THIS INVESTIGATION' : 'START A FOLLOW-UP INVESTIGATION')}</small>
                <strong>{text('下一轮调查', 'Next investigation')} · {runtimeTaskLabel(continuationKind, text)}</strong>
              </div>
              <em>{sessionId ? text('会话上下文已保留', 'session context retained') : text('历史 Case 未绑定会话', 'historical case has no session')}</em>
            </div>
            <div className="case-injection-channel" aria-hidden="true"><i /><span>{text(continuesSameCase ? '继续写入同一 Case' : '继承目标与历史，创建后续 Case', continuesSameCase ? 'CONTINUE THE SAME CASE' : 'CARRY CONTEXT INTO A FOLLOW-UP CASE')}</span><i /></div>
            <div className="case-injection-input">
              <textarea id="case-followup-input" rows={4} aria-describedby={`case-injection-contract${followUpError ? ' case-followup-error' : ''}`} value={followUp} onChange={(event) => { setFollowUp(event.target.value); if (followUpError) setFollowUpError('') }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void sendFollowUp() } }} disabled={!canSubmitFollowUp || followUpBusy} placeholder={sessionId ? episodeBusy ? text('当前运行回合结束后可追加下一步调查意图', 'Wait for the current runtime episode before adding the next intent') : text('补充信息，或提出下一步调查问题…', 'Inject the next investigation intent…') : text('该历史 Case 没有会话；可从下方重新发起', 'This historical Case has no session; start a follow-up below')} />
              {sessionId ? <button onClick={() => void sendFollowUp()} disabled={!canSubmitFollowUp || !followUp.trim() || followUpBusy}>{followUpBusy ? text('提交中…', 'ADMITTING…') : text(continuesSameCase ? '继续调查' : '发起后续调查', continuesSameCase ? 'CONTINUE INVESTIGATION' : 'START FOLLOW-UP')}</button> : <button onClick={() => {
                const target = investigation.target_object_ids[0]
                const query = new URLSearchParams({ profile: investigation.execution_profile ?? 'INVESTIGATE', from: 'case', origin: `case:${investigation.case_id}` })
                if (target) query.set('object', target)
                query.set('question', text(`继续调查：${investigation.goal}`, `Follow up on: ${investigation.goal}`))
                navigate(`/start?${query.toString()}`)
              }}>{text('围绕当前目标发起新调查', 'START FROM THIS CASE TARGET')}</button>}
            </div>
            {followUpError && <p id="case-followup-error" className="conversation-error" role="alert">{text('提交失败，问题已保留，可重试：', 'Submission failed. Your question is retained for retry: ')}{followUpError}</p>}
            <small id="case-injection-contract" className="case-injection-contract">{episodeBusy
              ? text('当前 InvestigationRole 仍有一个未结束的运行回合。为了避免并发修改同一 Case，系统会等它结束后再接受新的调查回合。', 'An InvestigationRole episode is still active. To avoid concurrent mutation of the same Case, a new investigation episode is admitted only after the current one ends.')
              : text(continuesSameCase ? '这次追问会继续写入当前 durable Case，并保留既有目标、证据和状态。' : '当前 Case 已经结束；追问会沿同一 session 保留目标和历史，并建立新的 follow-up Case。', continuesSameCase ? 'This follow-up continues the current durable Case while preserving its targets, evidence, and state.' : 'This Case is terminal; a follow-up retains session targets and history, then opens a new follow-up Case.')}</small>
          </div>
        </div>
      </section>
  )

  return (
    <div className="case-workspace-stack">
      <article className="case-hero">
        <div className="case-hero-main">
          <span className="case-hero-sigil"><ProductGlyph kind="investigations" size={33} /></span>
          <div>
            <small>{investigation.execution_profile ?? 'RUNTIME'} · {investigation.origin_scope.toUpperCase()}</small>
            <strong>{investigation.goal}</strong>
            <p>{text(`${investigation.confirmed_findings.length} 条确认事实 · ${investigation.conflicts.length} 条来源冲突 · ${visibleUnknowns.length} 个未决问题 · ${investigation.open_evidence_needs.length} 个证据缺口`, `${investigation.confirmed_findings.length} findings · ${investigation.conflicts.length} conflicts · ${visibleUnknowns.length} unknowns · ${investigation.open_evidence_needs.length} evidence needs`)}</p>
            <details className="case-technical-coordinate"><summary>{text('技术坐标', 'TECHNICAL COORDINATE')}</summary><span className="mono">CASE {investigation.case_id}</span><span>REV {investigation.revision}</span></details>
          </div>
        </div>
        <div className="case-hero-state"><span className={`case-state-badge state-${investigation.status}`}>{investigation.status}</span>{investigation.can_cancel && <button className="case-cancel-button" onClick={() => void cancelCase()} disabled={cancelBusy}><OctagonX size={12} /> {cancelBusy ? text('取消中…', 'CANCELLING…') : text('取消调查', 'CANCEL CASE')}</button>}{cancelError && <em className="case-cancel-error">{cancelError}</em>}</div>
      </article>
      {investigation.target_object_ids.length > 0 && (
        <div className="case-target-strip">
          <small>{text('调查目标', 'CASE TARGETS')}</small>
          <div>{(targetsExpanded ? investigation.target_object_ids : investigation.target_object_ids.slice(0, 6)).map((objectId) => <button key={objectId} onClick={() => {
            const query = new URLSearchParams({ object: objectId, from: 'case', caseRef: investigation.case_id })
            navigate(`/intelligence?${query.toString()}`)
          }}><BrainCircuit size={11} /><span>{text('打开对象档案', 'OPEN OBJECT DOSSIER')}</span><b className="mono">{compactEvidenceObjectRef(objectId)}</b></button>)}{investigation.target_object_ids.length > 6 && <button className="case-target-expand" type="button" aria-expanded={targetsExpanded} onClick={() => setTargetsExpanded(value => !value)}>{targetsExpanded ? text('收起目标', 'Show fewer targets') : text(`查看其余 ${investigation.target_object_ids.length - 6} 个目标`, `View ${investigation.target_object_ids.length - 6} more targets`)}</button>}</div>
        </div>
      )}

      {investigation.status === 'failed' && investigation.terminal_reason && (
        <motion.section
          className="case-terminal"
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <TerminalSquare size={16} />
          <div>
            <small>{text('本轮运行已停止', 'EPISODE STOPPED')}</small>
            <strong>{investigationStopMessage(investigation.terminal_reason, text)}</strong>
            <details><summary>{text('查看原因代码', 'Reason code')}</summary><code>{investigation.terminal_reason}</code></details>
          </div>
          {latestTaskRunId && (
            <button onClick={() => {
              const query = new URLSearchParams({ run: latestTaskRunId, from: 'case', caseRef: investigation.case_id })
              navigate(`/agents?${query.toString()}`)
            }}>
              {text('查看执行记录', 'OPEN TASK TRACE')}
            </button>
          )}
        </motion.section>
      )}

      {investigation.status === 'waiting' && (
        <section className={`case-wait-boundary status-${investigation.current_activity.task_status ?? 'waiting'}`}>
          <span className="case-wait-glyph"><CircleDot size={14} /></span>
          <div>
            <small>{waitingForInput ? text('等待补充信息或证据', 'WAITING FOR INFORMATION OR EVIDENCE') : text('等待依赖变化', 'WAITING FOR DEPENDENCY')}</small>
            <strong>{waitingForInput
              ? text('补充信息或调整问题，继续当前调查。', 'Add information or refine your question to continue this investigation.')
              : text('正在等待相关证据或子任务完成，进展会自动更新。', 'Waiting for evidence or related tasks. Progress updates automatically.')}</strong>
          </div>
          <div className="case-wait-actions">
            {waitingForInput && sessionId && <button onClick={() => document.getElementById('case-session-composer')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>{text('继续当前 Case', 'CONTINUE CASE')}</button>}
            {investigation.current_activity.task_status === 'waiting_dependency' && latestTaskRunId && <button onClick={() => navigate(`/agents?run=${encodeURIComponent(latestTaskRunId)}&from=case&caseRef=${encodeURIComponent(investigation.case_id)}`)}>{text('查看等待边界', 'OPEN WAIT BOUNDARY')}</button>}
          </div>
        </section>
      )}


      <motion.div
        key={`decision:${eventCue?.state === 'decision' ? eventCue.eventId : 'stable'}`}
        className={`decision-focus-wrap ${stateFocus === 'decision' ? 'state-focused' : stateFocus ? 'state-dimmed' : ''} ${eventCue?.state === 'decision' ? 'state-forged' : ''}`}
        initial={eventCue?.state === 'decision' && !reduceMotion ? { opacity: .35, scale: .985 } : false}
        animate={{ opacity: stateFocus && stateFocus !== 'decision' ? .78 : 1, scale: 1 }}
        transition={{ duration: reduceMotion ? 0 : .28 }}
        role="button"
        tabIndex={0}
        aria-pressed={stateFocus === 'decision'}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest('button,a,summary')) return
          toggleFocus('decision')
        }}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            toggleFocus('decision')
          }
        }}
      >
        <DecisionPanel investigation={investigation} onEvidence={onEvidence} />
      </motion.div>

      <div className={`case-state-grid ${stateFocus ? `has-state-focus focus-${stateFocus}` : ''}`}>
        <StateColumn key={`confirmed:${eventCue?.state === 'confirmed' ? eventCue.eventId : 'stable'}`} title={text('已确认', 'CONFIRMED')} tone="lime" icon={BadgeCheck} items={investigation.confirmed_findings} onEvidence={onEvidence} active={stateFocus === 'confirmed'} dimmed={Boolean(stateFocus && stateFocus !== 'confirmed')} forged={eventCue?.state === 'confirmed'} reduceMotion={reduceMotion} onFocus={() => toggleFocus('confirmed')} />
        <StateColumn key={`conflicts:${eventCue?.state === 'conflicts' ? eventCue.eventId : 'stable'}`} title={text('冲突', 'CONFLICTS')} tone="amber" icon={CircleAlert} items={investigation.conflicts} onEvidence={onEvidence} active={stateFocus === 'conflicts'} dimmed={Boolean(stateFocus && stateFocus !== 'conflicts')} forged={eventCue?.state === 'conflicts'} reduceMotion={reduceMotion} onFocus={() => toggleFocus('conflicts')} />
        <StateColumn key={`unknowns:${eventCue?.state === 'unknowns' ? eventCue.eventId : 'stable'}`} title={text('未知', 'UNKNOWNS')} tone="violet" icon={FileWarning} items={visibleUnknowns} onEvidence={onEvidence} active={stateFocus === 'unknowns'} dimmed={Boolean(stateFocus && stateFocus !== 'unknowns')} forged={eventCue?.state === 'unknowns'} reduceMotion={reduceMotion} onFocus={() => toggleFocus('unknowns')} />
        <EvidenceNeeds key={`needs:${eventCue?.state === 'needs' ? eventCue.eventId : 'stable'}`} investigation={investigation} active={stateFocus === 'needs'} dimmed={Boolean(stateFocus && stateFocus !== 'needs')} forged={eventCue?.state === 'needs'} reduceMotion={reduceMotion} onFocus={() => toggleFocus('needs')} />
      </div>

      {conversationMount ? createPortal(conversation, conversationMount) : conversation}

    </div>
  )
}

function StateColumn({ title, tone, icon: Icon, items, onEvidence, active, dimmed, forged, reduceMotion, onFocus }: { title: string; tone: string; icon: typeof BadgeCheck; items: InvestigationFinding[]; onEvidence: (ref: string) => void; active: boolean; dimmed: boolean; forged: boolean; reduceMotion: boolean; onFocus: () => void }) {
  const { text } = useI18n()
  const [expanded, setExpanded] = useState(false)
  return (
    <motion.section
      className={`state-column tone-${tone} ${active ? 'state-focused' : ''} ${dimmed ? 'state-dimmed' : ''} ${forged ? 'state-forged' : ''}`}
      initial={forged && !reduceMotion ? { opacity: .38, y: 7, scale: .985 } : false}
      animate={{ opacity: dimmed ? .78 : 1, y: 0, scale: 1 }}
      transition={{ duration: reduceMotion ? 0 : .28, ease: [0.22, 1, 0.36, 1] }}
    >
      <button type="button" className="state-column-head" onClick={onFocus}><Icon size={14} /><strong>{title}</strong><span>{items.length}</span></button>
      <div className="state-items">
        {(expanded ? items : items.slice(0, 8)).map((item, index) => (
          <motion.article key={`${item.proposition}:${index}`} className="state-item" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <strong>{item.proposition}</strong>
            <EvidenceButtons refs={item.evidence_refs} onEvidence={onEvidence} />
          </motion.article>
        ))}
        {items.length === 0 && <div className="state-empty">{text('当前没有条目。', 'No current items.')}</div>}
        {items.length > 8 && <button type="button" className="state-show-more" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? text('收起条目', 'Show fewer') : text(`查看其余 ${items.length - 8} 条`, `View ${items.length - 8} more`)}</button>}
      </div>
    </motion.section>
  )
}

function EvidenceNeeds({ investigation, active, dimmed, forged, reduceMotion, onFocus }: { investigation: InvestigationView; active: boolean; dimmed: boolean; forged: boolean; reduceMotion: boolean; onFocus: () => void }) {
  const { text } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const needs = investigation.open_evidence_needs
  return (
    <motion.section className={`state-column tone-cyan ${active ? 'state-focused' : ''} ${dimmed ? 'state-dimmed' : ''} ${forged ? 'state-forged' : ''}`} initial={forged && !reduceMotion ? { opacity: .38, y: 7 } : false} animate={{ opacity: dimmed ? .78 : 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .28 }}>
      <button type="button" className="state-column-head" onClick={onFocus}><SearchCheck size={14} /><strong>{text('证据缺口', 'EVIDENCE NEEDS')}</strong><span>{investigation.open_evidence_needs.length}</span></button>
      <div className="state-items">
        {(expanded ? needs : needs.slice(0, 8)).map((need) => (
          <article key={need.need_id} className="state-item evidence-need-item">
            <strong>{need.question}</strong><small>{need.purpose} · priority {need.priority}</small>
            <div className="need-roles">{need.required_source_roles.map((role) => <span key={role}>{role}</span>)}</div>
          </article>
        ))}
        {needs.length === 0 && <div className="state-empty">{text('当前没有开放的证据缺口。', 'No open evidence gaps.')}</div>}
        {needs.length > 8 && <button type="button" className="state-show-more" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? text('收起缺口', 'Show fewer') : text(`查看其余 ${needs.length - 8} 个缺口`, `View ${needs.length - 8} more needs`)}</button>}
      </div>
    </motion.section>
  )
}

function DecisionPanel({ investigation, onEvidence }: { investigation: InvestigationView; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const decision = investigation.latest_decision
  return (
    <section className={`decision-panel ${decision ? 'ready' : ''}`}>
      <div className="decision-oracle"><RoleSigil role="DecisionRole" live={false}/><div><small>ORACLE / DECISION</small><strong>{decision ? text('研判已生成', 'DECISION READY') : liveStatuses.has(investigation.status) ? text('研判尚未生成', 'Decision pending') : text('本次调查未生成研判', 'No decision from this investigation')}</strong></div></div>
      {decision ? (
        <div className="decision-content">
          <InvestigationReport investigation={investigation} onEvidence={onEvidence} />
        </div>
      ) : <p className="decision-waiting">{liveStatuses.has(investigation.status) ? text('查看当前进展和证据缺口；运行结束后可补充信息，继续调查。', 'Review progress and evidence needs. Add information after the current episode to continue.') : text('本次运行已经结束。可查看终止原因，或保留已有上下文继续调查。', 'This run has ended. Inspect its stop reason or start a follow-up with the retained context.')}</p>}
    </section>
  )
}

export function RuntimeEventRail({ events, limit, activeEventId, onFocus, onEvidence }: { events: ProductRuntimeEvent[]; limit: number; activeEventId: string | null; onFocus: (event: ProductRuntimeEvent) => void; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const visible = events.slice(-limit).reverse()
  return <div className="runtime-event-list">{visible.map((event, index) => <motion.div key={event.event_id} className="runtime-event-entry" initial={{ opacity: 0, x: 18, scale: .98 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={{ delay: Math.min(index * .015, .18) }}><button type="button" onClick={() => onFocus(event)} className={`runtime-event event-${event.event_type} ${activeEventId === event.event_id ? 'event-focused' : ''} ${eventState(event.event_type) ? 'event-actionable' : ''}`}><span className="event-symbol"><EventIcon type={event.event_type} /></span><div><small>{event.role_id ? runtimeActorLabel(event.role_id, text) : event.actor ?? event.source_kind}</small><strong>{runtimeEventSummary(event, text)}</strong><em>{event.technical_type} · {new Date(event.occurred_at).toLocaleTimeString()}</em>{event.evidence_refs.length > 0 && <span className="event-evidence">{text(`${event.evidence_refs.length} 条证据引用`, `${event.evidence_refs.length} evidence refs`)}</span>}</div></button>{(event.task_run_id || event.evidence_refs.length > 0) && <div className="runtime-event-actions">{event.task_run_id && <Link to={`/agents?${new URLSearchParams({ run: event.task_run_id, from: 'case', caseRef: event.case_id })}`}><TerminalSquare size={11}/>{text('查看任务轨迹', 'Open task trace')}</Link>}{event.evidence_refs.length > 0 && <EvidenceButtons refs={event.evidence_refs} onEvidence={onEvidence} />}</div>}</motion.div>)}</div>
}

function EvidenceButtons({ refs, onEvidence }: { refs: string[]; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const [expanded, setExpanded] = useState(false)
  if (!refs.length) return null
  return <div className="finding-evidence">{(expanded ? refs : refs.slice(0, 3)).map((ref, index) => <button key={ref} onClick={() => onEvidence(ref)} title={ref}><Link2 size={10} /> {text('证据', 'EVIDENCE')} {index + 1}</button>)}{refs.length > 3 && <button type="button" className="evidence-expand" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>{expanded ? text('收起', 'Show less') : text(`查看其余 ${refs.length - 3} 条`, `View ${refs.length - 3} more`)}</button>}</div>
}

export function EvidenceOverlay({ evidenceRef, onClose }: { evidenceRef: string; onClose: () => void }) {
  const { text } = useI18n()
  const reduceMotion = Boolean(useReducedMotion())
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose }, [onClose])
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const handleKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onCloseRef.current() } }
    document.addEventListener('keydown', handleKey)
    return () => { document.removeEventListener('keydown', handleKey); previous?.focus() }
  }, [])
  const query = useQuery({ queryKey: ['evidence-overlay', evidenceRef], queryFn: () => getEvidence(evidenceRef) })
  const item = query.data
  return createPortal(
    <motion.aside
      className="investigation-evidence-lens"
      role="dialog"
      aria-label={text('证据查看', 'Evidence inspector')}
      initial={reduceMotion ? false : { opacity: 0, x: 36, clipPath: 'inset(0 0 0 18%)' }}
      animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
      exit={reduceMotion ? undefined : { opacity: 0, x: 28, clipPath: 'inset(0 0 0 14%)' }}
      transition={{ type: 'spring', stiffness: 250, damping: 28 }}
    >
      <div className="overlay-head">
        <div><small>EVIDENCE TRACE</small><strong>{item?.source.source_id ?? text('解析中…', 'Resolving…')}</strong><span className="mono">{evidenceRef}</span></div>
        <button ref={closeRef} onClick={onClose}>{text('关闭', 'CLOSE')}</button>
      </div>
      {item ? <EvidenceTrace item={item} /> : <div className="inspector-empty"><Orbit size={30} />{query.isError ? <><strong>{text('证据读取失败', 'Evidence read failed')}</strong><p>{String(query.error.message)}</p><button className="evidence-read-retry" onClick={() => void query.refetch()}>{text('重新读取', 'Retry')}</button></> : text('解析 Evidence…', 'resolving evidence…')}</div>}
    </motion.aside>, document.body
  )
}

function EvidenceTrace({ item }: { item: EvidenceDetail }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const locator = Object.entries(item.locator).map(([key, value]) => key + '=' + String(value)).join(' · ') || 'root'
  const objectIds = evidenceBoundObjectIds(item)
  return <div className="overlay-body">
    <div className="trace-hero">
      <BadgeCheck size={22} />
      <div>
        <small>{item.source.source_role} / {item.source.source_class}</small>
        <strong>{item.target.target_kind} · {item.target.label}</strong>
        <span className="mono" title={item.observation.external_object_id}>{compactEvidenceObjectRef(item.observation.external_object_id)}</span>
      </div>
    </div>
    {item.target.target_kind === 'claim' && item.target.detail.value !== undefined &&
      <div className="trace-statement">
        <small>{text('来源支持的断言', 'SOURCE-BOUND CLAIM')}</small>
        <p>{formatValue(item.target.detail.value)}</p>
      </div>}
    {item.document_passages?.length > 0 &&
      <section className="evidence-document-passages">
        <header>
          <small>{text('固定版本原文节选', 'SOURCE PASSAGES')}</small>
          <p>{text('这些是固定来源的解析片段；具体断言仍按引用与定位核对。', 'Passages from the fixed source; verify each claim against its citation and locator.')}</p>
        </header>
        {item.document_passages.map((passage, index) =>
          <article key={passage.chunk_ref} title={passage.chunk_ref}>
            <span>{String(index + 1).padStart(2, '0')} / {passage.section ?? text('正文', 'BODY')}</span>
            <p>{passage.text}</p>
          </article>)}
      </section>}
    <TraceRow label="SOURCE REVISION" value={item.observation.external_revision ?? 'content-addressed'} />
    <TraceRow label="LOCATOR" value={locator} />
    <TraceRow label="OBSERVED" value={new Date(item.observation.observed_at).toLocaleString()} />
    <TraceRow label="TRUST" value={item.artifact?.trust_class ?? 'observation-bound'} />
    {objectIds.length > 0 && <div className="evidence-object-links">
      <small>{text('绑定对象', 'BOUND OBJECTS')}</small>
      <div>{objectIds.map((objectId, index) =>
        <button key={objectId} onClick={() => navigate(`/intelligence?object=${encodeURIComponent(objectId)}&from=case`)}>
          <BrainCircuit size={11} />
          {index === 0 ? text('打开主体档案', 'OPEN SUBJECT DOSSIER') : text('打开关系对象', 'OPEN RELATED OBJECT')}
          <span className="mono">{compactEvidenceObjectRef(objectId)}</span>
        </button>)}</div>
    </div>}
    {item.observation.canonical_url &&
      <a className="investigation-evidence-source" href={item.observation.canonical_url} target="_blank" rel="noreferrer">
        <Link2 size={11} /> {text('打开规范来源', 'OPEN CANONICAL SOURCE')}
      </a>}
    <div className="mono overlay-ref">{item.evidence_ref}</div>
  </div>
}

function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

function TraceRow({ label, value }: { label: string; value: string }) { return <div className="trace-row"><small>{label}</small><strong>{value}</strong></div> }
function EventIcon({ type }: { type: string }) { if (type === 'failed') return <CircleAlert size={13} />; if (type === 'decision_ready') return <Sparkles size={13} />; if (type === 'finding_added') return <BadgeCheck size={13} />; if (type === 'evidence_need_changed') return <SearchCheck size={13} />; if (type === 'waiting') return <Orbit size={13} />; return <TerminalSquare size={13} /> }
export function RadioState({ state }: { state: string }) { return state === 'live' ? <CircleDot size={11} /> : <Activity size={11} /> }
function latestNarrative(events: ProductRuntimeEvent[], text: (zh: string, en: string) => string) { const latest = events[events.length - 1]; return latest ? runtimeEventSummary(latest, text) : text('调查正在整理当前证据与执行状态。', 'The investigation is organizing its evidence and runtime state.') }

function ProgressiveReveal({ text }: { text: string }) {
  const reduced = useReducedMotion()
  return (
    <motion.p
      key={text}
      className="progressive-narrative"
      initial={reduced ? false : { opacity: .25, clipPath: 'inset(0 100% 0 0)' }}
      animate={{ opacity: 1, clipPath: 'inset(0 0% 0 0)' }}
      transition={{ duration: reduced ? 0 : .46, ease: [0.22, 1, 0.36, 1] }}
    >
      {text}
    </motion.p>
  )
}

function continuationTaskKind(value: string | null, profile: string | null): TaskKind {
  if (
    value === 'verify_version_fix'
    || value === 'resolve_conflict'
    || value === 'investigate_relation'
    || value === 'investigate_incident'
    || value === 'watch_incident'
    || value === 'assess_normative_applicability'
    || value === 'observe_live_asset'
  ) return value
  if (profile === 'VERIFY') return 'verify_version_fix'
  if (profile === 'WATCH') return 'watch_incident'
  return 'investigate_incident'
}

function followUpNarrative(result: QuestionResult, text: (zh: string, en: string) => string) {
  if (result.mode === 'accepted') return text(
    `继续当前调查 · ${result.execution_profile} · Case ${result.investigation?.case_id ?? ''}`,
    `CONTINUE CURRENT INVESTIGATION · ${result.execution_profile} · Case ${result.investigation?.case_id ?? ''}`,
  )
  const answerItems = Object.entries(result.decision?.answer ?? {}).slice(0, 4)
  if (answerItems.length) return answerItems.map(([key, value]) => `${key}: ${formatFollowUpAnswer(value)}`).join(' · ')
  const conclusion = result.decision?.conclusions?.[0]?.statement
  return conclusion
    ? conclusion
    : text(
      `Decision ${result.decision?.decision_id ?? ''} 已就绪。`,
      `Decision ${result.decision?.decision_id ?? ''} ready.`,
    )
}

function formatFollowUpAnswer(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}
