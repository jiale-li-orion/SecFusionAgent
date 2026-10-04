import { useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  Eye,
  FlaskConical,
  Gauge,
  Orbit,
  ScanSearch,
  Send,
  Sparkles,
  Telescope,
} from 'lucide-react'
import { askQuestion, type QuestionResult, type TaskKind } from '../lib/api'

const modes = [
  {
    id: 'DIRECT',
    title: '快速回答',
    taskKind: 'lookup' as TaskKind,
    icon: Gauge,
    description: '从当前已确认 Evidence World 直接形成证据约束的回答。',
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
    description: '扩大本地检索上下文，保持 passage 与 canonical fact 的边界。',
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
    description: '围绕修复边界、版本与证据冲突启动 durable verification。',
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
    description: '进入多步调查，可选择 Skill / Capability 并在真实 runtime 中发生委派。',
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
    description: '保留 waiting Case，在外部世界或依赖变化后恢复下一 episode。',
    tempo: 'waiting',
    durable: 'durable waiting Case',
    outcome: 'Wake episode',
    capability: 'world-change recovery',
    role: 'ARGUS',
  },
]

const slots = [
  { left: 14, top: 33 },
  { left: 31, top: 17 },
  { left: 50, top: 12 },
  { left: 69, top: 17 },
  { left: 86, top: 33 },
]

export function StartPage() {
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [modeId, setModeId] = useState('VERIFY')
  const [question, setQuestion] = useState('')
  const [cveId, setCveId] = useState('')
  const [result, setResult] = useState<QuestionResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const selected = useMemo(() => modes.find((mode) => mode.id === modeId)!, [modeId])
  const selectedIndex = modes.findIndex((mode) => mode.id === modeId)

  async function launch() {
    if (!question.trim() || busy) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const response = await askQuestion({
        question: question.trim(),
        cveId: cveId.trim() || undefined,
        taskKind: selected.taskKind,
      })
      setResult(response)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="start-space-v3">
      <header className="start-hero-v3">
        <div>
          <p>GLOBAL TASK INJECTION / CANONICAL EXECUTION PROFILES</p>
          <h1>START <span>MISSION</span></h1>
          <small>选择的是系统执行边界、durability 与 Role 路由，不是聊天语气。</small>
        </div>
        <div className="start-route-legend-v3">
          <span><i className="oracle" />DIRECT / RETRIEVE → ORACLE</span>
          <span><i className="argus" />VERIFY / INVESTIGATE / WATCH → ARGUS</span>
        </div>
      </header>

      <div className={`start-theater-v3 ${busy ? 'is-launching' : ''}`}>
        <svg className="start-orbit-map-v3" viewBox="0 0 100 58" preserveAspectRatio="none" aria-hidden="true">
          <ellipse cx="50" cy="31" rx="39" ry="21" />
          <ellipse cx="50" cy="31" rx="27" ry="15" className="inner" />
          <path className="axis" d="M 7 44 C 28 32, 38 30, 50 31 C 62 30, 72 32, 93 44" />
          <motion.path
            className={`selected-route role-${selected.role.toLowerCase()}`}
            d={missionRoute(selectedIndex, selected.role)}
            initial={false}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: reduceMotion ? 0 : .42, ease: 'easeOut' }}
          />
        </svg>

        <div className="start-role-gate-v3 oracle">
          <span className="role-gate-sigil-v3"><Orbit size={18} /></span>
          <small>DECISION ROLE</small>
          <strong>ORACLE</strong>
          <em>DIRECT · RETRIEVE</em>
        </div>

        <div className="start-role-gate-v3 argus">
          <span className="role-gate-sigil-v3"><Orbit size={18} /></span>
          <small>INVESTIGATION ROLE</small>
          <strong>ARGUS</strong>
          <em>VERIFY · INVESTIGATE · WATCH</em>
        </div>

        {modes.map(({ id, title, icon: Icon, role }, index) => {
          const active = id === modeId
          const slot = slots[index]
          return (
            <motion.button
              key={id}
              className={`mode-chamber-v3 ${active ? 'active' : ''} role-${role.toLowerCase()}`}
              style={{ left: `${slot.left}%`, top: `${slot.top}%` }}
              onClick={() => {
                setModeId(id)
                setResult(null)
                setError('')
              }}
              animate={{
                y: active ? 20 : 0,
                scale: active ? 1.08 : .96,
                opacity: active ? 1 : .62,
              }}
              transition={{ type: 'spring', stiffness: 220, damping: 24 }}
            >
              <span className="mode-chamber-index-v3">0{index + 1}</span>
              <span className="mode-chamber-glyph-v3"><Icon size={active ? 23 : 18} /></span>
              <small>{title}</small>
              <strong>{id}</strong>
              <em>{role}</em>
              {active && <i />}
            </motion.button>
          )
        })}

        <motion.div
          className={`mission-reactor-v3 ${busy ? 'active' : ''} role-${selected.role.toLowerCase()}`}
          animate={{ scale: busy && !reduceMotion ? [1, 1.05, 1] : 1 }}
          transition={{ duration: .9, repeat: busy && !reduceMotion ? Infinity : 0 }}
        >
          <span className="reactor-ring-v3 ring-a" />
          <span className="reactor-ring-v3 ring-b" />
          <Sparkles size={21} />
          <strong>{busy ? 'LAUNCH' : selected.id}</strong>
          <small>{selected.role}</small>
        </motion.div>

        <motion.div
          key={selected.id}
          className="mode-readout-v3"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <span>{selected.title}</span>
          <strong>{selected.description}</strong>
          <div>
            <ModeFact label="INTERACTION" value={selected.tempo} />
            <ModeFact label="CASE" value={selected.durable} />
            <ModeFact label="OUTCOME" value={selected.outcome} />
            <ModeFact label="CAPABILITY" value={selected.capability} />
          </div>
        </motion.div>

        <div className="alchemist-boundary-v3">
          <span>ALCHEMIST</span>
          <small>appears only when runtime persists a real enrichment child Task</small>
        </div>
      </div>

      <div className="payload-deck-v3">
        <div className="payload-deck-head-v3">
          <div><small>MISSION PAYLOAD</small><strong>{selected.id} → {selected.role}</strong></div>
          <span>Question API / Product contract</span>
        </div>

        <div className="payload-grid-v3">
          <label className="payload-field-v3 target">
            <span>TARGET / OPTIONAL</span>
            <input
              className="mono"
              value={cveId}
              onChange={(event) => setCveId(event.target.value)}
              placeholder="CVE-2026-…"
            />
          </label>

          <label className="payload-field-v3 prompt">
            <span>MISSION PROMPT</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="要核验什么？证据缺口是什么？"
            />
          </label>

          <button className={`payload-launch-v3 role-${selected.role.toLowerCase()}`} onClick={launch} disabled={busy || !question.trim()}>
            <span><Send size={16} /></span>
            <small>{busy ? 'REQUEST IN FLIGHT' : 'EXECUTE PROFILE'}</small>
            <strong>{busy ? 'LAUNCHING…' : `LAUNCH ${selected.id}`}</strong>
          </button>
        </div>

        {(error || result) && (
          <motion.div
            className={`start-outcome-v3 ${error ? 'error' : result?.mode === 'accepted' ? 'accepted' : 'completed'}`}
            initial={{ opacity: 0, y: 12, clipPath: 'inset(0 0 70% 0)' }}
            animate={{ opacity: 1, y: 0, clipPath: 'inset(0 0 0% 0)' }}
          >
            {error ? (
              <>
                <small>REQUEST FAILED</small>
                <strong>{error}</strong>
              </>
            ) : result ? (
              <>
                <small>{result.mode === 'accepted' ? 'INVESTIGATION ACCEPTED' : 'DECISION READY'}</small>
                <strong>{result.execution_profile}</strong>
                <span>{result.mode === 'accepted' ? `Case ${result.investigation?.case_id ?? 'created'}` : summarizeDecision(result)}</span>
                <em className="mono">session {result.session_id} · turn {result.turn_index}</em>
                {result.mode === 'accepted' && result.investigation?.case_id && (
                  <button onClick={() => navigate(`/investigations?case=${encodeURIComponent(result.investigation!.case_id)}&session=${encodeURIComponent(result.session_id)}`)}>
                    ENTER DURABLE CASE <ArrowUpRight size={13} />
                  </button>
                )}
              </>
            ) : null}
          </motion.div>
        )}
      </div>
    </section>
  )
}

function ModeFact({ label, value }: { label: string; value: string }) {
  return <span><small>{label}</small><strong>{value}</strong></span>
}

function missionRoute(index: number, role: string) {
  const slot = slots[index]
  const gateX = role === 'ORACLE' ? 8 : 92
  return `M ${slot.left} ${slot.top * .58} C ${slot.left} 28, 50 29, 50 31 C 50 35, ${gateX} 35, ${gateX} 44`
}

function summarizeDecision(result: QuestionResult) {
  const decision = result.decision
  if (!decision) return 'Decision returned.'
  const answer = decision.answer ?? decision.recommendation
  if (typeof answer === 'string' && answer.trim()) return answer
  return `Decision ${decision.decision_id ?? ''} completed.`
}
