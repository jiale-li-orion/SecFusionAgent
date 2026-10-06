import { useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowUpRight,
  BrainCircuit,
  Eye,
  FlaskConical,
  Gauge,
  Link2,
  Orbit,
  ScanSearch,
  Send,
  SlidersHorizontal,
  Sparkles,
  Telescope,
} from 'lucide-react'
import { askQuestion, type QuestionResult, type TaskKind } from '../lib/api'
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

const oracleRailSlots = [
  { left: 24, top: 31 },
  { left: 24, top: 64 },
]

const argusRailSlots = [
  { left: 76, top: 24 },
  { left: 82, top: 45 },
  { left: 76, top: 67 },
]

export function StartPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const profileParam = params.get('profile')?.toUpperCase() ?? ''
  const cveParam = params.get('cve')?.toUpperCase() ?? ''
  const objectParam = params.get('object') ?? ''
  const questionParam = params.get('question') ?? ''
  const originSpace = params.get('from')
  const originRef = params.get('origin')
  const reduceMotion = Boolean(useReducedMotion())
  const [modeId, setModeId] = useState(() => modes.some((mode) => mode.id === profileParam) ? profileParam : 'VERIFY')
  const [previewModeId, setPreviewModeId] = useState<string | null>(null)
  const [question, setQuestion] = useState(questionParam)
  const [target, setTarget] = useState(cveParam || (objectParam ? `object:${objectParam}` : ''))
  const [result, setResult] = useState<QuestionResult | null>(null)
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
  const preview = useMemo(() => modes.find((mode) => mode.id === previewModeId) ?? selected, [previewModeId, selected])
  const previewIndex = modes.findIndex((mode) => mode.id === preview.id)

  async function launch() {
    if (!question.trim() || busy) return
    const requiresTarget = selected.id !== 'RETRIEVE'
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
    setResult(null)
    try {
      const response = await askQuestion({
        question: question.trim(),
        cveId: parsedTarget?.kind === 'cve' ? parsedTarget.value : undefined,
        objectId: parsedTarget?.kind === 'object' ? parsedTarget.value : undefined,
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

      <div id="mission-theater" className={`start-theater chamber-focus-${selected.id.toLowerCase()} ${busy ? 'is-launching' : ''}`}>
        <svg className="start-orbit-map" viewBox="0 0 100 58" preserveAspectRatio="none" aria-hidden="true">
          <ellipse cx="50" cy="31" rx="39" ry="21" />
          <ellipse cx="50" cy="31" rx="27" ry="15" className="inner" />
          <path className="axis" d="M 7 44 C 28 32, 38 30, 50 31 C 62 30, 72 32, 93 44" />
          <motion.path
            className={`selected-route ${previewModeId ? 'is-preview' : ''} role-${preview.role.toLowerCase()}`}
            d={missionRoute(previewIndex, preview.role, modeId)}
            initial={false}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: reduceMotion ? 0 : .42, ease: 'easeOut' }}
          />
        </svg>

        <div className="start-role-gate oracle">
          <span className="role-gate-sigil"><Orbit size={18} /></span>
          <small>DECISION ROLE</small>
          <strong>ORACLE</strong>
          <em>DIRECT · RETRIEVE</em>
        </div>

        <div className="start-role-gate argus">
          <span className="role-gate-sigil"><Orbit size={18} /></span>
          <small>INVESTIGATION ROLE</small>
          <strong>ARGUS</strong>
          <em>VERIFY · INVESTIGATE · WATCH</em>
        </div>

        {modes.map(({ id, title, icon: Icon, role }, index) => {
          const active = id === modeId
          const slot = missionChamberSlot(index, modeId)
          return (
            <motion.button
              key={id}
              className={`mode-chamber mode-${id.toLowerCase()} ${active ? 'active' : ''} ${previewModeId === id ? 'preview' : ''} role-${role.toLowerCase()}`}
              initial={false}
              onHoverStart={() => setPreviewModeId(id)}
              onHoverEnd={() => setPreviewModeId(null)}
              onFocus={() => setPreviewModeId(id)}
              onBlur={() => setPreviewModeId(null)}
              onClick={() => {
                if (busy) return
                setModeId(id)
                setResult(null)
                setError('')
              }}
              animate={{
                left: `${slot.left}%`,
                top: `${slot.top}%`,
                y: active ? 0 : slot.top > 50 ? 3 : -3,
                scale: active ? 1.08 : .92,
                opacity: active ? 1 : .76,
                rotate: active ? 0 : slot.left < 50 ? -1.2 : 1.2,
              }}
              transition={{ type: 'spring', stiffness: 190, damping: 24, mass: .82 }}
            >
              <span className="mode-chamber-index">0{index + 1}</span>
              <span className="mode-chamber-glyph"><Icon size={active ? 23 : 18} /></span>
              <ModeInstrument mode={id} active={active} />
              <small>{text(title, modeTitleEn(id))}</small>
              <strong>{id}</strong>
              <em>{role}</em>
              <b>{active ? text('已装载', 'LOADED') : text('点击装载', 'LOAD')}</b>
              {active && <i />}
            </motion.button>
          )
        })}

        <motion.div
          className={`mission-reactor ${busy ? 'active' : ''} role-${selected.role.toLowerCase()}`}
          animate={{ scale: busy && !reduceMotion ? [1, 1.05, 1] : 1 }}
          transition={{ duration: .9, repeat: busy && !reduceMotion ? Infinity : 0 }}
        >
          <span className="reactor-ring ring-a" />
          <span className="reactor-ring ring-b" />
          <Sparkles size={21} />
          <strong>{busy ? text('启动中', 'LAUNCH') : selected.id}</strong>
          <small>{selected.role}</small>
        </motion.div>

        <motion.div
          key={preview.id}
          className="mode-readout"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <span>{text(preview.title, modeTitleEn(preview.id))} · {preview.id}</span>
          <strong>{text(preview.description, modeDescriptionEn(preview.id))}</strong>
          <div>
            <ModeFact label={text('响应节奏', 'TEMPO')} value={preview.tempo} />
            <ModeFact label={text('持久状态', 'DURABILITY')} value={preview.durable} />
            <ModeFact label={text('结果形态', 'OUTCOME')} value={preview.outcome} />
            <ModeFact label={text('允许能力', 'CAPABILITY')} value={preview.capability} />
          </div>
        </motion.div>

        <div className="alchemist-boundary">
          <span>ALCHEMIST</span>
          <small>{text('真实 Enrichment 子任务创建后，ALCHEMIST 进入运行链。', 'ALCHEMIST enters the runtime when a real Enrichment child task is created.')}</small>
        </div>

        <AnimatePresence>
          {busy && (
            <motion.div
              className={`mission-injection role-${selected.role.toLowerCase()}`}
              initial={{ opacity: 0, clipPath: 'circle(0% at 50% 50%)' }}
              animate={{ opacity: 1, clipPath: 'circle(74% at 50% 50%)' }}
              exit={{ opacity: 0, clipPath: 'circle(18% at 50% 50%)' }}
              transition={{ duration: reduceMotion ? 0 : .42, ease: [0.22, 1, 0.36, 1] }}
            >
              <motion.div
                className="mission-injection-packet"
                initial={{ y: 38, scale: .78, opacity: 0 }}
                animate={{ y: 0, scale: 1, opacity: 1 }}
                transition={{ delay: reduceMotion ? 0 : .08, type: 'spring', stiffness: 260, damping: 24 }}
              >
                <small>{text('PRODUCT REQUEST / 准入', 'PRODUCT REQUEST / ADMISSION')}</small>
                <strong>{selected.id}</strong>
                <span>{selected.role}</span>
              </motion.div>
              <div className="mission-injection-route">
                <i />
                <span>{text('请求正在进入真实执行边界', 'REQUEST ENTERING REAL EXECUTION BOUNDS')}</span>
                <b>{selected.role === 'ORACLE' ? 'DecisionRole@1' : 'InvestigationRole@1'}</b>
              </div>
              <div className="mission-injection-bounds">
                <span>{requiredSourceRoles.length ? requiredSourceRoles.join(' · ') : text('来源角色：未指定', 'source roles: unconstrained')}</span>
                <span>priority {priority}</span>
                <span>{selected.role === 'ORACLE' ? `${interactiveTimeoutSeconds}s · retrieval ${retrievalLimit}` : `${investigationTimeoutSeconds}s · ${agentTurns} turns · ${toolCalls} calls`}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

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
            <span>{selected.id === 'RETRIEVE' ? text('目标 / 可选', 'TARGET / OPTIONAL') : text('目标 / 必填', 'TARGET / REQUIRED')}</span>
            <input
              className="mono"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              placeholder="CVE-2026-… / object:<id>"
            />
          </label>

          <label className="payload-field prompt">
            <span>{text('问题核心', 'QUESTION')}</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={text('写清要确认的问题。', 'State the question the system must resolve.')}
            />
          </label>

          <button className={`payload-launch role-${selected.role.toLowerCase()}`} onClick={launch} disabled={busy || !question.trim() || (selected.id !== 'RETRIEVE' && !target.trim())}>
            <span><Send size={16} /></span>
            <small>{busy ? text('请求执行中', 'REQUEST IN FLIGHT') : text(`${selected.role} 接管任务`, `${selected.role} TAKES OWNERSHIP`)}</small>
            <strong>{busy ? text('启动中…', 'LAUNCHING…') : text(`启动 ${selected.title}`, `START ${modeTitleEn(selected.id)}`)}</strong>
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

        {(error || result) && (
          <motion.div
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
            ) : result ? (
              result.mode === 'accepted' ? (
                <div className="start-case-outcome">
                  <div className="case-outcome-axis"><span /><i /><b /></div>
                  <div>
                    <small>{text('ARGUS / DURABLE CASE 已接收', 'ARGUS / DURABLE CASE ACCEPTED')}</small>
                    <strong>{result.execution_profile}</strong>
                    <span>{result.investigation?.goal ?? text('调查已进入 durable runtime。', 'Investigation entered durable runtime.')}</span>
                    <em className="mono">{result.investigation?.case_id ?? text('Case 已创建', 'case created')} · {result.investigation?.status ?? text('已接收', 'accepted')}</em>
                  </div>
                  {result.investigation?.case_id && (
                    <button onClick={() => navigate(`/investigations?${new URLSearchParams({ case: result.investigation!.case_id, session: result.session_id, from: 'start', request: result.request_id }).toString()}`)}>
                      {text('进入 Case 现场', 'ENTER CASE FIELD')} <ArrowUpRight size={13} />
                    </button>
                  )}
                </div>
              ) : (
                <div className="start-decision-outcome">
                  <div className="decision-seal"><Sparkles size={18} /><i /></div>
                  <div>
                    <small>{text('ORACLE / DECISION 已生成', 'ORACLE / DECISION READY')}</small>
                    <strong>{result.execution_profile}</strong>
                    <p>{summarizeDecision(result)}</p>
                    <div className="decision-boundary">
                      <span>{text(`${result.decision?.citations?.length ?? 0} 条 citations`, `${result.decision?.citations?.length ?? 0} citations`)}</span>
                      <span>{text(`${result.decision?.conflicts?.length ?? 0} 个 conflicts`, `${result.decision?.conflicts?.length ?? 0} conflicts`)}</span>
                      <span>{text(`${result.decision?.unknowns?.length ?? 0} 个 unknowns`, `${result.decision?.unknowns?.length ?? 0} unknowns`)}</span>
                    </div>
                    <div className="start-decision-next">
                      {missionTargetDossierPath(target, result.request_id) && <button onClick={() => navigate(missionTargetDossierPath(target, result.request_id)!)}><BrainCircuit size={11} /> {text('打开目标档案', 'OPEN TARGET DOSSIER')}</button>}
                      {missionTargetDossierPath(target, result.request_id) && (result.decision?.citations ?? []).slice(0, 3).map((citation, index) => <button key={citation.evidence_ref} onClick={() => navigate(missionTargetEvidencePath(target, citation.evidence_ref, result.request_id)!)}><Link2 size={11} /> {text(`证据 ${index + 1}`, `EVIDENCE ${index + 1}`)}<span className="mono">{compactOutcomeRef(citation.evidence_ref)}</span></button>)}
                    </div>
                    <em className="mono">{result.decision?.decision_id ?? 'decision'} · session {result.session_id} · turn {result.turn_index}</em>
                  </div>
                </div>
              )
            ) : null}
          </motion.div>
        )}
      </div>
    </section>
  )
}

function missionTargetDossierPath(raw: string, requestId: string) {
  const target = parseMissionTarget(raw)
  if (!target) return null
  const params = new URLSearchParams({ from: 'start', request: requestId })
  params.set(target.kind === 'cve' ? 'cve' : 'object', target.value)
  return `/intelligence?${params.toString()}`
}

function missionTargetEvidencePath(raw: string, evidenceRef: string, requestId: string) {
  const dossier = missionTargetDossierPath(raw, requestId)
  if (!dossier) return null
  const [path, query = ''] = dossier.split('?', 2)
  const params = new URLSearchParams(query)
  params.set('evidence', evidenceRef)
  return `${path}?${params.toString()}`
}

function compactOutcomeRef(value: string) { return value.length > 26 ? `${value.slice(0, 12)}…${value.slice(-7)}` : value }

function ModeInstrument({ mode, active }: { mode: string; active: boolean }) {
  if (mode === 'DIRECT') {
    return <span className={'mode-instrument direct ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
  }
  if (mode === 'RETRIEVE') {
    return <span className={'mode-instrument retrieve ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><i /><b /></span>
  }
  if (mode === 'VERIFY') {
    return <span className={'mode-instrument verify ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
  }
  if (mode === 'INVESTIGATE') {
    return <span className={'mode-instrument investigate ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><i /><i /><b /></span>
  }
  return <span className={'mode-instrument watch ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
}

function parseMissionTarget(raw: string): { kind: 'cve' | 'object'; value: string } | null {
  const value = raw.trim()
  if (!value) return null
  const canonical = value.toUpperCase()
  if (/^CVE-\d{4}-\d+$/.test(canonical)) return { kind: 'cve', value: canonical }
  if (/^object:/i.test(value)) {
    const objectId = value.replace(/^object:/i, '').trim()
    if (objectId) return { kind: 'object', value: objectId }
  }
  return null
}

function originToIntelligence(originRef: string) {
  if (originRef.startsWith('cve:')) return `/intelligence?cve=${encodeURIComponent(originRef.slice(4))}`
  if (originRef.startsWith('object:')) return `/intelligence?object=${encodeURIComponent(originRef.slice(7))}`
  if (originRef.startsWith('incident:')) return `/intelligence?incident=${encodeURIComponent(originRef.slice(9))}`
  return '/intelligence'
}

function missionChamberSlot(index: number, activeModeId: string) {
  const activeIndex = modes.findIndex((mode) => mode.id === activeModeId)
  const activeSlots: Record<string, { left: number; top: number }> = {
    DIRECT: { left: 46, top: 35 },
    RETRIEVE: { left: 50, top: 38 },
    VERIFY: { left: 52, top: 35 },
    INVESTIGATE: { left: 50, top: 32 },
    WATCH: { left: 50, top: 44 },
  }
  if (index === activeIndex) return activeSlots[activeModeId] ?? { left: 50, top: 38 }
  const mode = modes[index]
  const layouts: Record<string, Partial<Record<string, { left: number; top: number }>>> = {
    DIRECT: {
      RETRIEVE: { left: 24, top: 62 },
      VERIFY: { left: 77, top: 24 },
      INVESTIGATE: { left: 83, top: 48 },
      WATCH: { left: 76, top: 72 },
    },
    RETRIEVE: {
      DIRECT: { left: 22, top: 35 },
      VERIFY: { left: 76, top: 24 },
      INVESTIGATE: { left: 83, top: 48 },
      WATCH: { left: 76, top: 70 },
    },
    VERIFY: {
      DIRECT: { left: 20, top: 28 },
      RETRIEVE: { left: 22, top: 62 },
      INVESTIGATE: { left: 78, top: 48 },
      WATCH: { left: 71, top: 72 },
    },
    INVESTIGATE: {
      DIRECT: { left: 18, top: 28 },
      RETRIEVE: { left: 21, top: 64 },
      VERIFY: { left: 74, top: 20 },
      WATCH: { left: 77, top: 70 },
    },
    WATCH: {
      DIRECT: { left: 19, top: 25 },
      RETRIEVE: { left: 22, top: 61 },
      VERIFY: { left: 74, top: 20 },
      INVESTIGATE: { left: 81, top: 48 },
    },
  }
  const explicit = layouts[activeModeId]?.[mode.id]
  if (explicit) return explicit
  const sameRole = modes
    .map((candidate, modeIndex) => ({ candidate, modeIndex }))
    .filter(({ candidate, modeIndex }) => modeIndex !== activeIndex && candidate.role === mode.role)
    .map(({ modeIndex }) => modeIndex)
  const roleIndex = sameRole.indexOf(index)
  if (mode.role === 'ORACLE') return oracleRailSlots[Math.max(0, roleIndex)] ?? oracleRailSlots[0]
  return argusRailSlots[Math.max(0, roleIndex)] ?? argusRailSlots[0]
}

function AdvancedRange({ label, value, min, max, step, onChange, suffix }: { label: string; value: number; min: number; max: number; step: number; onChange: (value: number) => void; suffix: string }) {
  return (
    <label className="advanced-range">
      <span><small>{label}</small><strong>{value}{suffix}</strong></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  )
}

function modeTitleEn(id: string) {
  return ({ DIRECT: 'QUICK ANSWER', RETRIEVE: 'EVIDENCE RETRIEVAL', VERIFY: 'TARGETED VERIFICATION', INVESTIGATE: 'DEEP INVESTIGATION', WATCH: 'CONTINUOUS WATCH' } as Record<string, string>)[id] ?? id
}

function modeDescriptionEn(id: string) {
  return ({
    DIRECT: 'Current Evidence World is sufficient. ORACLE closes directly from the bounded context.',
    RETRIEVE: 'Expand the local retrieval window and bring additional Evidence into the current context.',
    VERIFY: 'Open a durable Case around version, fix-boundary, applicability, or source conflict; ARGUS advances by EvidenceNeed.',
    INVESTIGATE: 'Enter multi-step execution where Skill, Capability, and delegated Enrichment follow task state.',
    WATCH: 'Keep the Case waiting and resume a new episode when the external world or a dependency changes.',
  } as Record<string, string>)[id] ?? id
}

function ModeFact({ label, value }: { label: string; value: string }) {
  return <span><small>{label}</small><strong>{value}</strong></span>
}

function missionRoute(index: number, role: string, activeModeId: string) {
  const slot = missionChamberSlot(index, activeModeId)
  const routeY = Math.max(12, Math.min(50, slot.top * .58))
  const gateX = role === 'ORACLE' ? 8 : 92
  const bendX = role === 'ORACLE' ? 38 : 62
  return `M ${slot.left} ${routeY} C ${slot.left} ${routeY - 5}, ${bendX} 30, 50 31 C ${50} 36, ${gateX} 37, ${gateX} 45`
}

function summarizeDecision(result: QuestionResult) {
  const decision = result.decision
  if (!decision) return 'Decision returned.'
  const answerItems = Object.entries(decision.answer ?? {}).slice(0, 4)
  if (answerItems.length) return answerItems.map(([key, value]) => `${key}: ${formatDecisionAnswerValue(value)}`).join(' · ')
  const conclusion = decision.conclusions?.[0]?.statement
  if (conclusion) return conclusion
  return `Decision ${decision.decision_id ?? ''} completed.`
}

function formatDecisionAnswerValue(value: unknown) {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}
