import { HeroArtifact } from '../instrument/HeroArtifact'
import { RoleSigil } from '../instrument/RoleSigil'
import { ArrowRight } from 'lucide-react'
import type { AgentRoleRuntime } from '../../lib/api'
import { rolePresentation } from '../../lib/agentRuntimePresentation'
import { useI18n } from '../../lib/i18n'

const roles=['DecisionRole','InvestigationRole','EnrichmentRole']
const descriptions:Record<string,[string,string]>={
  DecisionRole:['整理已有证据，给出有引用的判断，并标明冲突与未决问题。','Turn existing evidence into cited judgments, with conflicts and open questions kept explicit.'],
  InvestigationRole:['沿着问题追踪来源，核验事实，在证据不足时继续寻找线索。','Trace sources, verify facts and follow the gaps that still need evidence.'],
  EnrichmentRole:['读取原始材料、解析关联对象，把可以确认的证据补充到情报世界。','Read original material, resolve related objects and retain the evidence that can be verified.'],
}
export function RoleConstellation({runtime,selected,focused,onFocus}:{runtime:AgentRoleRuntime[]|undefined;selected:string|null;focused:string|null;onFocus:(role:string|null)=>void}) {
  const {text}=useI18n()
  const primary=focused??(selected&&roles.includes(selected)?selected:'DecisionRole')
  const presentation=rolePresentation[primary]
  const state=runtime?.find(r=>r.role_id===primary)
  return <section className={`vision-role-stage role-${primary.toLowerCase()}`}>
    <div className="vision-role-portrait"><HeroArtifact kind={primary}/></div>
    <div className="vision-role-story"><small>{text(presentation.cn,presentation.alias)}{selected===primary?text(' · 当前任务归属',' · SELECTED TASK OWNER'):''}</small><h2>{presentation.alias}</h2><p>{text(...descriptions[primary])}</p><div className="vision-role-measure">{state?<><strong>{state.active_tasks>0?text(`${state.active_tasks} 个任务执行中`,`${state.active_tasks} active tasks`):text('当前空闲','Currently idle')}</strong><span>{text(`已保留 ${state.total_tasks} 次执行`,`${state.total_tasks} retained executions`)}</span></>:<span>{text('尚未读取角色运行状态','Role runtime is not available yet')}</span>}</div>{focused&&<button onClick={()=>onFocus(null)}>{text('查看所有角色的任务','View tasks from all roles')}<ArrowRight size={14}/></button>}</div>
    <div className="vision-role-selectors" role="group" aria-label={text('选择角色','Choose a role')}>{roles.map(id=>{const p=rolePresentation[id];const r=runtime?.find(item=>item.role_id===id);return <button key={id} aria-pressed={primary===id} className={primary===id?'selected':''} onClick={()=>onFocus(focused===id?null:id)}><RoleSigil role={id} live={(r?.active_tasks??0)>0}/><span><strong>{p.alias}</strong><small>{text(p.cn,p.alias)}</small></span><ArrowRight size={14}/></button>})}</div>
  </section>
}
