import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'motion/react'
import { ArrowUp, ArrowUpRight, ChevronRight, CircleHelp, History, Layers, MessageSquarePlus, ScanLine, SlidersHorizontal, Square, X } from '../components/ui/icons'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { UiThemeProvider } from '../components/ui/theme'
import { ConversationTurn } from '../components/questions/ConversationTurn'
import { AuditRail } from '../components/questions/AuditRail'
import { QuestionDrawer } from '../components/questions/QuestionDrawer'
import { QuestionHistory } from '../components/questions/QuestionHistory'
import { QuestionWelcome } from '../components/questions/QuestionWelcome'
import { StreamedDecisionDraft } from '../components/questions/StreamedDecisionDraft'
import { EvidenceOverlay } from '../components/investigations/CaseSurfaces'
import { getAgentTask } from '../lib/api/agents'
import { getKnowledgeObject, searchIntelligence } from '../lib/api/intelligence'
import {
  getInvestigation, getInvestigationActivity, getQuestionSession,
  streamQuestion, type ProductRuntimeEvent,
} from '../lib/api/investigations'
import { useI18n } from '../lib/i18n'
import './questions-space.css'

const eventNames = [
  'started', 'status_changed', 'progress', 'finding_added', 'finding_changed',
  'conflict_changed', 'unknown_changed', 'evidence_need_changed', 'decision_ready',
  'waiting', 'completed', 'failed', 'canceled',
]

function readableTarget(value: string) {
  const urlStart = value.indexOf('https://')
  if (urlStart < 0) return value
  try {
    const url = new URL(value.slice(urlStart))
    const filename = decodeURIComponent(url.pathname.split('/').at(-1) ?? '')
      .replace(/\.(pdf|html?)$/i, '').replaceAll('-', ' ').trim()
    return filename || url.hostname
  } catch { return value }
}

export function QuestionsPage() {
  const { text } = useI18n()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const sessionId = params.get('session')
  const origin = params.get('origin')
  const originSpace = params.get('from')
  const incidentOrigin = origin?.startsWith('incident:') ? origin.slice('incident:'.length) : null
  const originPath = incidentOrigin
    ? `/intelligence?incident=${encodeURIComponent(incidentOrigin)}`
    : origin?.startsWith('object:')
      ? `/intelligence?object=${encodeURIComponent(origin.slice('object:'.length))}`
      : origin?.startsWith('cve:')
        ? `/intelligence?cve=${encodeURIComponent(origin.slice('cve:'.length))}`
    : origin?.startsWith('case:')
      ? `/investigations?case=${encodeURIComponent(origin.slice('case:'.length))}`
    : originSpace === 'world' && origin
      ? `/?story=${encodeURIComponent(origin)}`
      : null
  const selectedTurn = Number(params.get('turn')) || null
  const routeTarget = params.get('cve') ?? (params.get('object') ? `object:${params.get('object')}` : '')
  const routeQuestion = params.get('question') ?? ''
  const routeIdentity = JSON.stringify([sessionId, routeTarget, routeQuestion])
  const [previousRouteIdentity, setPreviousRouteIdentity] = useState(routeIdentity)
  const [target, setTarget] = useState(routeTarget)
  const [targetLabel, setTargetLabel] = useState('')
  const [searchTarget, setSearchTarget] = useState('')
  const [question, setQuestion] = useState(routeQuestion)
  const [showReasoning, setShowReasoning] = useState(false)
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [draftRaw, setDraftRaw] = useState('')
  const [reasoningRaw, setReasoningRaw] = useState('')
  const [completedReasoning, setCompletedReasoning] = useState<Record<string, string>>({})
  const [streamPhase, setStreamPhase] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [failedRunId, setFailedRunId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [evidence, setEvidence] = useState<string | null>(null)
  const [liveEvents, setLiveEvents] = useState<ProductRuntimeEvent[]>([])
  const [connectedCaseId, setConnectedCaseId] = useState<string | null>(null)
  const [auditOpen, setAuditOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(params.get('history') === '1')
  const transcriptRef = useRef<HTMLDivElement>(null)
  const latestTurnRef = useRef<string | null>(null)
  const reasoningBuffer = useRef('')
  const abortRef = useRef<AbortController | null>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const followBottomRef = useRef(true)

  useEffect(() => () => abortRef.current?.abort(), [])

  if (routeIdentity !== previousRouteIdentity) {
    setPreviousRouteIdentity(routeIdentity)
    setTarget(routeTarget)
    setTargetLabel('')
    setQuestion(routeQuestion)
  }

  const history = useInfiniteQuery({
    queryKey: ['question-session', sessionId, 'pages'],
    queryFn: ({ pageParam, signal }) => getQuestionSession(sessionId!, pageParam, signal),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: last => last.next_before_turn ?? undefined,
    enabled: Boolean(sessionId),
  })
  const turns = history.data?.pages.slice().reverse().flatMap(page => page.turns) ?? []
  const earliestTurn = turns[0]?.turn_index
  const { hasNextPage: hasEarlierTurns, isFetchingNextPage: fetchingEarlierTurns, isFetchNextPageError: earlierTurnsFailed, fetchNextPage: fetchEarlierTurns } = history
  const focusTurn = turns.find(turn => turn.turn_index === selectedTurn) ?? turns.at(-1) ?? null
  const targetObjectId = sessionId && focusTurn?.target_object_ids.length === 1 ? focusTurn.target_object_ids[0] : null
  const targetObject = useQuery({ queryKey: ['question-target-object', targetObjectId], queryFn: () => getKnowledgeObject(targetObjectId!), enabled: Boolean(targetObjectId) })
  useEffect(() => {
    const timer = window.setTimeout(() => setSearchTarget(target.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [target])
  const targetSearch = useQuery({
    queryKey: ['question-target-search', searchTarget],
    queryFn: () => searchIntelligence(searchTarget, 5),
    enabled: !sessionId && !busy && searchTarget.length > 1 && !/^object:/i.test(searchTarget) && !/^CVE-\d{4}-\d+$/i.test(searchTarget),
    retry: false,
  })
  const resolvedTarget = targetObject.data?.external_identifiers.cve?.[0]
    ?? (typeof targetObject.data?.properties.display_name === 'string' ? targetObject.data.properties.display_name : null)
    ?? (typeof targetObject.data?.properties.title === 'string' ? targetObject.data.properties.title : null)
    ?? (targetObject.data?.canonical_key ? readableTarget(targetObject.data.canonical_key) : null)
  const visibleTarget = targetLabel || (sessionId ? resolvedTarget : null) || target || (targetObjectId ? `object:${targetObjectId}` : '')
  const caseId = focusTurn?.investigation_ref?.replace(/^case:/, '') ?? params.get('case')
  const caseActivity = useQuery({ queryKey: ['question-case-activity', caseId], queryFn: () => getInvestigationActivity(caseId!), enabled: Boolean(caseId), retry: false })
  const runIds = [...new Set((failedRunId ? [failedRunId] : [
    focusTurn?.context_id?.replace(/^context:/, ''),
    ...(caseActivity.data?.events ?? []).map(item => item.task_run_id),
    ...liveEvents.filter(item => item.case_id === caseId).map(item => item.task_run_id),
  ]).filter((id): id is string => Boolean(id)))]
  const taskQueries = useQueries({ queries: runIds.map(id => ({ queryKey: ['question-task', id], queryFn: () => getAgentTask(id), retry: false })) })
  const tasks = taskQueries.flatMap(query => query.data ? [query.data] : [])
  const turnRunIds = new Set<string>()
  if (focusTurn) {
    for (const task of tasks) {
      if (task.task.request_id === focusTurn.request_id
        || focusTurn.context_id === `context:${task.task.run_id}`) turnRunIds.add(task.task.run_id)
    }
    let changed = true
    while (changed) {
      changed = false
      for (const task of tasks) {
        if (!turnRunIds.has(task.task.run_id)
          && (turnRunIds.has(task.task.parent_run_id ?? '')
            || turnRunIds.has(task.task.predecessor_run_id ?? ''))) {
          turnRunIds.add(task.task.run_id)
          changed = true
        }
      }
    }
  }
  const auditTasks = failedRunId ? tasks : tasks.filter(task => turnRunIds.has(task.task.run_id))
  const caseDetail = useQuery({ queryKey: ['question-case', caseId], queryFn: () => getInvestigation(caseId!), enabled: Boolean(caseId), refetchInterval: query => ['active', 'waiting'].includes(query.state.data?.status ?? '') ? 4000 : false })
  const auditEventMap = new Map<string, ProductRuntimeEvent>()
  for (const item of [...(caseActivity.data?.events ?? []), ...liveEvents.filter(event => event.case_id === caseId)]) auditEventMap.set(item.event_id, item)
  const auditEvents = [...auditEventMap.values()].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
  const turnAuditEvents = auditEvents.filter(event => event.task_run_id && turnRunIds.has(event.task_run_id))
  const streamConnected = Boolean(caseId && connectedCaseId === caseId)

  useEffect(() => {
    if (selectedTurn && earliestTurn && selectedTurn < earliestTurn
      && hasEarlierTurns && !fetchingEarlierTurns && !earlierTurnsFailed) {
      void fetchEarlierTurns()
    }
  }, [selectedTurn, earliestTurn, hasEarlierTurns, fetchingEarlierTurns, earlierTurnsFailed, fetchEarlierTurns])

  useEffect(() => {
    if (!caseId) return
    const source = new EventSource(`/api/v1/investigations/${encodeURIComponent(caseId)}/events`)
    source.onopen = () => setConnectedCaseId(caseId)
    source.onerror = () => setConnectedCaseId(current => current === caseId ? null : current)
    const onEvent = (message: MessageEvent<string>) => {
      try {
        const item = JSON.parse(message.data) as ProductRuntimeEvent
        setLiveEvents(current => current.some(event => event.event_id === item.event_id) ? current : [...current, item])
        if (item.task_run_id) void queryClient.invalidateQueries({ queryKey: ['question-case-activity', caseId] })
        if (['decision_ready', 'completed', 'failed', 'canceled'].includes(item.event_type)) {
          void queryClient.invalidateQueries({ queryKey: ['question-case', caseId] })
          void queryClient.invalidateQueries({ queryKey: ['question-case-activity', caseId] })
          void queryClient.invalidateQueries({ queryKey: ['question-session', sessionId, 'pages'] })
        }
      } catch { /* A malformed event must not stop the stream. */ }
    }
    eventNames.forEach(name => source.addEventListener(name, onEvent as EventListener))
    return () => { eventNames.forEach(name => source.removeEventListener(name, onEvent as EventListener)); source.close() }
  }, [caseId, queryClient, sessionId])

  const latestTurnIndex = turns.at(-1)?.turn_index ?? null
  const latestTurnKey = sessionId && latestTurnIndex !== null ? `${sessionId}:${latestTurnIndex}` : null
  useEffect(() => {
    const transcript = transcriptRef.current
    if (transcript) {
      if (!sessionId) transcript.scrollTop = 0
      else if (pendingQuestion || (latestTurnKey !== null && latestTurnKey !== latestTurnRef.current)) {
        transcript.scrollTop = transcript.scrollHeight
      }
    }
    latestTurnRef.current = latestTurnKey
  }, [sessionId, latestTurnKey, pendingQuestion])

  async function submit() {
    const prompt = question.trim()
    if (!prompt || busy) return
    const cve = target.trim().toUpperCase()
    const objectId = target.trim().match(/^object:(.+)$/i)?.[1]?.trim()
    if (!sessionId && target.trim() && !/^CVE-\d{4}-\d+$/.test(cve) && !objectId) {
      setError(text('请从搜索结果选择对象，或输入完整 CVE 编号。', 'Choose an object from the search results or enter a complete CVE ID.'))
      return
    }
    const controller = new AbortController()
    abortRef.current = controller
    followBottomRef.current = true
    setBusy(true)
    setError('')
    setPendingQuestion(prompt)
    setFailedRunId(null)
    setDraftRaw('')
    setReasoningRaw('')
    setReasoningOpen(showReasoning)
    reasoningBuffer.current = ''
    setStreamPhase('connecting')
    try {
      const result = await streamQuestion({
        question: prompt,
        sessionId: sessionId ?? undefined,
        cveId: !sessionId && /^CVE-\d{4}-\d+$/.test(cve) ? cve : undefined,
        objectId: !sessionId ? objectId : undefined,
        interactiveTimeoutSeconds: 90,
      }, {
        includeReasoning: showReasoning,
        signal: controller.signal,
        onEvent: event => {
          if (event.event === 'status') setStreamPhase(event.phase)
          if (event.event === 'model_delta') {
            if (event.kind === 'content') setDraftRaw(current => current + event.text)
            if (event.kind === 'reasoning') {
              reasoningBuffer.current += event.text
              setReasoningRaw(reasoningBuffer.current)
            }
          }
        },
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['account-conversations'] }),
        queryClient.invalidateQueries({ queryKey: ['question-session', result.session_id] }),
      ])
      const next = new URLSearchParams()
      if (origin && originSpace && originPath) {
        next.set('origin', origin)
        next.set('from', originSpace)
        if (params.get('targetLabel')) next.set('targetLabel', params.get('targetLabel')!)
      }
      next.set('session', result.session_id)
      next.set('turn', String(result.turn_index))
      if (target.trim()) next.set(objectId ? 'object' : 'cve', objectId ?? cve)
      if (result.mode === 'accepted' && result.investigation) next.set('case', result.investigation.case_id)
      if (result.mode === 'completed' && result.decision) next.set('decision', result.decision.decision_id)
      if (reasoningBuffer.current) setCompletedReasoning(current => ({ ...current, [`${result.session_id}:${result.turn_index}`]: reasoningBuffer.current }))
      setParams(next, { replace: true })
      setQuestion('')
      setPendingQuestion('')
      setStreamPhase('')
    } catch (exc) {
      if (controller.signal.aborted) {
        setError(text('已停止接收。后台任务可能仍在运行，稍后可在历史对话中查看。', 'Stopped receiving. The task may still be running; check your history for its result.'))
        setPendingQuestion('')
        setDraftRaw('')
        setReasoningRaw('')
        setStreamPhase('')
        void queryClient.invalidateQueries({ queryKey: ['account-conversations'] })
        return
      }
      setError(exc instanceof Error ? exc.message : text('问答请求失败', 'Question failed'))
      setFailedRunId(exc && typeof exc === 'object' && 'runId' in exc && typeof exc.runId === 'string' ? exc.runId : null)
      setStreamPhase('failed')
    } finally { abortRef.current = null; setBusy(false) }
  }

  function newConversation() {
    if (busy) return
    setHistoryOpen(false)
    setAuditOpen(false)
    setParams(new URLSearchParams(), { replace: false })
    setQuestion('')
    setTarget('')
    setTargetLabel('')
    setPendingQuestion('')
    setFailedRunId(null)
    setDraftRaw('')
    setReasoningRaw('')
    setCompletedReasoning({})
    setError('')
    window.setTimeout(() => composerRef.current?.focus(), 0)
  }

  useEffect(() => {
    const viewport = transcriptRef.current
    const content = viewport?.firstElementChild
    if (!viewport || !content) return
    const observer = new ResizeObserver(() => {
      if (followBottomRef.current && pendingQuestion) viewport.scrollTop = viewport.scrollHeight
    })
    observer.observe(content)
    return () => observer.disconnect()
  }, [pendingQuestion])

  const isNewConversation = !sessionId && !pendingQuestion

  return <UiThemeProvider theme="dark"><section className="qa-workspace ui-night dark">
    <header className="qa-heading">
      <Button variant="ghost" className="qa-icon-button" onClick={() => setHistoryOpen(true)} disabled={busy} aria-label={text('历史对话', 'Conversation history')}><History size={20} /></Button>
      <div className="qa-heading-title"><h1>{text('问答', 'Ask SecFusion')}</h1><span>SecFusion</span></div>
      <Button variant="ghost" className="qa-new-button" aria-label={text('新对话', 'New chat')} onClick={newConversation} disabled={busy}><MessageSquarePlus size={18} /><span>{text('新对话', 'New chat')}</span></Button>
    </header>
    <main className={`qa-dialogue ${isNewConversation ? 'is-new' : 'has-conversation'}`}>
        <div className="qa-transcript" ref={transcriptRef} onScroll={event => { const node = event.currentTarget; followBottomRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 100 }}><div className="qa-transcript-content">
          {originPath && <div className="qa-origin"><Layers size={18} /><div><small>{originSpace === 'case' ? text('沿着这次调查继续', 'Continue this investigation') : text('从情报继续探索', 'Continue from intelligence')}</small><strong>{params.get('originTitle') || params.get('targetLabel') || incidentOrigin || origin}</strong></div><Link to={originPath}>{originSpace === 'case' ? text('返回调查', 'Back to investigation') : text('查看来源', 'Source')}<ArrowUpRight size={13} /></Link></div>}
          {history.hasNextPage && <button className="qa-load-more qa-load-turns" onClick={() => void history.fetchNextPage()} disabled={history.isFetchingNextPage}>{history.isFetchingNextPage ? text('正在恢复更早回合…', 'Restoring earlier turns…') : text('查看更早回合', 'Load earlier turns')}</button>}
          {history.isFetchNextPageError && <button className="qa-retry" onClick={() => void history.fetchNextPage()}>{text('重试恢复更早回合', 'Retry earlier turns')}</button>}
          {history.isLoading && <p className="qa-muted">{text('恢复完整会话…', 'Restoring conversation…')}</p>}
          {history.isError && <div className="qa-error">{text('无法读取这段会话。', 'Could not load this conversation.')}<button onClick={() => void history.refetch()}>{text('重试', 'Retry')}</button></div>}
          {isNewConversation && <QuestionWelcome onSelect={prompt => { setQuestion(prompt); composerRef.current?.focus() }} />}

          {turns.map(turn => <ConversationTurn key={turn.turn_index} turn={turn} active={!failedRunId && focusTurn?.turn_index === turn.turn_index} sessionId={sessionId!} reasoning={completedReasoning[`${sessionId}:${turn.turn_index}`] ?? null} onSelect={() => { setFailedRunId(null); setAuditOpen(true); const next = new URLSearchParams(params); next.set('turn', String(turn.turn_index)); setParams(next, { replace: true }) }} onEvidence={setEvidence} />)}
          {pendingQuestion && <div className="qa-turn qa-turn-pending"><div className="qa-question"><small>{text('你 · 当前回合', 'YOU · CURRENT TURN')}</small><p>{pendingQuestion}</p></div><StreamedDecisionDraft draftRaw={draftRaw} reasoningRaw={reasoningRaw} reasoningOpen={reasoningOpen} onReasoningOpen={setReasoningOpen} phase={streamPhase} /></div>}
        </div></div>
        <div className="qa-compose">
          <div className="qa-composer-card">
            {visibleTarget && <div className="qa-target-chip"><Layers size={13} /><span>{visibleTarget}</span>{!sessionId && <button type="button" onClick={() => { setTarget(''); setTargetLabel('') }} aria-label={text('取消对象限定', 'Remove target scope')}><X size={13} /></button>}</div>}
            <label className="qa-question-input"><span className="qa-sr-only">{text('向 SecFusion 提问', 'Ask SecFusion')}</span><textarea ref={composerRef} value={question} onChange={event => setQuestion(event.target.value)} disabled={busy} rows={2} placeholder={text('问一个安全问题，或继续你的探索…', 'Ask a security question, or follow your curiosity…')} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit() } }} /></label>
            <div className="qa-composer-toolbar">
              <details className="qa-options"><summary><SlidersHorizontal size={15} />{text('自动', 'Auto')}<ChevronRight size={12} /></summary>
                <div className="qa-options-panel"><h3>{text('回答选项', 'Answer options')}</h3><p>{text('根据你的问题，自动检索、核验或展开调查。', 'Your question guides retrieval, verification, or a deeper investigation.')}</p>
                  <label className="qa-reasoning-choice"><input type="checkbox" checked={showReasoning} onChange={event => setShowReasoning(event.target.checked)} disabled={busy} />{text('显示模型推理（如有）', 'Show model reasoning, if available')}</label>
                  {!sessionId && <label className="qa-target"><span>{text('限定对象（可选）', 'Focus on an object (optional)')}</span><Input value={visibleTarget} onChange={event => { setTarget(event.target.value); setTargetLabel('') }} disabled={busy} placeholder={text('搜索对象或输入 CVE', 'Search an object or enter a CVE')} aria-label={text('查找调查对象', 'Find a question target')} /></label>}
                  {targetSearch.isFetching && <p role="status">{text('正在查找情报对象…', 'Finding objects…')}</p>}
                  {targetSearch.isError && <button className="qa-retry" onClick={() => void targetSearch.refetch()}>{text('重试对象检索', 'Retry target search')}</button>}
                  {targetSearch.data && !targetLabel && searchTarget === target.trim() && <div className="qa-target-results">{targetSearch.data.items.map(item => <button key={item.object_id} onClick={() => { setTarget(`object:${item.object_id}`); setTargetLabel(item.label) }}><Layers size={16} /><span>{item.label}</span><ArrowUpRight size={13} /></button>)}{!targetSearch.data.items.length && <p>{text('未找到匹配对象。', 'No matching objects.')}</p>}</div>}
                </div>
              </details>
              <span className="qa-composer-hint">{busy ? text('正在探索证据', 'Exploring the evidence') : text('Enter 发送 · Shift + Enter 换行', 'Enter to send · Shift + Enter for a new line')}</span>
              {busy ? <Button variant="ghost" className="qa-send qa-stop" onClick={() => abortRef.current?.abort()} aria-label={text('停止接收回答', 'Stop receiving answer')} title={text('停止接收回答', 'Stop receiving answer')}><Square size={15} fill="currentColor" /></Button> : <Button variant="ghost" className="qa-send" onClick={() => void submit()} disabled={!question.trim()} aria-label={text('发送问题', 'Send question')}><ArrowUp size={22} /></Button>}
            </div>
          </div>
          {error && <div className="qa-error" role="alert"><CircleHelp size={15} /><span>{error}</span>{failedRunId && <button onClick={() => setAuditOpen(true)}>{text('查看过程', 'View process')}</button>}</div>}
          <p className="qa-compose-note"><ScanLine size={12} />{text('让每个结论，都有据可查。', 'Every conclusion starts with evidence.')}</p>
        </div>
      </main>
      <QuestionDrawer open={historyOpen} onOpenChange={setHistoryOpen} title={text('历史对话', 'Conversation history')} description={text('从之前的问题继续探索。', 'Pick up where you left off.')} side="left">
        <QuestionHistory sessionId={sessionId} onSelect={() => setHistoryOpen(false)} onNew={newConversation} />
      </QuestionDrawer>
      <QuestionDrawer open={auditOpen} onOpenChange={setAuditOpen} title={text('运行过程', 'Behind the answer')} description={text('查看这个回合的证据、任务和上下文。', 'Evidence, tasks, and context for this turn.')} side="right">

      {auditOpen && <AuditRail turn={failedRunId ? null : focusTurn} failedRunId={failedRunId} tasks={auditTasks} taskLoading={taskQueries.some(query => query.isLoading)} taskReadFailed={taskQueries.some(query => query.isError)} onRetryTasks={() => taskQueries.forEach(query => { if (query.isError) void query.refetch() })} caseId={failedRunId ? null : caseId} caseStatus={caseDetail.data?.status} caseEvents={failedRunId ? [] : turnAuditEvents} caseActivityLoading={caseActivity.isLoading} caseActivityFailed={caseActivity.isError} onRetryActivity={() => void caseActivity.refetch()} streamConnected={streamConnected} onEvidence={setEvidence} /> }
      </QuestionDrawer>
    <AnimatePresence>{evidence && <EvidenceOverlay key={evidence} evidenceRef={evidence} onClose={() => setEvidence(null)} />}</AnimatePresence>
  </section></UiThemeProvider>
}
