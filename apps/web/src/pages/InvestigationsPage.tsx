import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  BadgeCheck,
  CircleAlert,
  CircleDot,
  FileWarning,
  MessageSquareText,
  Orbit,
  Radar,
  SearchCheck,
  Sparkles,
  TerminalSquare,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  getInvestigation,
  getInvestigationActivity,
  listInvestigations,
  type ProductRuntimeEvent,
} from '../lib/api'
import { CaseWorkspace, EvidenceOverlay, RadioState, RuntimeEventRail } from '../components/investigations/CaseSurfaces'
import { eventState, mergeRuntimeEvents, type CaseStateFocus, type EventCue } from '../lib/investigationPresentation'
import { useI18n } from '../lib/i18n'

const liveStatuses = new Set(['active', 'waiting'])

export function InvestigationsPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const listQuery = useQuery({ queryKey: ['investigations'], queryFn: () => listInvestigations(48), refetchInterval: 20_000 })
  const preferredCase = params.get('case')
  const sessionParam = params.get('session')
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
  const [caseArchiveExpanded, setCaseArchiveExpanded] = useState(false)
  const [eventHistoryExpanded, setEventHistoryExpanded] = useState(false)
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
  const sessionId = selected?.continuation_session_id ?? sessionParam
  const cases = useMemo(() => listQuery.data?.items ?? [], [listQuery.data?.items])
  const liveCount = cases.filter((item) => liveStatuses.has(item.status)).length
  const visibleCases = useMemo(() => {
    if (caseArchiveExpanded) return cases
    const selectedItem = cases.find((item) => item.case_id === selectedCase)
    const ordered = [
      ...(selectedItem ? [selectedItem] : []),
      ...cases.filter((item) => item.case_id !== selectedCase && liveStatuses.has(item.status)),
      ...cases.filter((item) => item.case_id !== selectedCase && !liveStatuses.has(item.status)),
    ]
    const seen = new Set<string>()
    return ordered.filter((item) => !seen.has(item.case_id) && seen.add(item.case_id)).slice(0, 6)
  }, [caseArchiveExpanded, cases, selectedCase])

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
            '跟进调查进展，查看已确认事实、来源冲突和证据缺口；补充信息后继续研判。',
            'Follow progress, review confirmed findings, source conflicts, and evidence gaps, then add information to continue.',
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
          <div className="case-rail-head">
            <SearchCheck size={15} />
            <strong>{text('案件卷宗', 'CASE FILES')}</strong>
            <span>{cases.length}</span>
            {cases.length > 6 && <button type="button" className="rail-density-toggle" aria-expanded={caseArchiveExpanded} onClick={() => setCaseArchiveExpanded((value) => !value)}>{caseArchiveExpanded ? text('聚焦', 'FOCUS') : text('全部', 'ALL')}</button>}
          </div>
          {listQuery.isError && (
            <div className="case-index-fault" role="alert">
              <CircleAlert size={14} />
              <div><small>{text('CASE 索引读取失败', 'CASE INDEX READ ERROR')}</small><strong>{text('durable Case 索引读取失败。', 'The durable Case index read failed.')}</strong></div>
              <button className="recovery-action" onClick={() => void listQuery.refetch()}>{text('重试 Case 索引', 'RETRY CASE INDEX')}</button>
            </div>
          )}
          <div className="case-list">
            {visibleCases.map((item) => (
              <button key={item.case_id} className={`case-card ${item.case_id === selectedCase ? 'selected' : ''} case-${item.status}`} onClick={() => selectCase(item.case_id)}>
                <span className="case-status-dot" />
                <span className="case-card-copy"><small>{item.execution_profile ?? item.current_activity.task_kind ?? 'INVESTIGATION'} · {item.origin_scope.toUpperCase()}</small><strong>{item.goal}</strong><em>{item.current_activity.actor_role ?? 'runtime'} · {item.current_activity.phase}</em></span>
                <span className="case-card-tail"><b>{item.status}</b><small>r{item.revision}</small></span>
              </button>
            ))}
            {!caseArchiveExpanded && cases.length > visibleCases.length && <button type="button" className="rail-overflow-note" onClick={() => setCaseArchiveExpanded(true)}>+{cases.length - visibleCases.length} {text('历史 Case', 'archived cases')}</button>}
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
          <div className="activity-head">
            <div><small>{text('产品事件流', 'PRODUCT EVENT STREAM')}</small><strong>{text('实时活动', 'LIVE ACTIVITY')}</strong></div>
            <div className="activity-head-actions"><span className={`stream-beacon stream-${streamState}`} />{events.length > 8 && <button type="button" className="rail-density-toggle" aria-expanded={eventHistoryExpanded} onClick={() => setEventHistoryExpanded((value) => !value)}>{eventHistoryExpanded ? text('最近', 'RECENT') : text('历史', 'HISTORY')}</button>}</div>
          </div>
          {activityQuery.isError && <div className="activity-fault" role="alert"><CircleAlert size={13} /><span>{text('历史 ProductEvent read 读取失败；SSE 会继续尝试连接。', 'Historical ProductEvent read failed; SSE continues reconnect attempts.')}</span><button className="recovery-action" onClick={() => void activityQuery.refetch()}>{text('重试历史事件', 'RETRY EVENT HISTORY')}</button></div>}
          {events.length ? <RuntimeEventRail events={events} limit={eventHistoryExpanded ? 32 : 8} activeEventId={eventCue?.eventId ?? null} onFocus={(event) => { const state = eventState(event.event_type); if (state) setEventCue({ eventId: event.event_id, state }) }} /> : <EventRailBlueprint state={streamState} />}
          {!eventHistoryExpanded && events.length > 8 && <button type="button" className="rail-overflow-note event-overflow" onClick={() => setEventHistoryExpanded(true)}>+{events.length - 8} {text('更早事件', 'earlier events')}</button>}
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
  const navigate = useNavigate()
  return <div className="case-list-empty"><strong>{text('暂无调查记录', 'No investigations yet')}</strong><p>{text('针对漏洞、修复版本或关联事件发起调查。', 'Investigate a vulnerability, fix version, or related incident.')}</p><button className="recovery-action" onClick={() => navigate('/start?profile=VERIFY')}>{text('发起调查', 'START INVESTIGATION')}</button></div>
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
  return <div className="event-rail-blueprint"><div className="event-rail-state"><span /><strong>{state.toUpperCase()}</strong><small>{text('调查进展', 'INVESTIGATION ACTIVITY')}</small></div><p>{text('暂无活动记录。调查开始后，进展会自动出现在这里。', 'No activity yet. Progress appears here as the investigation runs.')}</p></div>
}
