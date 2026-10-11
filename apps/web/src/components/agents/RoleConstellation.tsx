import { BrainCircuit, Radar, Sparkles, ArrowUpRight } from '../ui/icons'
import { Card } from '../ui/card'
import { Badge } from '../ui/badge'
import type { AgentRoleRuntime } from '../../lib/api'
import { rolePresentation } from '../../lib/agentRuntimePresentation'
import { useI18n } from '../../lib/i18n'
import './role-cards.css'

const roles = [
  { id: 'DecisionRole', icon: BrainCircuit, zh: '研判与回答', en: 'Reasoning & answers', detail: ['整理已有证据，给出有引用的判断。', 'Turn evidence into clear, cited judgments.'] },
  { id: 'InvestigationRole', icon: Radar, zh: '调查与核验', en: 'Investigation & verification', detail: ['追踪来源，核验事实，持续寻找线索。', 'Trace sources, verify facts, and follow new leads.'] },
  { id: 'EnrichmentRole', icon: Sparkles, zh: '知识富化', en: 'Knowledge enrichment', detail: ['读取材料，连接对象，补充可信证据。', 'Read material, connect objects, and retain evidence.'] },
] as const

export function RoleConstellation({ runtime, selected, focused, onFocus }: { runtime: AgentRoleRuntime[] | undefined; selected: string | null; focused: string | null; onFocus: (role: string | null) => void }) {
  const { text } = useI18n()
  return <div className="agent-role-cards" role="group" aria-label={text('按协作角色查看任务', 'Filter tasks by agent role')}>
    {roles.map(({ id, icon: Icon, zh, en, detail }) => {
      const state = runtime?.find(role => role.role_id === id)
      return <Card key={id} className={`agent-role-card role-${id} ${focused === id ? 'is-focused' : ''}`}>
        <button className="agent-role-select" onClick={() => onFocus(focused === id ? null : id)} aria-pressed={focused === id}>
          <span className="agent-role-symbol"><Icon size={25}/></span>
          <span className="agent-role-identity"><small>{rolePresentation[id].alias}</small><strong>{text(zh,en)}</strong></span><ArrowUpRight size={16}/>
          <p>{text(detail[0], detail[1])}</p>
          <span className="agent-role-readout">{state ? <><Badge variant={state.active_tasks ? 'default' : 'secondary'}>{state.active_tasks ? text(`${state.active_tasks} 个执行中`, `${state.active_tasks} active`) : text('空闲', 'Idle')}</Badge><span>{state.total_tasks} {text('次运行', 'runs')}</span></> : <span>{text('读取状态中…', 'Loading state…')}</span>}{selected === id && <em>{text('当前任务', 'Selected task')}</em>}</span>
        </button>
      </Card>
    })}
  </div>
}
