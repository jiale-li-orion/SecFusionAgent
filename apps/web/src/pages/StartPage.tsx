import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { Eye, FlaskConical, Gauge, Radar, ScanSearch, Send, Sparkles, Telescope } from 'lucide-react'
import { askQuestion, type QuestionResult, type TaskKind } from '../lib/api'

const modes = [
  { id: 'DIRECT', title: '快速回答', taskKind: 'lookup' as TaskKind, icon: Gauge, tone: 'lime', description: '从当前已确认 Evidence World 直接形成证据约束的回答。' },
  { id: 'RETRIEVE', title: '证据检索', taskKind: 'retrieve' as TaskKind, icon: ScanSearch, tone: 'cyan', description: '扩大本地检索上下文，保持 passage 与 canonical fact 的边界。' },
  { id: 'VERIFY', title: '精准核验', taskKind: 'verify_version_fix' as TaskKind, icon: FlaskConical, tone: 'violet', description: '围绕修复边界、版本与证据冲突启动 durable verification。' },
  { id: 'INVESTIGATE', title: '深度调查', taskKind: 'investigate_incident' as TaskKind, icon: Telescope, tone: 'amber', description: '进入多步调查，可选择 Skill / Capability 并发生真实委派。' },
  { id: 'WATCH', title: '持续守望', taskKind: 'watch_incident' as TaskKind, icon: Eye, tone: 'blue', description: '保留 waiting Case，在外部世界变化后恢复调查。' },
]

export function StartPage() {
  const [modeId, setModeId] = useState('VERIFY')
  const [question, setQuestion] = useState('')
  const [cveId, setCveId] = useState('')
  const [result, setResult] = useState<QuestionResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const selected = useMemo(() => modes.find((m) => m.id === modeId)!, [modeId])

  async function launch() {
    if (!question.trim()) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const response = await askQuestion({ question: question.trim(), cveId: cveId.trim() || undefined, taskKind: selected.taskKind })
      setResult(response)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page start-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">FIVE OPERATING MODES · ONE RUNTIME</p>
          <h1>START YOUR MISSION</h1>
          <p className="lede">选的不是聊天风格，而是系统真实的执行边界。</p>
        </div>
      </div>

      <div className="mission-layout">
        <div className="mission-stage panel-glass">
          <div className="mission-orbits" />
          <div className="mode-grid">
            {modes.map(({ id, title, icon: Icon, tone, description }) => {
              const active = id === modeId
              return (
                <motion.button
                  key={id}
                  onClick={() => setModeId(id)}
                  className={`mode-pod tone-${tone} ${active ? 'active' : ''}`}
                  animate={{ y: active ? -10 : 0, scale: active ? 1.035 : 1 }}
                  transition={{ type: 'spring', stiffness: 220, damping: 22 }}
                >
                  <span className="mode-sigil"><Icon size={24} /></span>
                  <small>{title}</small>
                  <strong>{id}</strong>
                  <p>{description}</p>
                </motion.button>
              )
            })}
          </div>

          <motion.div key={selected.id} className={`launch-core tone-${selected.tone}`} initial={{ scale: 0.96 }} animate={{ scale: 1 }}>
            <Sparkles size={18} />
            <strong>{selected.id}</strong>
            <small>{selected.title}</small>
          </motion.div>
        </div>

        <aside className="mission-console panel-glass">
          <div className="console-title">
            <span className={`signal-icon ${selected.tone}`}><Radar size={18} /></span>
            <div><small>SELECTED PROFILE</small><strong>{selected.id}</strong></div>
          </div>
          <p className="console-description">{selected.description}</p>

          <label className="field-label">Target CVE <span>optional</span></label>
          <input className="field-input mono" value={cveId} onChange={(e) => setCveId(e.target.value)} placeholder="CVE-2026-…" />

          <label className="field-label">Mission prompt</label>
          <textarea className="field-textarea" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="要核验什么？证据缺口是什么？" />

          <button className="launch-button" onClick={launch} disabled={busy || !question.trim()}>
            {busy ? 'LAUNCHING…' : <>LAUNCH {selected.id} <Send size={16} /></>}
          </button>

          {error && <div className="result-block error-block">{error}</div>}
          {result && (
            <motion.div className="result-block" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <small>{result.mode === 'accepted' ? 'INVESTIGATION ACCEPTED' : 'DECISION READY'}</small>
              <strong>{result.execution_profile}</strong>
              <p>{result.mode === 'accepted' ? `Case ${result.investigation?.case_id ?? ''}` : summarizeDecision(result)}</p>
              <span className="mono tiny">session {result.session_id}</span>
            </motion.div>
          )}
        </aside>
      </div>
    </section>
  )
}

function summarizeDecision(result: QuestionResult) {
  const decision = result.decision
  if (!decision) return 'Decision returned.'
  const answer = decision.answer ?? decision.recommendation
  if (typeof answer === 'string' && answer.trim()) return answer
  return `Decision ${decision.decision_id ?? ''} completed.`
}
