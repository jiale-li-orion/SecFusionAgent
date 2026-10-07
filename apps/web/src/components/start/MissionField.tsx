import type { LucideIcon } from 'lucide-react'
import { ArrowRight, CircleDot } from 'lucide-react'
import { useI18n } from '../../lib/i18n'
import { modeDescriptionEn, modeTitleEn } from '../../lib/startMissionPresentation'

type MissionMode = {
  id: string; title: string; icon: LucideIcon; role: string; description: string
  tempo: string; durable: string; outcome: string; capability: string
}

export function MissionField({ modes, selected, busy, onSelect, children }: {
  modes: MissionMode[]; selected: MissionMode; busy: boolean
  onSelect: (id: string) => void; children: React.ReactNode
}) {
  const { text } = useI18n()
  const Icon = selected.icon
  return <div className="start-theater mission-field-rebuilt">
    <header className="mission-field-heading"><span>01 / {text('选择求知方式', 'CHOOSE HOW TO INVESTIGATE')}</span><small>{text('从当前证据，到持续调查', 'FROM CURRENT EVIDENCE TO CONTINUOUS INVESTIGATION')}</small></header>
    <div className="mission-profile-options" role="group" aria-label={text('执行模式', 'Execution mode')}>
      {modes.map((mode, index) => <button key={mode.id} data-mission-mode={mode.id} className={`mission-profile-option ${selected.id === mode.id ? 'active' : ''}`} aria-pressed={selected.id === mode.id} disabled={busy} onClick={() => onSelect(mode.id)}>
        <span className="mission-profile-number">0{index + 1}<mode.icon size={20} /></span>
        <strong>{mode.id}</strong><span>{text(mode.title, modeTitleEn(mode.id))}</span><small>{mode.role}</small>
      </button>)}
    </div>
    <section className={`mission-profile-detail role-${selected.role.toLowerCase()}`} aria-live="polite">
      <div className="mission-profile-identity"><span><Icon size={32} /></span><div><small>{text('当前执行路径', 'SELECTED EXECUTION PATH')}</small><h2>{text(selected.title, modeTitleEn(selected.id))}</h2></div><b>{selected.role}</b></div>
      <p>{text(selected.description, modeDescriptionEn(selected.id))}</p>
      <dl><div><dt>{text('响应节奏', 'TEMPO')}</dt><dd>{selected.tempo}</dd></div><div><dt>{text('持久状态', 'DURABILITY')}</dt><dd>{selected.durable}</dd></div><div><dt>{text('结果形态', 'OUTCOME')}</dt><dd>{selected.outcome}</dd></div><div><dt>{text('允许能力', 'CAPABILITY')}</dt><dd>{selected.capability}</dd></div></dl>
      <div className="mission-execution-path"><span>{text('问题与目标', 'QUESTION + TARGET')}</span><ArrowRight size={15} /><strong>{selected.role}</strong><ArrowRight size={15} /><span>{selected.role === 'ORACLE' ? text('有引用的研判', 'CITED DECISION') : text('持续调查与研判', 'DURABLE CASE + DECISION')}</span></div>
    </section>
    <div className="mission-runtime-boundary">{children}</div>
    {busy && <p className="mission-submit-status" role="status"><CircleDot size={16} />{text('正在提交，等待真实运行结果…', 'SUBMITTING · WAITING FOR THE RUNTIME…')}</p>}
  </div>
}
