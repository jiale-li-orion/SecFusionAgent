import { useState } from 'react'
import { AnimatePresence } from 'motion/react'
import { ArrowUpRight, BrainCircuit, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { QuestionResult } from '../../lib/api'
import { missionTargetDossierPath } from '../../lib/startMissionPresentation'
import { useI18n } from '../../lib/i18n'
import { DecisionReport } from '../DecisionReport'
import { EvidenceOverlay } from '../investigations/CaseSurfaces'

export function MissionOutcome({ result, target }: { result: QuestionResult; target: string }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [evidence, setEvidence] = useState<string | null>(null)
  if (result.mode === 'accepted') return <div className="start-case-outcome">
    <div className="case-outcome-axis"><span /><i /><b /></div>
    <div><small>{text('ARGUS / 调查已接收', 'ARGUS / CASE ACCEPTED')}</small><strong>{result.execution_profile}</strong><span>{result.investigation?.goal}</span><em className="mono">{result.investigation?.case_id} · {result.investigation?.status}</em></div>
    {result.investigation?.case_id && <button onClick={() => navigate(`/investigations?${new URLSearchParams({ case: result.investigation!.case_id, session: result.session_id, from: 'start', request: result.request_id })}`)}>{text('进入调查现场', 'ENTER CASE FIELD')}<ArrowUpRight size={13} /></button>}
  </div>
  const dossierPath = missionTargetDossierPath(target, result.request_id)
  return <>
    <div className="start-decision-outcome">
      <div className="decision-seal"><Sparkles size={18} /><i /></div>
      <div><small>{text('ORACLE / 研判已生成', 'ORACLE / DECISION READY')}</small><strong>{result.execution_profile}</strong>
        {result.decision && <DecisionReport decision={result.decision} onEvidence={setEvidence} />}
        {dossierPath && <div className="start-decision-next"><button onClick={() => navigate(dossierPath)}><BrainCircuit size={12} />{text('打开目标档案', 'OPEN TARGET DOSSIER')}</button></div>}
        {result.session_id && <em className="mono">{text('当前会话', 'SESSION')} {result.session_id} · {text('回合', 'TURN')} {result.turn_index}</em>}
      </div>
    </div>
    <AnimatePresence>{evidence && <EvidenceOverlay key={evidence} evidenceRef={evidence} onClose={() => setEvidence(null)} />}</AnimatePresence>
  </>
}
