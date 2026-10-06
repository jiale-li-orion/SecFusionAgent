import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  Activity,
  BadgeCheck,
  BrainCircuit,
  CircleAlert,
  CircleDot,
  OctagonX,
  FileWarning,
  Link2,
  MessageSquareText,
  Orbit,
  Radar,
  SearchCheck,
  Sparkles,
  TerminalSquare,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  askQuestion,
  cancelInvestigation,
  evidenceBoundObjectIds,
  getEvidence,
  getInvestigation,
  getInvestigationActivity,
  listInvestigations,
  type EvidenceDetail,
  type InvestigationFinding,
  type InvestigationView,
  type ProductRuntimeEvent,
  type QuestionResult,
  type TaskKind,
} from '../lib/api'
import { useI18n } from '../lib/i18n'

const liveStatuses = new Set(['active', 'waiting'])
type CaseStateFocus = 'confirmed' | 'conflicts' | 'unknowns' | 'needs' | 'decision'
type EventCue = { eventId: string; state: CaseStateFocus }

export function InvestigationsPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const listQuery = useQuery({ queryKey: ['investigations'], queryFn: () => listInvestigations(48), refetchInterval: 20_000 })
  const preferredCase = params.get('case')
  const sessionId = params.get('session')
  const origin = params.get('from')
  const originRun = params.get('run')
  const focusParam = params.get('focus')
  const evidenceParam = params.get('evidence')
  const fallbackCase = listQuery.data?.items.find((item) => liveStatuses.has(item.status))?.case_id ?? listQuery.data?.items[0]?.case_id ?? null
  const selectedCase = preferredCase ?? fallbackCase
  const detailQuery = useQuery({ queryKey: ['investigation', selectedCase], queryFn: () => getInvestigation(selectedCase!), enabled: Boolean(selectedCase), refetchInterval: selectedCase ? 15_000 : false })
  const activityQuery = useQuery({ queryKey: ['investigation-activity', selectedCase], queryFn: () => getInvestigationActivity(selectedCase!), enabled: Boolean(selectedCase) })
  const [streamEvents, setStreamEvents] = useState<Record<string, ProductRuntimeEvent[]>>({})
  const [streamConnection, setStreamConnection] = useState<{ caseId: string; state: 'live' | 'retrying' } | null>(null)
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(evidenceParam)
  const [eventCue, setEventCue] = useState<EventCue | null>(null)
  const events = useMemo(
    () => mergeRuntimeEvents(activityQuery.data?.events ?? [], selectedCase ? streamEvents[selectedCase] ?? [] : []),
    [activityQuery.data?.events, selectedCase, streamEvents],
  )
  const streamState: 'idle' | 'connecting' | 'live' | 'retrying' = !selectedCase
    ? 'idle'
    : streamConnection?.caseId === selectedCase
      ? streamConnection.state
      : 'connecting'

  useEffect(() => {
    if (!selectedCase) return
    const source = new EventSource(`/api/v1/investigations/${encodeURIComponent(selectedCase)}/events`)
    source.onopen = () => setStreamConnection({ caseId: selectedCase, state: 'live' })
    const eventNames = ['started', 'status_changed', 'progress', 'finding_added', 'finding_changed', 'conflict_changed', 'unknown_changed', 'evidence_need_changed', 'decision_ready', 'waiting', 'completed', 'failed', 'canceled']
    const onEvent = (message: MessageEvent<string>) => {
      try {
        const item = JSON.parse(message.data) as ProductRuntimeEvent
        setStreamEvents((current) => {
          const caseEvents = current[selectedCase] ?? []
          if (caseEvents.some((event) => event.event_id === item.event_id)) return current
          return { ...current, [selectedCase]: [...caseEvents, item] }
        })
        const state = eventState(item.event_type)
        if (state) setEventCue({ eventId: item.event_id, state })
        void queryClient.invalidateQueries({ queryKey: ['investigation', selectedCase] })
        void queryClient.invalidateQueries({ queryKey: ['investigations'] })
      } catch {
        // Keep the stream alive if one ProductEvent cannot be decoded.
      }
    }
    eventNames.forEach((name) => source.addEventListener(name, onEvent as EventListener))
    source.onerror = () => setStreamConnection({ caseId: selectedCase, state: 'retrying' })
    return () => {
      eventNames.forEach((name) => source.removeEventListener(name, onEvent as EventListener))
      source.close()
    }
  }, [queryClient, selectedCase])

  const selected = detailQuery.data
  const cases = listQuery.data?.items ?? []
  const liveCount = cases.filter((item) => liveStatuses.has(item.status)).length

  function selectCase(caseId: string) {
    setSelectedEvidence(null)
    setEventCue(null)
    setParams({ case: caseId })
  }

  return (
    <section className={`investigations-space investigations-page ${selected ? 'has-case' : 'case-index-only'}`}>
      <header className="case-docket-heading investigation-heading">
        <div>
          <p>{text('让 Case 保持开放，直到证据推动它前进', 'KEEP THE CASE OPEN UNTIL THE EVIDENCE MOVES')}</p>
          <h1>{text('调查', 'INVESTIGATION')} <span>{text('现场', 'FIELD')}</span></h1>
          <small>{text(
            '同一 durable Case 容纳 Confirmed、Conflict、Unknown、EvidenceNeed、Decision 与 continuous session；ProductEvent / SSE 把真实状态变化逐条送入现场。',
            'One durable Case contains Confirmed, Conflict, Unknown, EvidenceNeed, Decision, and the continuous session. ProductEvent / SSE delivers real state changes into the field.',
          )}</small>
        </div>
        <div className="investigation-stats">
          <span><CircleDot size={12} /> {text('运行中', 'LIVE')} <strong>{liveCount}</strong></span>
          <span>{text('调查', 'CASES')} <strong>{cases.length}</strong></span>
          <span className={`stream-state stream-${streamState}`}><RadioState state={streamState} /> {streamState.toUpperCase()}</span>
        </div>
      </header>
      {origin === 'task' && originRun && (
        <div className="investigation-origin">
          <span>TASK → CASE</span>
          <strong className="mono">{originRun}</strong>
          <button onClick={() => {
            const query = new URLSearchParams({ run: originRun, from: 'case', caseRef: selectedCase ?? '' })
            navigate(`/agents?${query.toString()}`)
          }}>{text('返回 Task', 'BACK TO TASK')}</button>
        </div>
      )}

      <div className="investigation-layout">
        <aside className="case-rail">
          <div className="case-rail-head"><SearchCheck size={15} /><strong>{text('案件卷宗', 'CASE FILES')}</strong><span>{cases.length}</span></div>
          {listQuery.isError && (
            <div className="case-index-fault" role="alert">
              <CircleAlert size={14} />
              <div><small>{text('CASE 索引不可用', 'CASE INDEX UNAVAILABLE')}</small><strong>{text('durable Case 索引当前不可读。', 'The durable Case index is currently unreadable.')}</strong></div>
              <button className="recovery-action" onClick={() => void listQuery.refetch()}>{text('重试 Case 索引', 'RETRY CASE INDEX')}</button>
            </div>
          )}
          <div className="case-list">
            {cases.map((item) => (
              <button key={item.case_id} className={`case-card ${item.case_id === selectedCase ? 'selected' : ''} case-${item.status}`} onClick={() => selectCase(item.case_id)}>
                <span className="case-status-dot" />
                <span className="case-card-copy"><small>{item.execution_profile ?? item.current_activity.task_kind ?? 'INVESTIGATION'}</small><strong>{item.goal}</strong><em>{item.current_activity.actor_role ?? 'runtime'} · {item.current_activity.phase}</em></span>
                <span className="case-card-tail"><b>{item.status}</b><small>r{item.revision}</small></span>
              </button>
            ))}
            {listQuery.isLoading && <div className="case-list-empty">{text('加载 durable Cases…', 'Loading durable cases…')}</div>}
            {!listQuery.isLoading && cases.length === 0 && <CaseRailBlueprint />}
          </div>
        </aside>

        <main className="case-workspace">
          <AnimatePresence mode="wait">
            {detailQuery.isError ? (
              <div className="case-detail-fault" role="alert"><TerminalSquare size={18} /><small>{text('CASE 读取失败', 'CASE READ FAILED')}</small><strong>{String(detailQuery.error.message)}</strong><button className="recovery-action" onClick={() => void detailQuery.refetch()}>{text('重试当前 Case', 'RETRY CASE READ')}</button></div>
            ) : selected ? (
              <motion.div
                key={selected.case_id}
                className="case-docket-transition"
                initial={reduceMotion ? false : { opacity: 0, x: -18, rotateZ: -.18 }}
                animate={{ opacity: 1, x: 0, rotateZ: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0, x: 14, rotateZ: .12 }}
                transition={{ duration: reduceMotion ? 0 : .26, ease: [0.22, 1, 0.36, 1] }}
              >
                <CaseWorkspace investigation={selected} events={events} eventCue={eventCue} initialFocus={normalizeCaseFocus(focusParam)} onEvidence={setSelectedEvidence} sessionId={sessionId} reduceMotion={reduceMotion} onFollowUpComplete={() => { void queryClient.invalidateQueries({ queryKey: ['investigation', selectedCase] }); void queryClient.invalidateQueries({ queryKey: ['investigations'] }) }} />
              </motion.div>
            ) : <InvestigationFieldBlueprint loading={listQuery.isLoading} />}
          </AnimatePresence>
        </main>

        <aside className="activity-rail">
          <div className="activity-head"><div><small>{text('产品事件流', 'PRODUCT EVENT STREAM')}</small><strong>{text('实时活动', 'LIVE ACTIVITY')}</strong></div><span className={`stream-beacon stream-${streamState}`} /></div>
          {activityQuery.isError && <div className="activity-fault" role="alert"><CircleAlert size={13} /><span>{text('历史 ProductEvent read 不可用；SSE 会继续尝试连接。', 'Historical ProductEvent read is unavailable; SSE continues reconnect attempts.')}</span><button className="recovery-action" onClick={() => void activityQuery.refetch()}>{text('重试历史事件', 'RETRY EVENT HISTORY')}</button></div>}
          {events.length ? <RuntimeEventRail events={events} activeEventId={eventCue?.eventId ?? null} onFocus={(event) => { const state = eventState(event.event_type); if (state) setEventCue({ eventId: event.event_id, state }) }} /> : <EventRailBlueprint state={streamState} />}
        </aside>
      </div>

      <AnimatePresence>{selectedEvidence && <EvidenceOverlay evidenceRef={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}</AnimatePresence>
    </section>
  )
}

function normalizeCaseFocus(value: string | null): CaseStateFocus | null {
  if (value === 'confirmed' || value === 'conflicts' || value === 'unknowns' || value === 'needs' || value === 'decision') return value
  return null
}

function CaseRailBlueprint() {
  const { text } = useI18n()
  return (
    <div className="case-rail-blueprint">
      {['VERIFY FIX BOUNDARY', 'INVESTIGATE RELATION', 'WATCH INCIDENT'].map((label, index) => (
        <div key={label}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <div><small>{text('持久 CASE 槽位', 'DURABLE CASE SLOT')}</small><strong>{label}</strong><em>{text('从 START 创建', 'launch from START')}</em></div>
        </div>
      ))}
    </div>
  )
}

function InvestigationFieldBlueprint({ loading }: { loading: boolean }) {
  const { text } = useI18n()
  const states = [
    { label: text('已确认', 'CONFIRMED'), tone: 'lime', icon: BadgeCheck, copy: text('证据边界内的已证事实', 'evidence-bounded findings') },
    { label: text('冲突', 'CONFLICTS'), tone: 'amber', icon: CircleAlert, copy: text('保留来源分歧与张力', 'preserved source tension') },
    { label: text('未知', 'UNKNOWNS'), tone: 'violet', icon: FileWarning, copy: text('明确记录未决边界', 'explicit uncertainty') },
    { label: text('证据需求', 'EVIDENCE NEEDS'), tone: 'cyan', icon: SearchCheck, copy: text('下一步待获取证据', 'open acquisition gaps') },
  ]
  return (
    <div className="investigation-blueprint">
      <div className="investigation-blueprint-case">
        <div className="case-blueprint-sigil"><Radar size={25} /></div>
        <div><small>{text('持久 CASE / 调查状态', 'DURABLE CASE / INVESTIGATION STATE')}</small><strong>{loading ? text('解析 Case 索引…', 'RESOLVING CASE INDEX…') : text('尚未选择活动 Case', 'NO ACTIVE CASE SELECTED')}</strong><span>{text('VERIFY / INVESTIGATE / WATCH 会创建或恢复这台状态机。', 'VERIFY / INVESTIGATE / WATCH create or resume this state machine.')}</span></div>
        <div className="case-blueprint-revision"><b>REV —</b><small>{text('CASE 状态', 'CASE STATE')}</small></div>
      </div>

      <div className="investigation-blueprint-state">
        {states.map(({ label, tone, icon: Icon, copy }, index) => (
          <motion.div
            key={label}
            className={'case-state-blueprint tone-' + tone}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * .05 }}
          >
            <div><Icon size={14} /><strong>{label}</strong><span>0</span></div>
            <i /><i />
            <small>{copy}</small>
          </motion.div>
        ))}
      </div>

      <div className="investigation-blueprint-convergence">
        <svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
          <path d="M 6 3 C 30 4, 32 15, 50 16" />
          <path d="M 31 3 C 38 7, 41 14, 50 16" />
          <path d="M 69 3 C 62 7, 59 14, 50 16" />
          <path d="M 94 3 C 70 4, 68 15, 50 16" />
          <path className="decision" d="M 50 16 C 50 22, 50 24, 50 30" />
        </svg>
        <div className="argus-node"><Orbit size={17} /><small>ARGUS</small><strong>{text('证据使用', 'EVIDENCE USE')}</strong></div>
        <div className="oracle-decision-node"><Sparkles size={17} /><small>ORACLE</small><strong>DECISION</strong></div>
      </div>

      <div className="investigation-blueprint-session">
        <MessageSquareText size={15} />
        <div><small>{text('持续 CASE 会话', 'CONTINUOUS CASE SESSION')}</small><strong>{text('后续追问持续绑定同一个 durable Case', 'follow-up stays bound to the same durable Case')}</strong></div>
        <span>{text('会话 / Case 连续性', 'SESSION / CASE CONTINUITY')}</span>
      </div>
    </div>
  )
}

function EventRailBlueprint({ state }: { state: string }) {
  const { text } = useI18n()
  const labels = ['investigation.started', 'evidence_need_changed', 'finding_added', 'decision_ready']
  return (
    <div className="event-rail-blueprint">
      <div className="event-rail-state"><span /><strong>{state.toUpperCase()}</strong><small>{text('SSE 产品事件通道', 'SSE PRODUCT EVENT CHANNEL')}</small></div>
      {labels.map((label, index) => (
        <div
          key={label}
          className="event-blueprint-row"
        >
          <span>{String(index + 1).padStart(2, '0')}</span>
          <i />
          <div><small>{text('产品事件', 'PRODUCT EVENT')}</small><strong>{label}</strong><em>{text('真实 persisted/runtime event 出现后显示', 'appears when a persisted/runtime event exists')}</em></div>
        </div>
      ))}
    </div>
  )
}

function CaseWorkspace({ investigation, events, eventCue, initialFocus, onEvidence, sessionId, reduceMotion, onFollowUpComplete }: { investigation: InvestigationView; events: ProductRuntimeEvent[]; eventCue: EventCue | null; initialFocus: CaseStateFocus | null; onEvidence: (ref: string) => void; sessionId: string | null; reduceMotion: boolean; onFollowUpComplete: () => void }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [followUp, setFollowUp] = useState('')
  const [followUpBusy, setFollowUpBusy] = useState(false)
  const [sessionTurns, setSessionTurns] = useState<Array<{ kind: 'user' | 'system'; text: string }>>([])
  const [cancelBusy, setCancelBusy] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const [stateFocus, setStateFocus] = useState<CaseStateFocus | null>(initialFocus)

  useEffect(() => {
    if (eventCue) setStateFocus(eventCue.state)
  }, [eventCue])

  const latestTaskRunId = [...events].reverse().find((event) => event.task_run_id)?.task_run_id ?? null

  async function sendFollowUp() {
    const question = followUp.trim()
    if (!question || !sessionId || followUpBusy) return
    setFollowUpBusy(true)
    setSessionTurns((current) => [...current, { kind: 'user', text: question }])
    setFollowUp('')
    try {
      const result = await askQuestion({ question, sessionId, taskKind: continuationTaskKind(investigation.current_activity.task_kind) })
      setSessionTurns((current) => [...current, { kind: 'system', text: followUpNarrative(result, text) }])
      onFollowUpComplete()
    } catch (error) {
      setSessionTurns((current) => [...current, { kind: 'system', text: error instanceof Error ? error.message : text('后续追问失败', 'Follow-up failed') }])
    } finally {
      setFollowUpBusy(false)
    }
  }
  async function cancelCase() {
    if (cancelBusy || !liveStatuses.has(investigation.status)) return
    setCancelBusy(true)
    setCancelError('')
    try {
      await cancelInvestigation(investigation.case_id)
      onFollowUpComplete()
    } catch (error) {
      setCancelError(error instanceof Error ? error.message : text('取消 Case 失败', 'Cancel failed'))
    } finally {
      setCancelBusy(false)
    }
  }

  return (
    <div className="case-workspace-stack">
      <article className="case-hero">
        <div className="case-hero-main">
          <span className="case-hero-sigil"><Radar size={25} /></span>
          <div><small>CASE / {investigation.execution_profile ?? 'RUNTIME'}</small><strong>{investigation.goal}</strong><span className="mono">{investigation.case_id}</span></div>
        </div>
        <div className="case-hero-state"><span className={`case-state-badge state-${investigation.status}`}>{investigation.status}</span><strong>REV {investigation.revision}</strong><small>{investigation.current_activity.actor_role ?? 'runtime'} · {investigation.current_activity.phase}</small>{liveStatuses.has(investigation.status) && <button className="case-cancel-button" onClick={() => void cancelCase()} disabled={cancelBusy}><OctagonX size={12} /> {cancelBusy ? text('取消中…', 'CANCELLING…') : text('取消 Case', 'CANCEL CASE')}</button>}{cancelError && <em className="case-cancel-error">{cancelError}</em>}</div>
      </article>
      {investigation.target_object_ids.length > 0 && (
        <div className="case-target-strip">
          <small>{text('调查目标', 'CASE TARGETS')}</small>
          <div>{investigation.target_object_ids.slice(0, 6).map((objectId) => <button key={objectId} onClick={() => {
            const query = new URLSearchParams({ object: objectId, from: 'case', caseRef: investigation.case_id })
            navigate(`/intelligence?${query.toString()}`)
          }}><BrainCircuit size={11} /><span>{text('打开对象档案', 'OPEN OBJECT DOSSIER')}</span><b className="mono">{compactEvidenceObjectRef(objectId)}</b></button>)}</div>
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
            <small>{text('运行终止 / 可诊断失败', 'RUNTIME TERMINATION / DIAGNOSABLE FAILURE')}</small>
            <strong>{investigation.terminal_reason}</strong>
          </div>
          {latestTaskRunId && (
            <button onClick={() => {
              const query = new URLSearchParams({ run: latestTaskRunId, from: 'case', caseRef: investigation.case_id })
              navigate(`/agents?${query.toString()}`)
            }}>
              {text('打开 Task Trace', 'OPEN TASK TRACE')}
            </button>
          )}
        </motion.section>
      )}

      {investigation.status === 'waiting' && (
        <section className={`case-wait-boundary status-${investigation.current_activity.task_status ?? 'waiting'}`}>
          <span className="case-wait-glyph"><CircleDot size={14} /></span>
          <div>
            <small>{investigation.current_activity.task_status === 'waiting_input' ? text('等待用户输入', 'WAITING FOR INPUT') : text('等待依赖变化', 'WAITING FOR DEPENDENCY')}</small>
            <strong>{investigation.current_activity.task_status === 'waiting_input'
              ? text('继续提问会在同一个 durable Case 上开启新的 InvestigationRole episode。', 'A follow-up opens a new InvestigationRole episode on the same durable Case.')
              : text('Dependency wake 由 Task Runtime 接管；相关子任务状态变化后，父 Task 可以重新进入 queued。', 'Dependency wake is owned by Task Runtime; a relevant child state change can return the parent Task to queued.')}</strong>
          </div>
          <div className="case-wait-actions">
            {investigation.current_activity.task_status === 'waiting_input' && sessionId && <button onClick={() => document.getElementById('case-session-composer')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>{text('继续当前 Case', 'CONTINUE CASE')}</button>}
            {investigation.current_activity.task_status === 'waiting_dependency' && latestTaskRunId && <button onClick={() => navigate(`/agents?run=${encodeURIComponent(latestTaskRunId)}&from=case&caseRef=${encodeURIComponent(investigation.case_id)}`)}>{text('查看等待边界', 'OPEN WAIT BOUNDARY')}</button>}
          </div>
        </section>
      )}

      {investigation.status === 'waiting' && (
        <section className="case-resume-boundary">
          <div>
            <small>{text('WAITING / 恢复路径', 'WAITING / RESUME PATH')}</small>
            <strong>{sessionId ? text('通过当前 Case session 继续', 'CONTINUE THROUGH CURRENT CASE SESSION') : text('等待 runtime dependency wake', 'AWAIT RUNTIME DEPENDENCY WAKE')}</strong>
            <span>{sessionId
              ? text('新的用户输入会在同一个 Case 上开启下一次 InvestigationRole episode。', 'A new user turn opens the next InvestigationRole episode on the same durable Case.')
              : text('通用手动 resume API 尚未暴露；dependency wake 由 Task Runtime 持有。', 'Generic manual resume is not exposed; dependency wake remains owned by Task Runtime.')}</span>
          </div>
          {sessionId && <button onClick={() => { document.getElementById('case-followup-input')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); window.setTimeout(() => (document.getElementById('case-followup-input') as HTMLInputElement | null)?.focus(), 280) }}>{text('继续当前 Case', 'CONTINUE CASE')}</button>}
        </section>
      )}

      <div className={`case-state-grid ${stateFocus ? `has-state-focus focus-${stateFocus}` : ''}`}>
        <StateColumn key={`confirmed:${eventCue?.state === 'confirmed' ? eventCue.eventId : 'stable'}`} title={text('已确认', 'CONFIRMED')} tone="lime" icon={BadgeCheck} items={investigation.confirmed_findings} onEvidence={onEvidence} active={stateFocus === 'confirmed'} dimmed={Boolean(stateFocus && stateFocus !== 'confirmed')} forged={eventCue?.state === 'confirmed'} reduceMotion={reduceMotion} onFocus={() => setStateFocus((current) => current === 'confirmed' ? null : 'confirmed')} />
        <StateColumn key={`conflicts:${eventCue?.state === 'conflicts' ? eventCue.eventId : 'stable'}`} title={text('冲突', 'CONFLICTS')} tone="amber" icon={CircleAlert} items={investigation.conflicts} onEvidence={onEvidence} active={stateFocus === 'conflicts'} dimmed={Boolean(stateFocus && stateFocus !== 'conflicts')} forged={eventCue?.state === 'conflicts'} reduceMotion={reduceMotion} onFocus={() => setStateFocus((current) => current === 'conflicts' ? null : 'conflicts')} />
        <StateColumn key={`unknowns:${eventCue?.state === 'unknowns' ? eventCue.eventId : 'stable'}`} title={text('未知', 'UNKNOWNS')} tone="violet" icon={FileWarning} items={investigation.unknowns} onEvidence={onEvidence} active={stateFocus === 'unknowns'} dimmed={Boolean(stateFocus && stateFocus !== 'unknowns')} forged={eventCue?.state === 'unknowns'} reduceMotion={reduceMotion} onFocus={() => setStateFocus((current) => current === 'unknowns' ? null : 'unknowns')} />
        <EvidenceNeeds key={`needs:${eventCue?.state === 'needs' ? eventCue.eventId : 'stable'}`} investigation={investigation} active={stateFocus === 'needs'} dimmed={Boolean(stateFocus && stateFocus !== 'needs')} forged={eventCue?.state === 'needs'} reduceMotion={reduceMotion} onFocus={() => setStateFocus((current) => current === 'needs' ? null : 'needs')} />
      </div>

      <motion.div
        key={`decision:${eventCue?.state === 'decision' ? eventCue.eventId : 'stable'}`}
        className={`decision-focus-wrap ${stateFocus === 'decision' ? 'state-focused' : stateFocus ? 'state-dimmed' : ''} ${eventCue?.state === 'decision' ? 'state-forged' : ''}`}
        initial={eventCue?.state === 'decision' && !reduceMotion ? { opacity: .35, scale: .985 } : false}
        animate={{ opacity: stateFocus && stateFocus !== 'decision' ? .22 : 1, scale: 1 }}
        transition={{ duration: reduceMotion ? 0 : .28 }}
        role="button"
        tabIndex={0}
        aria-pressed={stateFocus === 'decision'}
        onClick={() => setStateFocus((current) => current === 'decision' ? null : 'decision')}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            setStateFocus((current) => current === 'decision' ? null : 'decision')
          }
        }}
      >
        <DecisionPanel investigation={investigation} onEvidence={onEvidence} />
      </motion.div>

      <section className="conversation-shell">
        <div className="conversation-title"><MessageSquareText size={15} /><div><small>{text('持续交互', 'CONTINUOUS INTERACTION')}</small><strong>{text('Case 会话', 'CASE SESSION')}</strong></div><span>{sessionId ? text('绑定当前 Case', 'BOUND TO CURRENT CASE') : text('从 START 进入后绑定会话', 'OPEN FROM START TO BIND SESSION')}</span></div>
        <div className="conversation-preview">
          <div className="system-message"><Sparkles size={14} /><ProgressiveReveal text={latestNarrative(events, investigation)} /></div>
          {sessionTurns.map((turn, index) => <motion.div key={`${turn.kind}:${index}`} className={`session-turn turn-${turn.kind}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}><small>{turn.kind === 'user' ? 'YOU' : 'SECFUSION'}</small><p>{turn.text}</p></motion.div>)}
          <div id="case-session-composer" className={`case-session-composer ${sessionId ? 'enabled' : 'disabled'}`}>
            <input id="case-followup-input" value={followUp} onChange={(event) => setFollowUp(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendFollowUp() } }} disabled={!sessionId || followUpBusy} placeholder={sessionId ? text('继续当前调查…', 'Continue this investigation…') : text('从 START 进入调查后即可持续追问', 'Launch from START to bind a continuous session')} />
            <button onClick={() => void sendFollowUp()} disabled={!sessionId || !followUp.trim() || followUpBusy}>{followUpBusy ? text('发送中…', 'SENDING…') : text('发送', 'SEND')}</button>
          </div>
        </div>
      </section>
    </div>
  )
}

function StateColumn({ title, tone, icon: Icon, items, onEvidence, active, dimmed, forged, reduceMotion, onFocus }: { title: string; tone: string; icon: typeof BadgeCheck; items: InvestigationFinding[]; onEvidence: (ref: string) => void; active: boolean; dimmed: boolean; forged: boolean; reduceMotion: boolean; onFocus: () => void }) {
  const { text } = useI18n()
  return (
    <motion.section
      className={`state-column tone-${tone} ${active ? 'state-focused' : ''} ${dimmed ? 'state-dimmed' : ''} ${forged ? 'state-forged' : ''}`}
      initial={forged && !reduceMotion ? { opacity: .38, y: 7, scale: .985 } : false}
      animate={{ opacity: dimmed ? .18 : 1, y: 0, scale: 1 }}
      transition={{ duration: reduceMotion ? 0 : .28, ease: [0.22, 1, 0.36, 1] }}
    >
      <button type="button" className="state-column-head" onClick={onFocus}><Icon size={14} /><strong>{title}</strong><span>{items.length}</span></button>
      <div className="state-items">
        {items.slice(0, 8).map((item, index) => (
          <motion.article key={`${item.proposition}:${index}`} className="state-item" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <strong>{item.proposition}</strong>
            <small>revision {item.updated_revision}</small>
            <EvidenceButtons refs={item.evidence_refs} onEvidence={onEvidence} />
          </motion.article>
        ))}
        {items.length === 0 && <div className="state-empty">{text('当前没有条目。', 'No current items.')}</div>}
      </div>
    </motion.section>
  )
}

function EvidenceNeeds({ investigation, active, dimmed, forged, reduceMotion, onFocus }: { investigation: InvestigationView; active: boolean; dimmed: boolean; forged: boolean; reduceMotion: boolean; onFocus: () => void }) {
  const { text } = useI18n()
  return (
    <motion.section className={`state-column tone-cyan ${active ? 'state-focused' : ''} ${dimmed ? 'state-dimmed' : ''} ${forged ? 'state-forged' : ''}`} initial={forged && !reduceMotion ? { opacity: .38, y: 7 } : false} animate={{ opacity: dimmed ? .18 : 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .28 }}>
      <button type="button" className="state-column-head" onClick={onFocus}><SearchCheck size={14} /><strong>{text('证据缺口', 'EVIDENCE NEEDS')}</strong><span>{investigation.open_evidence_needs.length}</span></button>
      <div className="state-items">
        {investigation.open_evidence_needs.slice(0, 8).map((need) => (
          <article key={need.need_id} className="state-item evidence-need-item">
            <strong>{need.question}</strong><small>{need.purpose} · priority {need.priority}</small>
            <div className="need-roles">{need.required_source_roles.map((role) => <span key={role}>{role}</span>)}</div>
          </article>
        ))}
        {investigation.open_evidence_needs.length === 0 && <div className="state-empty">{text('当前没有开放的证据缺口。', 'No open evidence gaps.')}</div>}
      </div>
    </motion.section>
  )
}

function DecisionPanel({ investigation, onEvidence }: { investigation: InvestigationView; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const decision = investigation.latest_decision
  return (
    <section className={`decision-panel ${decision ? 'ready' : ''}`}>
      <div className="decision-oracle"><div className="oracle-mini"><div /><div /><Sparkles size={19} /></div><div><small>ORACLE / DECISION</small><strong>{decision ? text('DECISION 已就绪', 'DECISION READY') : text('等待 Evidence', 'WAITING FOR EVIDENCE')}</strong></div></div>
      {decision ? (
        <div className="decision-content">
          {decision.conclusions.map((item, index) => (
            <div key={`${index}:${item.statement}`} className="decision-conclusion"><span>{String(index + 1).padStart(2, '0')}</span><div><small>{item.type}</small><strong>{item.statement}</strong><EvidenceButtons refs={item.evidence_refs} onEvidence={onEvidence} /></div></div>
          ))}
          {(decision.conflicts.length > 0 || decision.unknowns.length > 0) && <div className="decision-boundary"><span>{text(`${decision.conflicts.length} 个 conflicts`, `${decision.conflicts.length} conflicts`)}</span><span>{text(`${decision.unknowns.length} 个 unknowns`, `${decision.unknowns.length} unknowns`)}</span><span>{decision.stop_reason}</span></div>}
        </div>
      ) : <p className="decision-waiting">{text('ARGUS 正围绕 EvidenceNeed 推进。证据边界满足后，Decision 收束。', 'ARGUS is advancing around the current EvidenceNeed. Decision closes when the evidence boundary is satisfied.')}</p>}
    </section>
  )
}

function RuntimeEventRail({ events, activeEventId, onFocus }: { events: ProductRuntimeEvent[]; activeEventId: string | null; onFocus: (event: ProductRuntimeEvent) => void }) {
  const { text } = useI18n()
  const visible = events.slice(-32).reverse()
  return <div className="runtime-event-list">{visible.map((event, index) => <motion.button type="button" key={event.event_id} onClick={() => onFocus(event)} className={`runtime-event event-${event.event_type} ${activeEventId === event.event_id ? 'event-focused' : ''} ${eventState(event.event_type) ? 'event-actionable' : ''}`} initial={{ opacity: 0, x: 18, scale: .98 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={{ delay: Math.min(index * .015, .18) }}><span className="event-symbol"><EventIcon type={event.event_type} /></span><div><small>{event.role_id ?? event.actor ?? event.source_kind}</small><strong>{event.summary}</strong><em>{event.technical_type} · {new Date(event.occurred_at).toLocaleTimeString()}</em>{event.evidence_refs.length > 0 && <span className="event-evidence">{text(`${event.evidence_refs.length} 条 evidence refs`, `${event.evidence_refs.length} evidence refs`)}</span>}</div></motion.button>)}</div>
}

function eventState(eventType: string): CaseStateFocus | null {
  if (eventType === 'finding_added' || eventType === 'finding_changed') return 'confirmed'
  if (eventType === 'conflict_changed') return 'conflicts'
  if (eventType === 'unknown_changed') return 'unknowns'
  if (eventType === 'evidence_need_changed') return 'needs'
  if (eventType === 'decision_ready' || eventType === 'completed') return 'decision'
  return null
}

function EvidenceButtons({ refs, onEvidence }: { refs: string[]; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  if (!refs.length) return null
  return <div className="finding-evidence">{refs.slice(0, 3).map((ref) => <button key={ref} onClick={() => onEvidence(ref)}><Link2 size={10} /> {text('证据', 'EVIDENCE')}</button>)}{refs.length > 3 && <span>+{refs.length - 3}</span>}</div>
}

function EvidenceOverlay({ evidenceRef, onClose }: { evidenceRef: string; onClose: () => void }) {
  const { text } = useI18n()
  const query = useQuery({ queryKey: ['evidence-overlay', evidenceRef], queryFn: () => getEvidence(evidenceRef) })
  const item = query.data
  return (
    <motion.aside
      className="investigation-evidence-lens"
      initial={{ opacity: 0, x: 36, clipPath: 'inset(0 0 0 18%)' }}
      animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
      exit={{ opacity: 0, x: 28, clipPath: 'inset(0 0 0 14%)' }}
      transition={{ type: 'spring', stiffness: 250, damping: 28 }}
    >
      <div className="overlay-head">
        <div><small>EVIDENCE TRACE</small><strong>{item?.source.source_id ?? text('解析中…', 'Resolving…')}</strong><span className="mono">{evidenceRef}</span></div>
        <button onClick={onClose}>{text('关闭', 'CLOSE')}</button>
      </div>
      {item ? <EvidenceTrace item={item} /> : <div className="inspector-empty"><Orbit size={30} />{query.isError ? String(query.error.message) : text('解析 Evidence…', 'resolving evidence…')}</div>}
    </motion.aside>
  )
}

function EvidenceTrace({ item }: { item: EvidenceDetail }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const locator = Object.entries(item.locator).map(([key, value]) => key + '=' + String(value)).join(' · ') || 'root'
  const objectIds = evidenceBoundObjectIds(item)
  return <div className="overlay-body"><div className="trace-hero"><BadgeCheck size={22} /><div><small>{item.source.source_role} / {item.source.source_class}</small><strong>{item.target.target_kind} · {item.target.label}</strong><span>{item.observation.external_object_id}</span></div></div><TraceRow label="SOURCE REVISION" value={item.observation.external_revision ?? 'content-addressed'} /><TraceRow label="LOCATOR" value={locator} /><TraceRow label="OBSERVED" value={new Date(item.observation.observed_at).toLocaleString()} /><TraceRow label="TRUST" value={item.artifact?.trust_class ?? 'observation-bound'} />{objectIds.length > 0 && <div className="evidence-object-links"><small>{text('绑定对象', 'BOUND OBJECTS')}</small><div>{objectIds.map((objectId, index) => <button key={objectId} onClick={() => navigate(`/intelligence?object=${encodeURIComponent(objectId)}&from=case`)}><BrainCircuit size={11} /> {index === 0 ? text('打开主体档案', 'OPEN SUBJECT DOSSIER') : text('打开关系对象', 'OPEN RELATED OBJECT')}<span className="mono">{compactEvidenceObjectRef(objectId)}</span></button>)}</div></div>}{item.observation.canonical_url && <a className="investigation-evidence-source" href={item.observation.canonical_url} target="_blank" rel="noreferrer"><Link2 size={11} /> {text('打开规范来源', 'OPEN CANONICAL SOURCE')}</a>}<div className="mono overlay-ref">{item.evidence_ref}</div></div>
}

function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

function TraceRow({ label, value }: { label: string; value: string }) { return <div className="trace-row"><small>{label}</small><strong>{value}</strong></div> }
function EventIcon({ type }: { type: string }) { if (type === 'failed') return <CircleAlert size={13} />; if (type === 'decision_ready') return <Sparkles size={13} />; if (type === 'finding_added') return <BadgeCheck size={13} />; if (type === 'evidence_need_changed') return <SearchCheck size={13} />; if (type === 'waiting') return <Orbit size={13} />; return <TerminalSquare size={13} /> }
function RadioState({ state }: { state: string }) { return state === 'live' ? <CircleDot size={11} /> : <Activity size={11} /> }
function latestNarrative(events: ProductRuntimeEvent[], investigation: InvestigationView) { const latest = events[events.length - 1]; return latest?.summary ?? `${investigation.current_activity.actor_role ?? 'Runtime'} is ${investigation.current_activity.phase}.` }

function ProgressiveReveal({ text }: { text: string }) {
  return (
    <motion.p
      key={text}
      className="progressive-narrative"
      initial={{ opacity: .25, clipPath: 'inset(0 100% 0 0)' }}
      animate={{ opacity: 1, clipPath: 'inset(0 0% 0 0)' }}
      transition={{ duration: .46, ease: [0.22, 1, 0.36, 1] }}
    >
      {text}
    </motion.p>
  )
}

function mergeRuntimeEvents(initial: ProductRuntimeEvent[], streamed: ProductRuntimeEvent[]) {
  const byId = new Map<string, ProductRuntimeEvent>()
  for (const event of initial) byId.set(event.event_id, event)
  for (const event of streamed) byId.set(event.event_id, event)
  return [...byId.values()].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
}

function continuationTaskKind(value: string | null): TaskKind {
  if (value === 'verify_version_fix' || value === 'investigate_incident' || value === 'watch_incident') return value
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
