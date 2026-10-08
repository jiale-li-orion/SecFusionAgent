import { HeroArtifact } from '../instrument/HeroArtifact'
import { motion, useReducedMotion } from 'motion/react'
import { ProductGlyph } from '../instrument/ProductGlyph'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight, CircleDot } from 'lucide-react'
import { useI18n } from '../../lib/i18n'
import { modeDescriptionEn, modeTitleEn } from '../../lib/startMissionPresentation'

type MissionMode = { id: string; title: string; icon: LucideIcon; role: string; description: string; tempo: string; durable: string; outcome: string; capability: string }

export function MissionField({ modes, selected, busy, onSelect, children }: { modes: MissionMode[]; selected: MissionMode; busy: boolean; onSelect: (id: string) => void; children: React.ReactNode }) {
  const {text}=useI18n();const reduced=useReducedMotion()
  return <div className="vision-mission">
    <div className="vision-mission-rail"><span>{text('选择如何展开','CHOOSE AN APPROACH')}</span><div className="mission-profile-options" role="group" aria-label={text('执行模式','Execution mode')}>{modes.map((mode,index)=><button key={mode.id} data-mission-mode={mode.id} className={`vision-mode ${selected.id===mode.id?'active':''}`} aria-pressed={selected.id===mode.id} disabled={busy} onClick={()=>onSelect(mode.id)}><small>0{index+1}</small><ProductGlyph kind={mode.id} size={25}/><span><strong>{text(mode.title,modeTitleEn(mode.id))}</strong><small>{mode.id}</small></span><ArrowRight size={15}/></button>)}</div></div>
    <motion.div key={selected.role} className="vision-mission-sculpture" initial={reduced?false:{opacity:0,scale:.96}} animate={{opacity:1,scale:1}} transition={{duration:.35}}><HeroArtifact kind={selected.role==='ORACLE'?'DecisionRole':'InvestigationRole'}/><span>{selected.role}</span></motion.div>
    <section className="vision-mission-intent" aria-live="polite"><small>{text('当前执行方式','SELECTED APPROACH')}</small><h2>{text(selected.title,modeTitleEn(selected.id))}</h2><p>{text(selected.description,modeDescriptionEn(selected.id))}</p><div className="vision-mission-path"><span>{text('问题与目标','QUESTION + TARGET')}</span><ArrowRight size={14}/><strong>{selected.role}</strong><ArrowRight size={14}/><span>{selected.role==='ORACLE'?text('有引用的研判','CITED DECISION'):text('持续调查','CONTINUING CASE')}</span></div></section>
    <div className="vision-mission-boundary">{children}</div>
    {busy&&<p className="mission-submit-status" role="status"><CircleDot size={16}/>{text('正在提交，等待运行结果…','Submitting, awaiting the runtime…')}</p>}
  </div>
}
