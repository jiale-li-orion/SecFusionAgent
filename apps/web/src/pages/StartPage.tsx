import { SessionHistory } from '../components/SessionHistory'
import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'motion/react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Eye,
  FlaskConical,
  Gauge,
  ScanSearch,
  Send,
  SlidersHorizontal,
  Telescope,
} from 'lucide-react'
import { askQuestion, getDecision, getInvestigation, type QuestionResult, type TaskKind } from '../lib/api'
import { MissionField } from '../components/start/MissionField'
import { MissionOutcome } from '../components/start/MissionOutcome'
import { AlchemistBoundary } from '../components/start/AlchemistBoundary'
import { AdvancedRange } from '../components/start/MissionControls'
import { modeTitleEn, originToIntelligence, parseMissionTarget } from '../lib/startMissionPresentation'
import { useI18n } from '../lib/i18n'

const sourceRoles = ['primary', 'authority', 'forensic', 'reference', 'telemetry', 'signal'] as const

const modes = [
  {
    id: 'DIRECT',
    title: '快速回答',
    taskKind: 'lookup' as TaskKind,
    icon: Gauge,
    description: '当前 Evidence World 已满足回答条件。ORACLE 直接收束现有上下文。',
    tempo: 'interactive',
    durable: 'no durable Case',
    outcome: 'Decision',
    capability: 'current Evidence World',
    role: 'ORACLE',
  },
  {
    id: 'RETRIEVE',
    title: '证据检索',
    taskKind: 'retrieve' as TaskKind,
    icon: ScanSearch,
    description: '扩大本地检索窗口，把尚未进入当前上下文的 Evidence 拉近。',
    tempo: 'interactive',
    durable: 'upgrade when needed',
    outcome: 'Decision / escalate',
    capability: 'bounded local retrieval',
    role: 'ORACLE',
  },
  {
    id: 'VERIFY',
    title: '精准核验',
    taskKind: 'verify_version_fix' as TaskKind,
    icon: FlaskConical,
    description: '围绕版本、修复边界或来源冲突建立 durable Case，ARGUS 按 EvidenceNeed 推进。',
    tempo: 'multi-step',
    durable: 'durable Case',
    outcome: 'Investigation / Decision',
    capability: 'evidence + enrichment',
    role: 'ARGUS',
  },
  {
    id: 'INVESTIGATE',
    title: '深度调查',
    taskKind: 'investigate_incident' as TaskKind,
    icon: Telescope,
    description: '进入多步追索；Skill、Capability 与 delegated enrichment 按任务状态出现。',
    tempo: 'deep runtime',
    durable: 'durable Case',
    outcome: 'Investigation',
    capability: 'Skill / Capability / delegation',
    role: 'ARGUS',
  },
  {
    id: 'WATCH',
    title: '持续守望',
    taskKind: 'watch_incident' as TaskKind,
    icon: Eye,
    description: 'Case 进入 waiting；外部世界或依赖变化后，从原状态继续下一次 episode。',
    tempo: 'waiting',
    durable: 'durable waiting Case',
    outcome: 'Wake episode',
    capability: 'world-change recovery',
    role: 'ARGUS',
  },
]

export function StartPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const profileParam = params.get('profile')?.toUpperCase() ?? ''
  const cveParam = params.get('cve')?.toUpperCase() ?? ''
  const objectParam = params.get('object') ?? ''
  const questionParam = params.get('question') ?? ''
  const originSpace = params.get('from')
  const originRef = params.get('origin')
  const reduceMotion = Boolean(useReducedMotion())
  const [modeId, setModeId] = useState(() => modes.some((mode) => mode.id === profileParam) ? profileParam : 'VERIFY')
  const [question, setQuestion] = useState(questionParam)
  const [target, setTarget] = useState(cveParam || (objectParam ? `object:${objectParam}` : ''))
  const [liveResult, setResult] = useState<QuestionResult | null>(null)
  const savedDecision = params.get('decision')
  const savedCase = params.get('case')
  const sessionId = liveResult?.session_id ?? params.get('session') ?? undefined
  const decisionQuery = useQuery({ queryKey: ['decision', savedDecision], queryFn: () => getDecision(savedDecision!), enabled: Boolean(savedDecision), retry: false })
  const caseQuery = useQuery({ queryKey: ['start-case', savedCase], queryFn: () => getInvestigation(savedCase!), enabled: Boolean(savedCase && !savedDecision), retry: false, refetchInterval: (query) => ['active', 'waiting'].includes(query.state.data?.status ?? '') ? 5000 : false })
  const restored: QuestionResult | null = decisionQuery.data ? {
    mode: 'completed', decision: decisionQuery.data, session_id: sessionId ?? '',
    execution_profile: profileParam || 'DIRECT', request_id: params.get('request') ?? '', turn_index: Number(params.get('turn')) || 1,
  } : caseQuery.data ? {
    mode: 'accepted', investigation: caseQuery.data, session_id: sessionId ?? '',
    execution_profile: caseQuery.data.execution_profile ?? profileParam, request_id: params.get('request') ?? '', turn_index: Number(params.get('turn')) || 1,
  } : null
  const currentCase = liveResult?.mode === 'accepted' ? caseQuery.data : restored?.investigation ? caseQuery.data : null
  const result: QuestionResult | null = currentCase ? {
    ...(liveResult ?? restored!),
    mode: currentCase.latest_decision ? 'completed' : 'accepted',
    decision: currentCase.latest_decision,
    investigation: currentCase,
  } : liveResult ?? restored
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [requiredSourceRoles, setRequiredSourceRoles] = useState<string[]>([])
  const [priority, setPriority] = useState(50)
  const [interactiveTimeoutSeconds, setInteractiveTimeoutSeconds] = useState(5)
  const [retrievalLimit, setRetrievalLimit] = useState(8)
  const [allowWait, setAllowWait] = useState(true)
  const [investigationTimeoutSeconds, setInvestigationTimeoutSeconds] = useState(300)
  const [agentTurns, setAgentTurns] = useState(8)
  const [toolCalls, setToolCalls] = useState(12)
  const selected = useMemo(() => modes.find((mode) => mode.id === modeId)!, [modeId])

  useEffect(() => {
    document.getElementById('mission-outcome')?.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth', block: 'start' })
  }, [result?.request_id, result?.decision?.decision_id, reduceMotion])

  async function launch() {
    if (!question.trim() || busy) return
    const requiresTarget = selected.id !== 'RETRIEVE' && !sessionId
    const parsedTarget = parseMissionTarget(target)
    if (requiresTarget && !parsedTarget) {
      setError(text(`${selected.id} 需要 CVE 或 canonical object 目标。`, `${selected.id} requires a CVE or canonical object target.`))
      return
    }
    if (target.trim() && !parsedTarget) {
      setError(text('目标格式使用 CVE-YYYY-NNNN 或 object:<id>。', 'Use CVE-YYYY-NNNN or object:<id> as the target.'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const response = await askQuestion({
        question: question.trim(),
        sessionId,
        cveId: !sessionId && parsedTarget?.kind === 'cve' ? parsedTarget.value : undefined,
        objectId: !sessionId && parsedTarget?.kind === 'object' ? parsedTarget.value : undefined,
        taskKind: selected.taskKind,
        requiredSourceRoles,
        priority,
        interactiveTimeoutSeconds,
        retrievalLimit,
        allowWait,
        investigationTimeoutSeconds,
        agentTurns,
        toolCalls,
      })
      setResult(response)
      if (response.decision || response.investigation) {
        const next = new URLSearchParams(params)
        if (response.mode === 'completed' && response.decision) {
          queryClient.setQueryData(['decision', response.decision.decision_id], response.decision)
          next.set('decision', response.decision.decision_id)
          next.delete('case')
        } else if (response.investigation) {
          next.set('case', response.investigation.case_id)
          next.delete('decision')
        }
        void queryClient.invalidateQueries({ queryKey: ['question-session', response.session_id] })
        next.set('session', response.session_id)
        next.set('turn', String(response.turn_index))
        next.set('request', response.request_id)
        next.set('profile', modeId)
        next.set('question', question.trim())
        if (parsedTarget) next.set(parsedTarget.kind === 'cve' ? 'cve' : 'object', parsedTarget.value)
        setParams(next, { replace: true })
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : text('请求失败', 'Request failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className={`start-space profile-${selected.id.toLowerCase()} role-${selected.role.toLowerCase()} ${originSpace && originRef ? 'has-origin' : ''} ${busy ? 'launch-active' : ''}`}
      data-profile={selected.id}
      data-role={selected.role}
    >
      <header className="mission-briefing">
        <div>
          <p>{text('命名问题，也选择求知的代价', 'NAME THE QUESTION; CHOOSE THE PRICE OF KNOWING')}</p>
          <h1>{text('启动', 'START')} <span>{text('任务', 'MISSION')}</span></h1>
          <small>{text(
            'DIRECT 直接收束，RETRIEVE 扩大证据上下文，VERIFY 建立 durable verification，INVESTIGATE 进入多步追索，WATCH 保持 waiting Case 等待世界变化。',
            'DIRECT closes from current evidence. RETRIEVE expands local context. VERIFY opens durable verification. INVESTIGATE enters multi-step execution. WATCH keeps a waiting Case ready for world change.',
          )}</small>
        </div>
        <div className="start-route-legend">
          <span><i className="oracle" />DIRECT / RETRIEVE → ORACLE</span>
          <span><i className="argus" />VERIFY / INVESTIGATE / WATCH → ARGUS</span>
        </div>
      </header>

      {originSpace && originRef && (
        <div className="mission-origin">
          <div><small>{text('任务来源坐标', 'MISSION ORIGIN')}</small><strong>{originSpace.toUpperCase()} → {modeId}</strong><span className="mono">{originRef}</span></div>
          {originSpace === 'intelligence' && <button onClick={() => navigate(originToIntelligence(originRef))}>{text('返回原档案', 'BACK TO DOSSIER')}</button>}
        </div>
      )}

      <MissionField modes={modes} selected={selected} busy={busy} onSelect={(id) => { setModeId(id); setResult(null); setError('') }}>
        <AlchemistBoundary caseId={result?.mode === 'accepted' ? result.investigation?.case_id ?? null : null} />
      </MissionField>

      <div className="payload-deck">
        <div className="payload-deck-head">
          <div><small>{text('任务载荷', 'MISSION PAYLOAD')}</small><strong>{selected.id} → {selected.role}</strong></div>
          <button className={`advanced-toggle ${advancedOpen ? 'active' : ''}`} onClick={() => setAdvancedOpen((value) => !value)}>
            <SlidersHorizontal size={13} />
            <span>{advancedOpen ? text('收起执行边界', 'HIDE EXECUTION BOUNDS') : text('展开执行边界', 'SHOW EXECUTION BOUNDS')}</span>
          </button>
        </div>

        <div className="payload-grid">
          <label className="payload-field target">
            <span>{sessionId ? text('目标 / 由当前会话继承', 'TARGET / CARRIED BY SESSION') : selected.id === 'RETRIEVE' ? text('目标 / 可选', 'TARGET / OPTIONAL') : text('目标 / 必填', 'TARGET / REQUIRED')}</span>
            <input
              className="mono"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              disabled={Boolean(sessionId) || busy}
              placeholder="CVE-2026-… / object:<id>"
            />
          </label>

          <label className="payload-field prompt">
            <span>{text('问题核心', 'QUESTION')}</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={busy}
              onKeyDown={(event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.nativeEvent.isComposing) { event.preventDefault(); void launch() } }}
              placeholder={text('写清要确认的问题。', 'State the question the system must resolve.')}
            />
          </label>

          <button className={`payload-launch role-${selected.role.toLowerCase()}`} onClick={launch} disabled={busy || !question.trim() || (selected.id !== 'RETRIEVE' && !sessionId && !target.trim())}>
            <span><Send size={16} /></span>
            <small>{busy ? text('请求执行中', 'REQUEST IN FLIGHT') : text(`${selected.role} 接管任务`, `${selected.role} TAKES OWNERSHIP`)}</small>
            <strong>{busy ? text('启动中…', 'LAUNCHING…') : sessionId ? text('继续当前会话', 'CONTINUE SESSION') : text(`启动 ${selected.title}`, `START ${modeTitleEn(selected.id)}`)}</strong>
          </button>
        </div>

        {advancedOpen && (
          <motion.section
            className="mission-advanced"
            initial={{ opacity: 0, y: -8, clipPath: 'inset(0 0 100% 0)' }}
            animate={{ opacity: 1, y: 0, clipPath: 'inset(0 0 0% 0)' }}
          >
            <div className="advanced-source-roles">
              <small>{text('证据来源角色', 'REQUIRED SOURCE ROLES')}</small>
              <div>
                {sourceRoles.map((role) => {
                  const active = requiredSourceRoles.includes(role)
                  return <button key={role} className={active ? 'active' : ''} onClick={() => setRequiredSourceRoles((current) => active ? current.filter((item) => item !== role) : [...current, role])}>{role}</button>
                })}
              </div>
            </div>
            <AdvancedRange label={text('优先级', 'PRIORITY')} value={priority} min={0} max={100} step={5} onChange={setPriority} suffix="/100" />
            {selected.id === 'DIRECT' || selected.id === 'RETRIEVE' ? (
              <>
                <AdvancedRange label={text('交互超时', 'INTERACTIVE TIMEOUT')} value={interactiveTimeoutSeconds} min={1} max={30} step={1} onChange={setInteractiveTimeoutSeconds} suffix="s" />
                <AdvancedRange label={text('检索上限', 'RETRIEVAL LIMIT')} value={retrievalLimit} min={1} max={20} step={1} onChange={setRetrievalLimit} suffix=" hits" />
              </>
            ) : (
              <>
                <AdvancedRange label={text('调查时限', 'INVESTIGATION DEADLINE')} value={investigationTimeoutSeconds} min={30} max={3600} step={30} onChange={setInvestigationTimeoutSeconds} suffix="s" />
                <AdvancedRange label={text('Agent 回合预算', 'AGENT TURN BUDGET')} value={agentTurns} min={1} max={64} step={1} onChange={setAgentTurns} suffix=" turns" />
                <AdvancedRange label={text('Tool 调用预算', 'TOOL CALL BUDGET')} value={toolCalls} min={0} max={128} step={1} onChange={setToolCalls} suffix=" calls" />
                <button className={`allow-wait ${allowWait ? 'active' : ''}`} onClick={() => setAllowWait((value) => !value)}>
                  <span>{text('允许进入 waiting 并在依赖变化后恢复', 'ALLOW WAIT / RESUME ON DEPENDENCY CHANGE')}</span>
                  <b>{allowWait ? 'ON' : 'OFF'}</b>
                </button>
              </>
            )}
          </motion.section>
        )}

        {sessionId && <div className="mission-session-strip"><span>{text('同一会话保留目标与上下文，可切换模式继续追问。', 'Target and context carry across turns. Switch modes to continue.')}</span><button onClick={() => { const next = new URLSearchParams(params); ['session', 'decision', 'case', 'turn', 'request', 'question'].forEach((key) => next.delete(key)); setParams(next, { replace: true }) }} disabled={busy}>{text('开启新会话', 'NEW SESSION')}</button></div>}
      </div>
        {sessionId && <SessionHistory sessionId={sessionId} />}
        {decisionQuery.isLoading && <p role="status">{text('恢复已保存的研判…', 'RESTORING SAVED DECISION…')}</p>}
        {decisionQuery.isError && <div className="error-block" role="alert">{decisionQuery.error.message}<button onClick={() => void decisionQuery.refetch()}>{text('重试', 'RETRY')}</button></div>}
        {caseQuery.isLoading && <p role="status">{text('恢复调查状态…', 'RESTORING CASE STATE…')}</p>}
        {caseQuery.isError && <div className="error-block" role="alert">{caseQuery.error.message}<button onClick={() => void caseQuery.refetch()}>{text('重试', 'RETRY')}</button></div>}
        {(error || result) && (
          <motion.div
            id="mission-outcome"
            className={`start-outcome ${error ? 'error' : result?.mode === 'accepted' ? 'accepted' : 'completed'}`}
            role={error ? 'alert' : 'status'}
            aria-live="polite"
            initial={{ opacity: 0, y: 12, clipPath: 'inset(0 0 70% 0)' }}
            animate={{ opacity: 1, y: 0, clipPath: 'inset(0 0 0% 0)' }}
          >
            {error ? (
              <>
                <small>{text('请求失败', 'REQUEST FAILED')}</small>
                <strong>{error}</strong>
              </>
            ) : result ? <MissionOutcome result={result} target={target} /> : null}
          </motion.div>
        )}
    </section>
  )
}
