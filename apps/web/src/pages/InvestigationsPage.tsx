import { ProductGlyph } from '../components/instrument/ProductGlyph'
import { SpaceHeading } from '../components/instrument/SpaceHeading'
import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  BadgeCheck,
  CircleAlert,
  FileWarning,
  MessageSquareText,
  SearchCheck,
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
const LIVE_ACTIVITY_MAX_AGE_MS = 30 * 60 * 1000

function hasRecentRuntimeActivity(item: { status: string; current_activity: { updated_at: string | null } }) {
  if (!liveStatuses.has(item.status) || !item.current_activity.updated_at) return false
  return Date.now() - new Date(item.current_activity.updated_at).getTime() <= LIVE_ACTIVITY_MAX_AGE_MS
}

function isStalledRuntime(item: { status: string; current_activity: { updated_at: string | null } }) {
  return liveStatuses.has(item.status) && !hasRecentRuntimeActivity(item)
}

export function InvestigationsPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const listQuery = useInfiniteQuery({
    queryKey: ['investigations'],
    queryFn: ({ pageParam }) => listInvestigations(48, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: page => page.has_more ? page.next_cursor ?? undefined : undefined,
    refetchInterval: 20_000,
  })
  const preferredCase = params.get('case')
  const sessionParam = params.get('session')
  const origin = params.get('from')
  const originRun = params.get('run')
  const focusParam = params.get('focus')
  const evidenceParam = params.get('evidence')
  const listedCases = useMemo(() => listQuery.data?.pages.flatMap(page => page.items) ?? [], [listQuery.data?.pages])
  const fallbackCase = listedCases.find(hasRecentRuntimeActivity)?.case_id ?? listedCases[0]?.case_id ?? null
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
  const cases = useMemo(() => selected && !listedCases.some(item => item.case_id === selected.case_id)
    ? [selected, ...listedCases] : listedCases, [listedCases, selected])
  const liveCount = cases.filter(hasRecentRuntimeActivity).length
  const stalledCount = cases.filter(isStalledRuntime).length
  const visibleCases = useMemo(() => {
    if (caseArchiveExpanded) return cases
    const selectedItem = cases.find((item) => item.case_id === selectedCase)
    const ordered = [
      ...(selectedItem ? [selectedItem] : []),
      ...cases.filter((item) => item.case_id !== selectedCase && hasRecentRuntimeActivity(item)),
      ...cases.filter((item) => item.case_id !== selectedCase && !hasRecentRuntimeActivity(item)),
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
    <section className={`investigations-space studio-investigations investigations-page ${selected ? 'has-case' : 'case-index-only'}`}>
      <SpaceHeading index="03" eyebrow="INVESTIGATIONS / CONTINUITY" title={text('持续调查', 'Investigations')} description={text('已确认、冲突与缺口，在同一个调查里持续推进。', 'Findings, conflicts and evidence gaps stay together in one continuing investigation.')}>
        <div className="investigation-status-brief">
          <p>{text(
            `最近载入 ${cases.length} 个调查 · ${liveCount} 个近期有活动${stalledCount ? ` · ${stalledCount} 个长期未更新` : ''}。`,
            `${cases.length} investigation cases loaded. ${liveCount} have runtime activity within the last 30 minutes${stalledCount ? `; ${stalledCount} more still carry an active/waiting durable state but have not advanced for a long time, so the Product treats them as stalled while retaining them for diagnosis` : ''}. Selecting a case restores its activity from durable history and SSE.`,
          )}</p>
          <span className={`stream-state stream-${streamState}`}><RadioState state={streamState} /> {streamState.toUpperCase()}</span>
        </div>
      </SpaceHeading>
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
        <details className="vision-case-index"><summary><SearchCheck size={16}/>{text("切换调查", "Switch investigation")}<span>{text(`${cases.length} 个已载入调查`, `${cases.length} loaded cases`)}</span></summary><aside className="case-rail">
          <div className="case-rail-head">
            <SearchCheck size={15} />
            <strong>{text('调查记录', 'CASE FILES')}</strong>
            <span>{cases.length}</span>
            {cases.length > 6 && <button type="button" className="rail-density-toggle" aria-expanded={caseArchiveExpanded} onClick={() => setCaseArchiveExpanded((value) => !value)}>{caseArchiveExpanded ? text('收起', 'COLLAPSE') : text('展开已载入', 'EXPAND LOADED')}</button>}
          </div>
          {listQuery.isError && !listQuery.isFetchNextPageError && (
            <div className="case-index-fault" role="alert">
              <CircleAlert size={14} />
              <div><small>{text('CASE 索引读取失败', 'CASE INDEX READ ERROR')}</small><strong>{text('durable Case 索引读取失败。', 'The durable Case index read failed.')}</strong></div>
              <button className="recovery-action" onClick={() => void listQuery.refetch()}>{text('重试 Case 索引', 'RETRY CASE INDEX')}</button>
            </div>
          )}
          <div className="case-list">
            {visibleCases.map((item) => (
              <button key={item.case_id} className={`case-card ${item.case_id === selectedCase ? 'selected' : ''} case-${item.status} ${isStalledRuntime(item) ? 'case-stalled' : ''}`} onClick={() => selectCase(item.case_id)}>
                <span className="case-status-dot" />
                <span className="case-card-copy"><small>{item.execution_profile ?? item.current_activity.task_kind ?? 'INVESTIGATION'} · {item.origin_scope.toUpperCase()}</small><strong>{item.goal}</strong><em>{isStalledRuntime(item) ? text('运行时长期未更新；保留供诊断', 'Runtime has not advanced recently; retained for diagnosis') : `${item.current_activity.actor_role ?? 'runtime'} · ${item.current_activity.phase}`}</em></span>
                <span className="case-card-tail"><b>{isStalledRuntime(item) ? text('停滞', 'stalled') : item.status}</b></span>
              </button>
            ))}
            {!caseArchiveExpanded && cases.length > visibleCases.length && <button type="button" className="rail-overflow-note" onClick={() => setCaseArchiveExpanded(true)}>+{cases.length - visibleCases.length} {text('历史 Case', 'archived cases')}</button>}
            {listQuery.hasNextPage && <button type="button" className="rail-overflow-note" disabled={listQuery.isFetchingNextPage} onClick={() => { setCaseArchiveExpanded(true); void listQuery.fetchNextPage() }}>{listQuery.isFetchingNextPage ? text('读取更早调查…', 'Loading older cases…') : text('载入更早调查', 'Load older cases')}</button>}
            {listQuery.isFetchNextPageError && <button type="button" className="rail-overflow-note" onClick={() => void listQuery.fetchNextPage()}>{text('重试载入更早调查', 'Retry older cases')}</button>}
            {listQuery.isLoading && <div className="case-list-empty">{text('加载 durable Cases…', 'Loading durable cases…')}</div>}
            {!listQuery.isLoading && cases.length === 0 && <CaseRailBlueprint />}
          </div>
        </aside></details>

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

        <aside className="activity-rail"><div id="case-conversation-mount" /><details className="case-events-fold"><summary>{text('执行事件', 'Execution events')} <span>{events.length}</span></summary>
          <div className="activity-head">
            <div><small>{text('产品事件流', 'PRODUCT EVENT STREAM')}</small><strong>{text('实时活动', 'LIVE ACTIVITY')}</strong></div>
            <div className="activity-head-actions"><span className={`stream-beacon stream-${streamState}`} />{events.length > 8 && <button type="button" className="rail-density-toggle" aria-expanded={eventHistoryExpanded} onClick={() => setEventHistoryExpanded((value) => !value)}>{eventHistoryExpanded ? text('最近', 'RECENT') : text('历史', 'HISTORY')}</button>}</div>
          </div>
          {activityQuery.isError && <div className="activity-fault" role="alert"><CircleAlert size={13} /><span>{text('历史 ProductEvent read 读取失败；SSE 会继续尝试连接。', 'Historical ProductEvent read failed; SSE continues reconnect attempts.')}</span><button className="recovery-action" onClick={() => void activityQuery.refetch()}>{text('重试历史事件', 'RETRY EVENT HISTORY')}</button></div>}
          {events.length ? <RuntimeEventRail events={events} limit={eventHistoryExpanded ? events.length : 8} activeEventId={eventCue?.eventId ?? null} onFocus={(event) => { const state = eventState(event.event_type); if (state) setEventCue({ eventId: event.event_id, state }) }} onEvidence={setSelectedEvidence} /> : <EventRailBlueprint state={streamState} />}
          {!eventHistoryExpanded && events.length > 8 && <button type="button" className="rail-overflow-note event-overflow" onClick={() => setEventHistoryExpanded(true)}>+{events.length - 8} {text('更早事件', 'earlier events')}</button>}
        </details></aside>
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
  const navigate = useNavigate()
  const states = [
    { label: text('已确认', 'CONFIRMED'), tone: 'lime', icon: BadgeCheck, copy: text('证据边界内的已证事实', 'evidence-bounded findings') },
    { label: text('冲突', 'CONFLICTS'), tone: 'amber', icon: CircleAlert, copy: text('保留来源分歧与张力', 'preserved source tension') },
    { label: text('未知', 'UNKNOWNS'), tone: 'violet', icon: FileWarning, copy: text('明确记录未决边界', 'explicit uncertainty') },
    { label: text('证据需求', 'EVIDENCE NEEDS'), tone: 'cyan', icon: SearchCheck, copy: text('下一步待获取证据', 'open acquisition gaps') },
  ]
  return (
    <div className="case-empty-experience">
      <div className="case-empty-intro">
        <ProductGlyph kind="investigations" size={36} />
        <small>{text('调查工作台', 'INVESTIGATION WORKSPACE')}</small>
        <h2>{loading ? text('正在读取调查记录', 'Reading your investigations') : text('从一个待核验的问题开始', 'Start with a question worth verifying.')}</h2>
        <p>{text('每次调查都会把证据、已确认事实、冲突与未解问题留在同一个 Case 中。之后的追问可以沿着这条线索继续。', 'An investigation keeps evidence, confirmed findings, conflicts and open questions in one Case. Follow-up questions can continue along the same trail.')}</p>
        {!loading && <button type="button" onClick={() => navigate('/start?profile=VERIFY')}><SearchCheck size={16} />{text('发起核验', 'Start verification')}</button>}
      </div>
      <div className="case-empty-preview">
        <div className="case-empty-preview-head"><small>{text('一个 Case 会持续整理', 'WHAT A CASE KEEPS TOGETHER')}</small><span>ARGUS → ORACLE</span></div>
        <div className="case-empty-states">
          {states.map(({ label, tone, icon: Icon, copy }) => (
            <div key={label} className={'case-empty-state tone-' + tone}>
              <Icon size={17} /><strong>{label}</strong><span>{copy}</span>
            </div>
          ))}
        </div>
        <div className="case-empty-continuity"><MessageSquareText size={19} /><p>{text('调查开始后，活动、决策和证据引用会在这里持续更新。', 'Once work begins, activity, decisions and evidence links will keep updating here.')}</p></div>
      </div>
    </div>
  )
}

function EventRailBlueprint({ state }: { state: string }) {
  const { text } = useI18n()
  return <div className="event-rail-blueprint"><div className="event-rail-state"><span /><strong>{state.toUpperCase()}</strong><small>{text('调查进展', 'INVESTIGATION ACTIVITY')}</small></div><p>{text('暂无活动记录。调查开始后，进展会自动出现在这里。', 'No activity yet. Progress appears here as the investigation runs.')}</p></div>
}
