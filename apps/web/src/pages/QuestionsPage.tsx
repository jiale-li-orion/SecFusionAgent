import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'motion/react'
import { ArrowUpRight, ChevronRight, CornerDownLeft, Link2, Plus, Radio, Send, ShieldCheck } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { DecisionReport } from '../components/DecisionReport'
import { EvidenceOverlay } from '../components/investigations/CaseSurfaces'
import { InvestigationReport } from '../components/investigations/InvestigationReport'
import { getAgentTask, type AgentTaskDetail } from '../lib/api/agents'
import { getKnowledgeObject } from '../lib/api/intelligence'
import {
  getDecision, getInvestigation, getInvestigationActivity, getQuestionSession,
  listAccountConversations, streamQuestion, type ProductRuntimeEvent,
  type DecisionView, type QuestionSessionTurn, type TaskKind,
} from '../lib/api/investigations'
import { useI18n } from '../lib/i18n'
import './questions-space.css'

const profiles: Array<{ id: string; task: TaskKind; zh: string; en: string; description: string }> = [
  { id: 'DIRECT', task: 'lookup', zh: '快速回答', en: 'Direct', description: '从当前已确认事实回答' },
  { id: 'RETRIEVE', task: 'retrieve', zh: '证据检索', en: 'Retrieve', description: '扩展本地证据上下文' },
  { id: 'VERIFY', task: 'verify_version_fix', zh: '精准核验', en: 'Verify', description: '核对版本、修复与冲突' },
  { id: 'INVESTIGATE', task: 'investigate_incident', zh: '深度调查', en: 'Investigate', description: '多步 Agent 调查' },
  { id: 'WATCH', task: 'watch_incident', zh: '持续守望', en: 'Watch', description: '等待世界变化后继续' },
]

const eventNames = [
  'started', 'status_changed', 'progress', 'finding_added', 'finding_changed',
  'conflict_changed', 'unknown_changed', 'evidence_need_changed', 'decision_ready',
  'waiting', 'completed', 'failed', 'canceled',
]

function profileForTask(task: string) {
  return profiles.find(item => item.task === task)?.id ?? 'INVESTIGATE'
}

function previewStatement(raw: string): string {
  const matches = [...raw.matchAll(/"statement"\s*:\s*"/g)]
  const last = matches.at(-1)
  if (!last || last.index === undefined) return ''
  let escaped = false
  let text = ''
  for (const char of raw.slice(last.index + last[0].length)) {
    if (escaped) {
      text += char === 'n' ? '\n' : char === 't' ? ' ' : char
      escaped = false
    } else if (char === '\\') escaped = true
    else if (char === '"') break
    else text += char
  }
  return text
}

function formatTime(value: string, language: string) {
  return new Date(value).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function QuestionsPage() {
  const { text, language } = useI18n()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const sessionId = params.get('session')
  const selectedTurn = Number(params.get('turn')) || null
  const initialProfile = params.get('profile')?.toUpperCase() ?? 'RETRIEVE'
  const routeTarget = params.get('cve') ?? (params.get('object') ? `object:${params.get('object')}` : '')
  const routeQuestion = params.get('question') ?? ''
  const routeIdentity = JSON.stringify([sessionId, initialProfile, routeTarget, routeQuestion])
  const [previousRouteIdentity, setPreviousRouteIdentity] = useState(routeIdentity)
  const [profile, setProfile] = useState(profiles.some(item => item.id === initialProfile) ? initialProfile : 'RETRIEVE')
  const [target, setTarget] = useState(routeTarget)
  const [question, setQuestion] = useState(routeQuestion)
  const [showReasoning, setShowReasoning] = useState(false)
  const [reasoningOpen, setReasoningOpen] = useState(false)
  const [draftRaw, setDraftRaw] = useState('')
  const [reasoningRaw, setReasoningRaw] = useState('')
  const [completedReasoning, setCompletedReasoning] = useState<Record<string, string>>({})
  const [streamPhase, setStreamPhase] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [evidence, setEvidence] = useState<string | null>(null)
  const [liveEvents, setLiveEvents] = useState<ProductRuntimeEvent[]>([])
  const [connectedCaseId, setConnectedCaseId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const reasoningBuffer = useRef('')

  if (routeIdentity !== previousRouteIdentity) {
    setPreviousRouteIdentity(routeIdentity)
    setProfile(profiles.some(item => item.id === initialProfile) ? initialProfile : 'RETRIEVE')
    setTarget(routeTarget)
    setQuestion(routeQuestion)
  }

  const conversations = useInfiniteQuery({
    queryKey: ['account-conversations', 'pages'],
    queryFn: ({ pageParam, signal }) => listAccountConversations(20, signal, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: last => last.next_cursor ?? undefined,
  })
  const conversationItems = conversations.data?.pages.flatMap(page => page.items) ?? []
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
  const targetObject = useQuery({ queryKey: ['question-target-object', targetObjectId], queryFn: () => getKnowledgeObject(targetObjectId!), enabled: Boolean(targetObjectId && !target) })
  const resolvedTarget = targetObject.data?.external_identifiers.cve?.[0]
    ?? (typeof targetObject.data?.properties.display_name === 'string' ? targetObject.data.properties.display_name : null)
    ?? targetObject.data?.canonical_key
  const visibleTarget = target || resolvedTarget || (targetObjectId ? `object:${targetObjectId}` : '')
  const caseId = focusTurn?.investigation_ref?.replace(/^case:/, '') ?? params.get('case')
  const caseActivity = useQuery({ queryKey: ['question-case-activity', caseId], queryFn: () => getInvestigationActivity(caseId!), enabled: Boolean(caseId), retry: false })
  const runIds = [...new Set([
    focusTurn?.context_id?.replace(/^context:/, ''),
    ...(caseActivity.data?.events ?? []).map(item => item.task_run_id),
  ].filter((id): id is string => Boolean(id)))]
  const taskQueries = useQueries({ queries: runIds.map(id => ({ queryKey: ['question-task', id], queryFn: () => getAgentTask(id), retry: false })) })
  const tasks = taskQueries.flatMap(query => query.data ? [query.data] : [])
  const caseDetail = useQuery({ queryKey: ['question-case', caseId], queryFn: () => getInvestigation(caseId!), enabled: Boolean(caseId), refetchInterval: query => ['active', 'waiting'].includes(query.state.data?.status ?? '') ? 4000 : false })
  const auditEventMap = new Map<string, ProductRuntimeEvent>()
  for (const item of [...(caseActivity.data?.events ?? []), ...liveEvents.filter(event => event.case_id === caseId)]) auditEventMap.set(item.event_id, item)
  const auditEvents = [...auditEventMap.values()].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
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
        if (['decision_ready', 'completed', 'failed', 'canceled'].includes(item.event_type)) {
          void queryClient.invalidateQueries({ queryKey: ['question-case', caseId] })
        }
      } catch { /* A malformed event must not stop the stream. */ }
    }
    eventNames.forEach(name => source.addEventListener(name, onEvent as EventListener))
    return () => { eventNames.forEach(name => source.removeEventListener(name, onEvent as EventListener)); source.close() }
  }, [caseId, queryClient])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns.length, pendingQuestion])

  async function submit() {
    const prompt = question.trim()
    if (!prompt || busy) return
    const selected = profiles.find(item => item.id === profile) ?? profiles[1]
    const cve = target.trim().toUpperCase()
    const objectId = target.trim().match(/^object:(.+)$/i)?.[1]?.trim()
    if (!sessionId && selected.id !== 'RETRIEVE' && !/^CVE-\d{4}-\d+$/.test(cve) && !objectId) {
      setError(text('请选择 CVE 或 object:<id> 作为调查目标。', 'Select a CVE or object:<id> as the target.'))
      return
    }
    setBusy(true)
    setError('')
    setPendingQuestion(prompt)
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
        taskKind: selected.task,
        interactiveTimeoutSeconds: 30,
      }, {
        includeReasoning: showReasoning,
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
      next.set('session', result.session_id)
      next.set('turn', String(result.turn_index))
      next.set('profile', profile)
      if (target.trim()) next.set(objectId ? 'object' : 'cve', objectId ?? cve)
      if (result.mode === 'accepted' && result.investigation) next.set('case', result.investigation.case_id)
      if (result.mode === 'completed' && result.decision) next.set('decision', result.decision.decision_id)
      if (reasoningBuffer.current) setCompletedReasoning(current => ({ ...current, [`${result.session_id}:${result.turn_index}`]: reasoningBuffer.current }))
      setParams(next, { replace: true })
      setQuestion('')
      setPendingQuestion('')
      setStreamPhase('')
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : text('问答请求失败', 'Question failed'))
      setStreamPhase('failed')
    } finally { setBusy(false) }
  }

  function newConversation() {
    setParams(new URLSearchParams(), { replace: false })
    setQuestion('')
    setTarget('')
    setProfile('RETRIEVE')
    setPendingQuestion('')
    setDraftRaw('')
    setReasoningRaw('')
    setCompletedReasoning({})
    setError('')
  }

  return <section className="qa-workspace">
    <header className="qa-heading">
      <div className="qa-heading-mark" aria-hidden="true"><span /><span /><span /></div>
      <div><small>03 / QUESTION INTELLIGENCE · M6</small><h1>{text('证据问答', 'Evidence Dialogue')}</h1><p>{text('提出问题，沿着证据、上下文与执行轨迹走到结论。', 'Ask a question and follow its evidence, context, and execution to the conclusion.')}</p></div>
      <span className="qa-heading-state"><Radio size={13} />{text('持续会话', 'CONTINUOUS SESSION')}</span>
    </header>

    <div className="qa-layout">
      <aside className="qa-sessions" aria-label={text('会话列表', 'Conversations')}>
        <div className="qa-rail-head"><small>YOUR WORKSPACE</small><button onClick={newConversation} aria-label={text('新建会话', 'New conversation')}><Plus size={17} /></button></div>
        <h2>{text('会话', 'Conversations')}</h2>
        {conversations.isLoading && <p className="qa-muted">{text('读取会话…', 'Loading conversations…')}</p>}
        {conversations.isError && <button className="qa-retry" onClick={() => void conversations.refetch()}>{text('重试读取', 'Retry')}</button>}
        <nav className="qa-session-list">{conversationItems.map(item => {
          const current = item.session_id === sessionId
          const next = new URLSearchParams({ session: item.session_id, turn: String(item.latest_turn.turn_index), profile: profileForTask(item.latest_turn.task_kind) })
          return <Link key={item.session_id} to={`/start?${next}`} className={current ? 'current' : ''}>
            <span>{item.latest_turn.question}</span><small>{formatTime(item.updated_at, language)}</small><ChevronRight size={13} />
          </Link>
        })}</nav>
        {conversations.hasNextPage && <button className="qa-load-more" onClick={() => void conversations.fetchNextPage()} disabled={conversations.isFetchingNextPage}>{conversations.isFetchingNextPage ? text('正在读取…', 'Loading…') : text('更早的会话', 'Older conversations')}</button>}
        {conversations.isFetchNextPageError && <button className="qa-retry" onClick={() => void conversations.fetchNextPage()}>{text('重试读取更早会话', 'Retry older conversations')}</button>}
        {!conversations.isLoading && !conversationItems.length && <p className="qa-muted">{text('你的第一段证据对话将在这里出现。', 'Your first evidence dialogue will appear here.')}</p>}
        <div className="qa-rail-foot"><ShieldCheck size={15} /><span>{text('会话与调查仅你可见；证据与知识可共享。', 'Your sessions and cases are private; evidence and knowledge are shared.')}</span></div>
      </aside>

      <main className="qa-dialogue">
        <div className="qa-dialogue-head"><div><small>ORACLE / ARGUS</small><strong>{sessionId ? text('正在延续同一条证据链', 'Continuing one evidence chain') : text('从一个有意义的问题开始', 'Begin with a meaningful question')}</strong></div><span>{turns.length ? `${turns.length} ${text('回合', 'turns')}` : 'NEW'}</span></div>
        <div className="qa-transcript" aria-live="polite">
          {history.hasNextPage && <button className="qa-load-more qa-load-turns" onClick={() => void history.fetchNextPage()} disabled={history.isFetchingNextPage}>{history.isFetchingNextPage ? text('正在恢复更早回合…', 'Restoring earlier turns…') : text('查看更早回合', 'Load earlier turns')}</button>}
          {history.isFetchNextPageError && <button className="qa-retry" onClick={() => void history.fetchNextPage()}>{text('重试恢复更早回合', 'Retry earlier turns')}</button>}
          {history.isLoading && <p className="qa-muted">{text('恢复完整会话…', 'Restoring conversation…')}</p>}
          {history.isError && <div className="qa-error">{text('无法读取这段会话。', 'Could not load this conversation.')}<button onClick={() => void history.refetch()}>{text('重试', 'Retry')}</button></div>}
          {!sessionId && !pendingQuestion && <div className="qa-empty"><div className="qa-empty-orbit"><span /><span /><b /></div><small>QUESTION → EVIDENCE → DECISION</small><h2>{text('答案应该能追到它的来源。', 'Every answer should lead back to its source.')}</h2><p>{text('快速回答、检索、核验、调查与持续守望在同一会话中衔接。选择路径后，系统保留目标和上下文；每个结论都能打开原始证据。', 'Direct answers, retrieval, verification, investigation and watch continue in one session. Every conclusion opens its source evidence.')}</p></div>}
          {turns.map(turn => <ConversationTurn key={turn.turn_index} turn={turn} active={focusTurn?.turn_index === turn.turn_index} sessionId={sessionId!} reasoning={completedReasoning[`${sessionId}:${turn.turn_index}`] ?? null} onSelect={() => { const next = new URLSearchParams(params); next.set('turn', String(turn.turn_index)); setParams(next, { replace: true }) }} onEvidence={setEvidence} />)}
          {pendingQuestion && <div className="qa-turn qa-turn-pending"><div className="qa-question"><small>{text('你 · 当前回合', 'YOU · CURRENT TURN')}</small><p>{pendingQuestion}</p></div><div className="qa-answer"><small><i className="qa-live-dot" />{text('正在形成结构化研判', 'STRUCTURED DECISION IN PROGRESS')}</small>{previewStatement(draftRaw) ? <p className="qa-draft-text">{previewStatement(draftRaw)}<span className="qa-caret" /></p> : <p className="qa-muted">{streamPhase === 'connecting' ? text('正在建立安全流…', 'Connecting to the answer stream…') : text('正在检索上下文并核对证据…', 'Retrieving context and checking evidence…')}</p>}{draftRaw && <small className="qa-draft-label">{text('生成中 · 尚未经证据校验', 'GENERATING · NOT YET EVIDENCE-VALIDATED')}</small>}{reasoningRaw && <details open={reasoningOpen} onToggle={event => setReasoningOpen(event.currentTarget.open)} className="qa-reasoning"><summary>{text('模型推理流', 'Model reasoning stream')}</summary><pre>{reasoningRaw}</pre></details>}</div></div>}
          <div ref={bottomRef} />
        </div>
        <div className="qa-compose">
          <div className="qa-profiles" role="group" aria-label={text('问答路径', 'Question path')}>{profiles.map(item => <button key={item.id} className={profile === item.id ? 'selected' : ''} onClick={() => setProfile(item.id)} disabled={busy} title={item.description}><span>{text(item.zh, item.en)}</span><small>{item.id}</small></button>)}</div>
          <div className="qa-compose-grid"><label className="qa-target"><small>{text('调查对象', 'TARGET')}</small><input value={visibleTarget} onChange={event => setTarget(event.target.value)} disabled={busy || Boolean(sessionId)} placeholder="CVE-2026-… / object:<id>" /></label><label className="qa-question-input"><small>{text('你的问题', 'YOUR QUESTION')}</small><textarea value={question} onChange={event => setQuestion(event.target.value)} disabled={busy} rows={2} placeholder={text('问一个具体问题；Ctrl / ⌘ + Enter 发送', 'Ask a precise question; Ctrl / ⌘ + Enter to send')} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.nativeEvent.isComposing) { event.preventDefault(); void submit() } }} /></label><button className="qa-send" onClick={() => void submit()} disabled={busy || !question.trim()} aria-label={text('发送问题', 'Send question')}><Send size={18} /><span>{busy ? text('运行中', 'RUNNING') : text('发送', 'SEND')}</span></button></div>
          <div className="qa-compose-foot"><label><input type="checkbox" checked={showReasoning} onChange={event => setShowReasoning(event.target.checked)} disabled={busy} />{text('显示提供方推理流（如有）', 'Show provider reasoning stream, if available')}</label><span><CornerDownLeft size={12} />{text('会话持续保存', 'SESSION SAVED')}</span></div>
          {error && <div className="qa-error" role="alert">{error}</div>}
        </div>
      </main>

      <AuditRail turn={focusTurn} tasks={tasks} taskLoading={taskQueries.some(query => query.isLoading)} caseId={caseId} caseStatus={caseDetail.data?.status} caseDecision={caseDetail.data?.latest_decision} caseEvents={auditEvents} streamConnected={streamConnected} onEvidence={setEvidence} />
    </div>
    <AnimatePresence>{evidence && <EvidenceOverlay key={evidence} evidenceRef={evidence} onClose={() => setEvidence(null)} />}</AnimatePresence>
  </section>
}

function ConversationTurn({ turn, active, sessionId, reasoning, onSelect, onEvidence }: { turn: QuestionSessionTurn; active: boolean; sessionId: string; reasoning: string | null; onSelect: () => void; onEvidence: (ref: string) => void }) {
  const { text, language } = useI18n()
  const decision = useQuery({ queryKey: ['question-turn-decision', turn.decision_ref], queryFn: () => getDecision(turn.decision_ref!), enabled: Boolean(turn.decision_ref), retry: false })
  const caseId = turn.investigation_ref?.replace(/^case:/, '')
  const investigation = useQuery({ queryKey: ['question-turn-case', caseId], queryFn: () => getInvestigation(caseId!), enabled: Boolean(caseId), retry: false, refetchInterval: query => ['active', 'waiting'].includes(query.state.data?.status ?? '') ? 5000 : false })
  const caseHeadline = investigation.data?.status === 'resolved'
    ? text('调查已形成带引用的结论', 'Investigation resolved with cited findings')
    : ['failed', 'blocked', 'canceled'].includes(investigation.data?.status ?? '')
      ? text('调查已停止，请查看执行轨迹', 'Investigation stopped; inspect the execution trace')
      : text('证据不足，已转入持续调查', 'Evidence gap opened a continuing investigation')
  return <article className={`qa-turn ${active ? 'active' : ''}`}>
    <button className="qa-turn-index" onClick={onSelect} aria-label={text(`查看第 ${turn.turn_index} 回合轨迹`, `Inspect turn ${turn.turn_index}`)}>{String(turn.turn_index).padStart(2, '0')}</button>
    <div className="qa-question"><small>{text('你', 'YOU')} / {formatTime(turn.created_at, language)}</small><p>{turn.question}</p></div>
    <div className="qa-answer"><div className="qa-answer-meta"><span>{turn.decision_ref ? 'ORACLE' : 'ARGUS'} · {profileForTask(turn.task_kind)}</span><button onClick={onSelect}>{text('查看运行轨迹', 'INSPECT TRACE')}<ArrowUpRight size={12} /></button></div>
      {decision.isLoading && turn.decision_ref && <p className="qa-muted">{text('正在恢复研判…', 'Restoring decision…')}</p>}
      {decision.isError && <button className="qa-retry" onClick={() => void decision.refetch()}>{text('研判读取失败 · 重试', 'Decision failed · Retry')}</button>}
      {decision.data && <DecisionReport decision={decision.data} onEvidence={onEvidence} dialogue />}
      {reasoning && <details className="qa-reasoning"><summary>{text('本次模型推理流 · 仅当前页面保留', 'Provider reasoning · available until reload')}</summary><pre>{reasoning}</pre></details>}
      {investigation.data && <div className="qa-case-result"><strong>{caseHeadline}</strong>{!investigation.data.latest_decision && <p>{investigation.data.goal}</p>}<div><span>{investigation.data.status}</span><span>{investigation.data.confirmed_findings.length} {text('已确认', 'confirmed')}</span><span>{investigation.data.open_evidence_needs.length} {text('证据缺口', 'open needs')}</span></div>{investigation.data.latest_decision && <InvestigationReport investigation={investigation.data} onEvidence={onEvidence} />}<Link to={`/investigations?case=${caseId}&session=${sessionId}`}>{text('打开完整调查现场', 'Open full investigation')}<ArrowUpRight size={13} /></Link></div>}
      {!turn.decision_ref && !turn.investigation_ref && <p className="qa-muted">{text('本回合没有持久研判或调查引用。', 'No durable decision or case reference for this turn.')}</p>}
    </div>
  </article>
}

function AuditRail({ turn, tasks, taskLoading, caseId, caseStatus, caseDecision, caseEvents, streamConnected, onEvidence }: { turn: QuestionSessionTurn | null; tasks: AgentTaskDetail[]; taskLoading: boolean; caseId: string | null; caseStatus?: string; caseDecision?: DecisionView | null; caseEvents: ProductRuntimeEvent[]; streamConnected: boolean; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const decision = useQuery({ queryKey: ['question-audit-decision', turn?.decision_ref], queryFn: () => getDecision(turn!.decision_ref!), enabled: Boolean(turn?.decision_ref), retry: false })
  const finalDecision = decision.data ?? caseDecision
  const refs = useMemo(() => finalDecision ? [...new Set([...finalDecision.citations.map(item => item.evidence_ref), ...finalDecision.conclusions.flatMap(item => item.evidence_refs)])] : [], [finalDecision])
  const modelAttempts = tasks.flatMap(task => task.model_attempts.map(item => ({ ...item, role: task.task.role_id })))
  const contextCount = tasks.filter(task => task.context).length
  const runtimeCount = tasks.reduce((count, task) => count + task.capabilities.length + task.events.length, caseEvents.length)
  return <aside className="qa-audit" aria-label={text('可审计轨迹', 'Auditable trace')}>
    <header><div><small>TRACE / CONTEXT / SOURCES</small><h2>{text('证据轨迹', 'Evidence trace')}</h2></div><span className={turn ? 'active' : ''}>{turn ? `TURN ${String(turn.turn_index).padStart(2, '0')}` : 'IDLE'}</span></header>
    {!turn && <div className="qa-audit-empty"><div className="qa-audit-diagram"><span>01</span><i /><span>02</span><i /><span>03</span></div><p>{text('选中一个会话回合后，这里展示证据引用、模型调用、上下文装配和工具执行记录。', 'Select a turn to inspect its citations, model calls, assembled context, and tool activity.')}</p></div>}
    {turn && <>
      <div className="qa-audit-coordinate"><small>WORLD REVISION</small><strong>{turn.knowledge_revision ?? '—'}</strong><span>{turn.context_id ?? (caseId ? `case:${caseId}` : turn.request_id)}</span></div>
      <section className="qa-audit-section"><h3>{text('结论引用', 'Citations')} <b>{refs.length}</b></h3>{refs.length ? refs.map((ref, index) => <button className="qa-evidence-ref" key={ref} onClick={() => onEvidence(ref)}><span>{String(index + 1).padStart(2, '0')}</span><span>{ref}</span><Link2 size={13} /></button>) : <p>{text('本回合尚无可引用的最终结论。', 'No final citation yet for this turn.')}</p>}</section>
      <section className="qa-audit-section"><h3>{text('模型调用', 'Model execution')} <b>{modelAttempts.length}</b></h3>{taskLoading && <p>{text('读取模型轨迹…', 'Loading model trace…')}</p>}{modelAttempts.map(item => <div className="qa-audit-row" key={item.model_attempt_id}><small>{item.role} · {item.purpose} · {item.status}</small><strong>{item.actual_model}</strong><span>{item.latency_ms === null ? '—' : `${item.latency_ms} ms`} · {item.input_tokens ?? '—'} in / {item.output_tokens ?? '—'} out {item.reasoning_tokens ? `· ${item.reasoning_tokens} reasoning` : ''}</span></div>)}{!taskLoading && !modelAttempts.length && <p>{text('当前回合没有模型调用记录。', 'No model call recorded for this turn.')}</p>}</section>
      <section className="qa-audit-section"><h3>{text('上下文清单', 'Context manifest')} <b>{contextCount}</b></h3>{tasks.map(task => task.context && <div key={task.task.run_id}><div className="qa-audit-row"><small>{task.context!.role_ref} · REV {task.context!.context_revision}</small><strong>{task.context!.context_id}</strong><span>{task.context!.parent_context_id ? `${text('继承', 'Parent')}: ${task.context!.parent_context_id}` : text('新会话上下文', 'New session context')}</span></div><div className="qa-context-counts"><span>{task.context!.object_refs.length} objects</span><span>{task.context!.relation_refs.length} relations</span><span>{task.context!.evidence_refs.length} evidence</span><span>{task.context!.retrieval_invocation_refs.length} retrievals</span></div>{task.context!.evidence_refs.length > 0 && <details><summary>{text('输入证据引用', 'Input evidence references')}<ChevronRight size={13} /></summary><div className="qa-fragments">{task.context!.evidence_refs.map(ref => <button className="qa-context-ref" key={ref} onClick={() => onEvidence(ref)}>{ref}<ArrowUpRight size={11} /></button>)}</div></details>}{task.context!.retrieval_invocation_refs.length > 0 && <details><summary>{text('检索调用', 'Retrieval invocations')}<ChevronRight size={13} /></summary><div className="qa-fragments">{task.context!.retrieval_invocation_refs.map(ref => <div key={ref}><strong>{ref}</strong></div>)}</div></details>}</div>)}{tasks.flatMap(task => task.prompt_assemblies).map(assembly => <details key={assembly.assembly_id}><summary>{text('Prompt 片段', 'Prompt fragments')} · {assembly.role_revision}<ChevronRight size={13} /></summary><div className="qa-fragments">{assembly.fragments.map((fragment, index) => <div key={index}><small>{fragment.kind ?? 'fragment'} · {fragment.trust_class ?? 'unknown'}</small><strong>{fragment.source_ref ?? 'source unknown'}</strong><span>{fragment.selection_reason ?? ''}</span></div>)}</div></details>)}{!contextCount && !taskLoading && <p>{text('尚无可读取的上下文清单。', 'No context manifest available yet.')}</p>}</section>
      <section className="qa-audit-section"><h3>{text('工具与执行事件', 'Tools & runtime')} <b>{runtimeCount}</b></h3>{tasks.flatMap(task => task.capabilities).map(item => <div className="qa-audit-row" key={item.invocation_id}><small>TOOL · {item.status}</small><strong>{item.capability_id}</strong><span>{item.tool_impl_id}</span></div>)}{tasks.flatMap(task => task.events.map(item => ({ ...item, role: task.task.role_id }))).map(item => <div className="qa-audit-row" key={item.event_id}><small>{item.role} · TASK {item.seq}</small><strong>{item.event_type}</strong><span>{item.producer}</span></div>)}{caseId && <p className="qa-case-stream"><i className={streamConnected ? 'connected' : ''} />{text('调查事件流', 'Investigation event stream')} · {caseStatus ?? 'active'}</p>}{caseEvents.map(item => <div className="qa-audit-row" key={item.event_id}><small>{item.event_type} · {item.actor ?? item.source_kind}</small><strong>{item.summary}</strong>{item.evidence_refs.map(ref => <button key={ref} onClick={() => onEvidence(ref)}>{ref}<ArrowUpRight size={11} /></button>)}</div>)}</section>
    </>}
  </aside>
}
