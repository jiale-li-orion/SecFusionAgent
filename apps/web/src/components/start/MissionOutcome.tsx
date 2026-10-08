import { useState } from 'react'
import { AnimatePresence } from 'motion/react'
import { ArrowUpRight, BrainCircuit, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { QuestionResult } from '../../lib/api'
import { investigationStopMessage } from '../../lib/investigationPresentation'
import { missionTargetDossierPath, modeTitleEn } from '../../lib/startMissionPresentation'
import { useI18n } from '../../lib/i18n'
import { DecisionReport } from '../DecisionReport'
import { EvidenceOverlay } from '../investigations/CaseSurfaces'

const statusLabels: Record<string, [string, string]> = {
  active: ['正在调查', 'Investigation in progress'], waiting: ['等待新证据', 'Waiting for new evidence'],
  resolved: ['调查已完成', 'Investigation complete'], failed: ['调查已停止', 'Investigation stopped'],
  cancelled: ['调查已取消', 'Investigation cancelled'], closed: ['调查已关闭', 'Investigation closed'],
}
const phaseLabels: Record<string, [string, string]> = {
  queued: ['等待执行', 'Queued'], running: ['正在收集与核对证据', 'Collecting and checking evidence'],
  waiting: ['等待依赖或新材料', 'Waiting for dependencies or new material'],
  waiting_dependency: ['等待依赖到达', 'Waiting for dependencies'],
  waiting_input: ['等待补充信息', 'Waiting for input'], completed: ['本轮执行已结束', 'Episode finished'],
}
const profileLabels: Record<string, string> = { DIRECT: '快速回答', RETRIEVE: '证据检索', VERIFY: '精准核验', INVESTIGATE: '深度调查', WATCH: '持续守望' }

type Props = {
  result: QuestionResult
  target: string
  cancelling?: boolean
  cancelError?: string
  onCancel?: (caseId: string) => void
}

export function MissionOutcome({ result, target, cancelling, cancelError, onCancel }: Props) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [evidence, setEvidence] = useState<string | null>(null)
  const investigation = result.investigation
  const casePath = investigation ? `/investigations?${new URLSearchParams({ case: investigation.case_id, session: result.session_id, from: 'start', request: result.request_id })}` : null
  const dossierPath = missionTargetDossierPath(target, result.request_id)
  const profileLabel = text(profileLabels[result.execution_profile] ?? result.execution_profile, modeTitleEn(result.execution_profile))
  if (result.mode === 'accepted') {
    const status = investigation?.status ?? 'active'
    const phase = investigation?.current_activity?.phase
    const statusLabel = statusLabels[status]
    const phaseLabel = phase ? phaseLabels[phase] : null
    const terminal = !['active', 'waiting'].includes(status)
    return <div className={`start-case-outcome state-${status}`}>
      <div className="mission-case-heading">
        <div><small>ARGUS / {profileLabel}</small><h2>{statusLabel ? text(...statusLabel) : status}</h2></div>
        <span className={`mission-case-state ${terminal ? 'terminal' : ''}`}>{terminal ? text('本次执行已结束', 'Execution ended') : text('状态自动更新', 'Status updates automatically')}</span>
      </div>
      <p className="mission-case-goal">{investigation?.goal}</p>
      {phaseLabel && !terminal && <p>{text(...phaseLabel)}</p>}
      {status === 'waiting' && <p>{text('调查会在所需依赖变化后恢复。你可以进入调查现场查看缺口，或在同一会话中补充线索。', 'The investigation resumes when its dependencies change. Review the gaps or add a lead in this conversation.')}</p>}
      {terminal && investigation?.terminal_reason && <p>{investigationStopMessage(investigation.terminal_reason, text)}</p>}
      {investigation && <dl className="mission-case-facts">
        <div><dt>{text('已确认发现', 'Confirmed findings')}</dt><dd>{investigation.confirmed_findings.length}</dd></div>
        <div><dt>{text('待补充证据', 'Open evidence needs')}</dt><dd>{investigation.open_evidence_needs.length}</dd></div>
        <div><dt>{text('来源冲突', 'Source conflicts')}</dt><dd>{investigation.conflicts.length}</dd></div>
      </dl>}
      {investigation?.open_evidence_needs.length ? <div className="mission-open-needs"><small>{text('下一步需要确认', 'Still to establish')}</small><ul>{investigation.open_evidence_needs.slice(0, 3).map(need => <li key={need.need_id}>{need.question}</li>)}</ul></div> : null}
      <div className="start-decision-next">
        {casePath && <button onClick={() => navigate(casePath)}>{text('查看调查进展', 'View investigation')}<ArrowUpRight size={13} /></button>}
        {dossierPath && <button onClick={() => navigate(dossierPath)}>{text('打开目标档案', 'Open target dossier')}</button>}
        {investigation?.can_cancel && onCancel && <button className="mission-cancel" disabled={cancelling} onClick={() => onCancel(investigation.case_id)}>{cancelling ? text('正在停止…', 'Stopping…') : text('停止调查', 'Stop investigation')}</button>}
      </div>
      {cancelError && <p role="alert">{cancelError}</p>}
      {investigation && <details className="mission-run-details"><summary>{text('执行详情', 'Execution details')}</summary><p className="mono">{investigation.case_id}</p><p>{text('最后更新', 'Last updated')} · {new Date(investigation.updated_at).toLocaleString()}</p>{phase && <p>{phase}</p>}{investigation.terminal_reason && <p>{investigation.terminal_reason}</p>}</details>}
    </div>
  }
  return <>
    <div className="start-decision-outcome">
      <div className="decision-seal"><Sparkles size={18} /><i /></div>
      <div><small>{text('ORACLE / 研判已生成', 'ORACLE / DECISION READY')}</small><strong>{profileLabel}</strong>
        {result.decision && <DecisionReport decision={result.decision} onEvidence={setEvidence} />}
        {(dossierPath || casePath) && <div className="start-decision-next">
          {dossierPath && <button onClick={() => navigate(dossierPath)}><BrainCircuit size={12} />{text('打开目标档案', 'Open target dossier')}</button>}
          {casePath && <button onClick={() => navigate(casePath)}>{text('查看完整调查', 'View full investigation')}<ArrowUpRight size={13} /></button>}
        </div>}
        {result.session_id && <small>{text('会话回合', 'Conversation turn')} {result.turn_index} · {text('可在上方继续追问', 'Continue the conversation above')}</small>}
      </div>
    </div>
    <AnimatePresence>{evidence && <EvidenceOverlay key={evidence} evidenceRef={evidence} onClose={() => setEvidence(null)} />}</AnimatePresence>
  </>
}
