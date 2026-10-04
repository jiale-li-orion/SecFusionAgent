import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import {
  Activity,
  BookOpenCheck,
  BrainCircuit,
  ChevronRight,
  ArrowDownRight,
  CircleDot,
  GitFork,
  Orbit,
  Radio,
  Sparkles,
  TerminalSquare,
  TimerReset,
  Waypoints,
} from 'lucide-react'
import { getAgentLearning, getAgentRuntime, getAgentTask, type AgentRoleRuntime, type AgentTaskSummary, type ProductSkill } from '../lib/api'

const rolePresentation: Record<string, { alias: string; cn: string; tone: string; copy: string }> = {
  DecisionRole: { alias: 'ORACLE', cn: '判谕者', tone: 'cyan', copy: '把已验证 Context 收束为 Evidence-bounded Decision。' },
  InvestigationRole: { alias: 'ARGUS', cn: '百眼调查者', tone: 'violet', copy: '围绕 EvidenceNeed 调查、等待、恢复并决定是否委派。' },
  EnrichmentRole: { alias: 'ALCHEMIST', cn: '炼证者', tone: 'amber', copy: '运行富化 operator，把缺失事实推进 Evidence / Knowledge。' },
}

const activeStatuses = new Set(['submitted', 'queued', 'running', 'waiting_input', 'waiting_dependency'])

export function AgentsPage() {
  const runtimeQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 12_000 })
  const runtime = runtimeQuery.data
  const learningQuery = useQuery({ queryKey: ['agent-learning'], queryFn: getAgentLearning, refetchInterval: 30_000 })
  const learning = learningQuery.data
  const initialTask = runtime?.recent_tasks.find((task) => activeStatuses.has(task.status))?.run_id ?? runtime?.recent_tasks[0]?.run_id ?? null
  const [selectedTaskOverride, setSelectedTaskOverride] = useState<string | null>(null)
  const selectedTask = selectedTaskOverride ?? initialTask
  const detailQuery = useQuery({ queryKey: ['agent-task', selectedTask], queryFn: () => getAgentTask(selectedTask!), enabled: Boolean(selectedTask), refetchInterval: selectedTask ? 10_000 : false })
  const activeTasks = useMemo(() => runtime?.recent_tasks.filter((task) => activeStatuses.has(task.status)) ?? [], [runtime?.recent_tasks])
  const recentTasks = useMemo(() => runtime?.recent_tasks.filter((task) => !activeStatuses.has(task.status)).slice(0, 22) ?? [], [runtime?.recent_tasks])
  const skillFamilies = useMemo(() => groupSkillFamilies(learning?.skills ?? []), [learning?.skills])
  const [selectedSkillFamily, setSelectedSkillFamily] = useState<string | null>(null)
  const selectedSkill = skillFamilies.find((item) => item.key === (selectedSkillFamily ?? skillFamilies[0]?.key)) ?? null
  const activeCount = runtime?.roles.reduce((sum, role) => sum + role.active_tasks, 0) ?? 0
  const totalRuns = runtime?.roles.reduce((sum, role) => sum + role.total_tasks, 0) ?? 0

  return (
    <section className="agents-space-v3">
      <header className="agents-hero-v3">
        <div>
          <p>CANONICAL ROLE RUNTIME / M5</p>
          <h1>AGENT <span>MACHINE</span></h1>
          <small>Role · Task · Delegation · Capability · Skill · Experience · Recovery</small>
        </div>
        <div className="agent-runtime-readout-v3">
          <span className={activeCount > 0 ? 'live' : ''} />
          <div><small>ACTIVE TASKS</small><strong>{runtime ? activeCount : '—'}</strong></div>
          <div><small>DURABLE RUNS</small><strong>{runtime ? totalRuns : '—'}</strong></div>
          <div><small>CAPABILITY INVOCATIONS</small><strong>{runtime?.recent_capabilities.length ?? '—'}</strong></div>
        </div>
      </header>

      <div className="role-theater-v3">
        <div className="role-axis-v3" />
        {(runtime?.roles ?? []).map((role, index) => <RoleCard key={role.role_id} role={role} index={index} />)}
        {runtimeQuery.isLoading && <div className="role-loading-v3">RESOLVING CANONICAL ROLES…</div>}
      </div>

      <div className="agent-runtime-grid-v3">
        <section className="task-field-v3">
          <div className="instrument-section-head-v3">
            <div><small>DURABLE TASK FIELD</small><strong>EXECUTION / DELEGATION TOPOLOGY</strong></div>
            <span>{runtime?.recent_tasks.length ?? 0} loaded · real parent/child edges only</span>
          </div>

          <TaskTopology tasks={runtime?.recent_tasks ?? []} selectedTask={selectedTask} onSelect={setSelectedTaskOverride} />

          <div className="task-ledger-v3">
            <div className="task-ledger-column-v3 live">
              <div className="task-ledger-title-v3"><CircleDot size={12} /><strong>LIVE EXECUTION</strong><span>{activeTasks.length}</span></div>
              <div>
                {activeTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={setSelectedTaskOverride} />)}
                {runtime && activeTasks.length === 0 && <div className="task-ledger-empty-v3">No active durable tasks.</div>}
              </div>
            </div>
            <div className="task-ledger-column-v3 history">
              <div className="task-ledger-title-v3"><TimerReset size={12} /><strong>RECENT TERMINAL HISTORY</strong><span>{recentTasks.length}</span></div>
              <div>
                {recentTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={setSelectedTaskOverride} />)}
              </div>
            </div>
          </div>
        </section>

        <aside className="task-runtime-lens-v3">
          <div className="task-lens-head-v3">
            <div><small>SELECTED TASK</small><strong>{detailQuery.data?.task.task_kind ?? 'Select a task'}</strong></div>
            {detailQuery.data && <span className={`task-state state-${detailQuery.data.task.status}`}>{detailQuery.data.task.status}</span>}
          </div>
          {detailQuery.data ? <TaskDossier detail={detailQuery.data} /> : <div className="task-lens-empty-v3"><Waypoints size={32} /><strong>Task runtime lens</strong><p>选择一个 Task，查看 canonical Role、parent linkage、事件序列与真实 CapabilityInvocation。</p></div>}
        </aside>
      </div>

      <div className="agent-memory-complex-v3">
        <section className="skill-codex-v3">
          <div className="instrument-section-head-v3"><div><small>SKILL CODEX</small><strong>DURABLE PROCEDURAL MEMORY</strong></div><span>{learning?.skills.length ?? 0} records · {skillFamilies.length} families</span></div>
          <div className="skill-codex-body">
            <div className="skill-family-list">
              {skillFamilies.map((family) => <button key={family.key} className={family.key === selectedSkill?.key ? 'selected' : ''} onClick={() => setSelectedSkillFamily(family.key)}><span className="skill-glyph"><BookOpenCheck size={15} /></span><span><small>{family.records.map((item) => item.status).join(' · ')}</small><strong>{family.label}</strong><em>{family.records.length} durable records</em></span><ChevronRight size={14} /></button>)}
            </div>
            <div className="skill-detail">
              {selectedSkill ? <SkillFamilyDetail family={selectedSkill} /> : <div className="skill-empty">No durable Skills.</div>}
            </div>
          </div>
        </section>

        <section className="experience-memory-v3">
          <div className="instrument-section-head-v3"><div><small>EXPERIENCE MEMORY</small><strong>TRAJECTORY → EXPERIENCE → SKILL</strong></div><span>{learning?.experiences.length ?? 0} durable experiences</span></div>
          <ExperienceMemory learning={learning ?? null} />
        </section>
      </div>
    </section>
  )
}

function RoleCard({ role, index }: { role: AgentRoleRuntime; index: number }) {
  const presentation = rolePresentation[role.role_id] ?? { alias: role.role_id, cn: '', tone: 'cyan', copy: role.state_model }
  const live = role.active_tasks > 0
  const failed = role.status_counts.failed ?? 0
  const blocked = role.status_counts.blocked ?? 0
  return (
    <motion.article className={`role-entity-v3 role-${role.role_id.toLowerCase()} tone-${presentation.tone} ${live ? 'role-live' : ''}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .08 }}>
      <RoleSigil role={role.role_id} live={live} />
      <div className="role-entity-copy-v3">
        <small>{presentation.cn} / {role.role_id}@{role.version}</small>
        <strong>{presentation.alias}</strong>
        <p>{presentation.copy}</p>
        <div className="role-coordinates-v3"><span>{role.planner_profile}</span><span>{role.state_model}</span><span>{role.default_execution_profile}</span></div>
      </div>
      <div className="role-entity-runtime-v3">
        <b>{role.active_tasks}</b>
        <small>{live ? 'ACTIVE TASKS' : 'IDLE'}</small>
        <span>{role.total_tasks} durable runs</span>
        {(failed > 0 || blocked > 0) && <em>{failed} failed · {blocked} blocked</em>}
      </div>
    </motion.article>
  )
}

function RoleSigil({ role, live }: { role: string; live: boolean }) {
  if (role === 'DecisionRole') return <div className={`role-sigil oracle-sigil ${live ? 'live' : ''}`}><div className="orbit orbit-a" /><div className="orbit orbit-b" /><Sparkles size={22} /></div>
  if (role === 'InvestigationRole') return <div className={`role-sigil argus-sigil ${live ? 'live' : ''}`}><div className="argus-eye"><Radio size={22} /></div><i /><i /><i /></div>
  return <div className={`role-sigil alchemist-sigil ${live ? 'live' : ''}`}><div /><div /><div /><div /><Orbit size={20} /></div>
}

function TaskTopology({ tasks, selectedTask, onSelect }: { tasks: AgentTaskSummary[]; selectedTask: string | null; onSelect: (runId: string) => void }) {
  const topology = useMemo(() => buildTaskTopology(tasks, selectedTask), [tasks, selectedTask])
  const selectedModel = tasks.find((task) => task.run_id === selectedTask) ?? null
  const selectedCase = selectedModel?.case_id ?? null
  return <div className="task-topology">
    <div className="task-topology-head">
      <div className="task-role-axis"><span>ORACLE</span><span>ARGUS</span><span>ALCHEMIST</span></div>
      <div><small>REAL PARENT / CHILD LINKS ONLY</small><strong>{topology.nodes.length} visible nodes · {topology.edges.length} delegation links</strong></div>
    </div>
    <div className="task-topology-canvas">
      <div className="task-role-column role-decision" /><div className="task-role-column role-investigation" /><div className="task-role-column role-enrichment" />
      <svg className="task-topology-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {topology.edges.map((edge) => {
          const active = edge.parent.run_id === selectedTask || edge.child.run_id === selectedTask || Boolean(selectedCase && edge.parent.task.case_id === selectedCase && edge.child.task.case_id === selectedCase)
          return <path key={`${edge.parent.run_id}:${edge.child.run_id}`} className={active ? 'active' : selectedTask ? 'dimmed' : ''} d={`M ${edge.parent.x} ${edge.parent.y} C ${edge.parent.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${edge.child.y}`} />
        })}
      </svg>
      {topology.nodes.map((node) => {
        const task = node.task
        const related = !selectedTask || task.run_id === selectedTask || Boolean(selectedCase && task.case_id === selectedCase)
        return <motion.button
          key={task.run_id}
          className={`task-crystal state-${task.status} ${task.run_id === selectedTask ? 'selected' : ''} ${related ? '' : 'dimmed'}`}
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          onClick={() => onSelect(task.run_id)}
          initial={{ opacity: 0, scale: .75 }}
          animate={{ opacity: related ? 1 : .2, scale: task.run_id === selectedTask ? 1.1 : 1 }}
          transition={{ type: 'spring', stiffness: 230, damping: 25 }}
          title={`${task.role_id} · ${task.task_kind} · ${task.status}`}
        >
          <span className="task-crystal-core" />
          <span className="task-crystal-copy"><small>{rolePresentation[task.role_id]?.alias ?? task.role_id}</small><strong>{shortTaskKind(task.task_kind)}</strong><em>{task.status}</em></span>
          {task.parent_run_id && <GitFork size={10} className="task-child-mark" />}
        </motion.button>
      })}
      {topology.nodes.length === 0 && <div className="task-topology-empty">No durable TaskRun in current read window.</div>}
    </div>
  </div>
}

type TaskTopologyNode = { task: AgentTaskSummary; x: number; y: number; run_id: string }
type TaskTopologyEdge = { parent: TaskTopologyNode; child: TaskTopologyNode }

function buildTaskTopology(tasks: AgentTaskSummary[], selectedTask: string | null): { nodes: TaskTopologyNode[]; edges: TaskTopologyEdge[] } {
  const allById = new Map(tasks.map((task) => [task.run_id, task]))
  const chosen = new Map<string, AgentTaskSummary>()
  const selected = selectedTask ? allById.get(selectedTask) ?? null : null

  if (selected) {
    chosen.set(selected.run_id, selected)
    if (selected.parent_run_id && allById.has(selected.parent_run_id)) chosen.set(selected.parent_run_id, allById.get(selected.parent_run_id)!)
    for (const task of tasks) if (task.parent_run_id === selected.run_id || (selected.case_id && task.case_id === selected.case_id)) chosen.set(task.run_id, task)
  }
  for (const task of tasks) if (activeStatuses.has(task.status)) chosen.set(task.run_id, task)
  for (const task of tasks) {
    if (chosen.size >= 14) break
    if (task.parent_run_id && allById.has(task.parent_run_id)) {
      chosen.set(task.parent_run_id, allById.get(task.parent_run_id)!)
      chosen.set(task.run_id, task)
    }
  }
  for (const task of tasks) {
    if (chosen.size >= 14) break
    chosen.set(task.run_id, task)
  }

  const byRole = new Map<string, AgentTaskSummary[]>()
  for (const task of chosen.values()) byRole.set(task.role_id, [...(byRole.get(task.role_id) ?? []), task])
  const roleX: Record<string, number> = { DecisionRole: 17, InvestigationRole: 50, EnrichmentRole: 83 }
  const nodes: TaskTopologyNode[] = []
  for (const [role, roleTasks] of byRole) {
    const sorted = [...roleTasks].sort((a, b) => Number(activeStatuses.has(b.status)) - Number(activeStatuses.has(a.status)) || new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    sorted.slice(0, 6).forEach((task, index) => nodes.push({ task, run_id: task.run_id, x: roleX[role] ?? 50, y: 17 + index * 14 }))
  }
  const nodeById = new Map(nodes.map((node) => [node.run_id, node]))
  const edges: TaskTopologyEdge[] = []
  for (const node of nodes) {
    if (!node.task.parent_run_id) continue
    const parent = nodeById.get(node.task.parent_run_id)
    if (parent) edges.push({ parent, child: node })
  }
  return { nodes, edges }
}

function shortTaskKind(value: string) {
  const clean = value.replaceAll('_', ' ')
  return clean.length > 18 ? `${clean.slice(0, 16)}…` : clean
}

function TaskCard({ task, selected, onSelect }: { task: AgentTaskSummary; selected: boolean; onSelect: (runId: string) => void }) {
  const child = Boolean(task.parent_run_id)
  return (
    <button className={`task-ledger-row-v3 ${selected ? 'selected' : ''} state-${task.status}`} onClick={() => onSelect(task.run_id)}>
      <span className="task-role-mark">{rolePresentation[task.role_id]?.alias.slice(0, 2) ?? 'RT'}</span>
      <span className="task-main"><small>{task.role_id} · {child ? 'CHILD' : 'ROOT'}</small><strong>{humanize(task.task_kind)}</strong><em>{task.last_event_type ?? 'no event'} · {task.event_count} events</em></span>
      <span className="task-tail"><b>{task.status}</b>{child ? <GitFork size={12} /> : <ArrowDownRight size={12} />}</span>
    </button>
  )
}

function TaskDossier({ detail }: { detail: Awaited<ReturnType<typeof getAgentTask>> }) {
  const task = detail.task
  return (
    <div className="task-dossier-body">
      <div className="task-identity">
        <small>RUN ID</small><strong className="mono">{task.run_id}</strong>
        <div><span>{rolePresentation[task.role_id]?.alias ?? task.role_id}</span><span>{task.role_id}@{task.role_version}</span></div>
      </div>
      <div className="task-facts">
        <TaskFact label="CASE" value={task.case_id ?? 'standalone'} mono />
        <TaskFact label="PARENT" value={task.parent_run_id ?? 'root task'} mono />
        <TaskFact label="STOP REASON" value={task.stop_reason ?? (activeStatuses.has(task.status) ? 'in progress' : 'unspecified')} />
        <TaskFact label="UPDATED" value={new Date(task.updated_at).toLocaleString()} />
      </div>
      <div className="task-events-title"><Activity size={14} /><strong>EVENT TIMELINE</strong><span>{detail.events.length}</span></div>
      <div className="event-timeline">
        {detail.events.map((event, index) => (
          <motion.div key={event.event_id} className="event-row" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(index * .03, .25) }}>
            <span className="event-seq">{String(event.seq).padStart(2, '0')}</span>
            <span className="event-node" />
            <div><strong>{event.event_type}</strong><small>{event.producer} · {new Date(event.emitted_at).toLocaleTimeString()}</small></div>
          </motion.div>
        ))}
      </div>
      <div className="task-events-title"><TerminalSquare size={14} /><strong>CAPABILITY ACTIVITY</strong><span>{detail.capabilities.length}</span></div>
      {detail.capabilities.length ? detail.capabilities.map((item) => (
        <div key={item.invocation_id} className="capability-row"><div><small>{item.capability_id}</small><strong>{item.tool_impl_id}</strong></div><span>{item.status}</span></div>
      )) : <div className="capability-empty">No persisted CapabilityInvocation for this Task.</div>}
    </div>
  )
}

function TaskFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

function humanize(value: string) { return value.replaceAll('_', ' ').toUpperCase() }


type SkillFamily = { key: string; label: string; records: ProductSkill[] }

function groupSkillFamilies(skills: ProductSkill[]): SkillFamily[] {
  const groups = new Map<string, ProductSkill[]>()
  for (const skill of skills) {
    const tail = skill.skill_id.split('.').at(-1) ?? skill.skill_id
    const key = tail.replaceAll('_', '').toLowerCase()
    groups.set(key, [...(groups.get(key) ?? []), skill])
  }
  return [...groups.entries()].map(([key, records]) => ({
    key,
    label: preferredSkillLabel(records),
    records: [...records].sort((a, b) => statusRank(b.status) - statusRank(a.status)),
  })).sort((a, b) => a.label.localeCompare(b.label))
}

function preferredSkillLabel(records: ProductSkill[]) {
  const canonical = records.find((item) => /[A-Z]/.test(item.skill_id.split('.').at(-1) ?? '')) ?? records[0]
  return canonical?.skill_id.split('.').at(-1) ?? 'Skill'
}

function statusRank(status: string) { return ({ active: 5, validated: 4, candidate: 3, superseded: 2, deprecated: 1 } as Record<string, number>)[status] ?? 0 }

function SkillFamilyDetail({ family }: { family: SkillFamily }) {
  const primary = family.records[0]
  return <div className="skill-detail-stack">
    <div className="skill-detail-head"><div><small>SKILL FAMILY</small><strong>{family.label}</strong><span className="mono">{primary.skill_ref}</span></div><div className="skill-status-stack">{family.records.map((item) => <span key={item.skill_ref} className={`skill-status status-${item.status}`}>{item.status}</span>)}</div></div>
    <div className="skill-record-stack">{family.records.map((item) => <article key={item.skill_ref} className="skill-record"><div className="skill-record-title"><span>{item.source_type}</span><strong>{item.skill_id}@{item.version}</strong><b>{item.status}</b></div><div className="skill-chips">{item.task_patterns.map((value) => <span key={value}>{value}</span>)}{item.required_capability_classes.map((value) => <span key={value}>{value}</span>)}</div><div className="skill-procedure">{item.steps.map((step, index) => <div key={String(step.step_id ?? index)}><span>{String(index + 1).padStart(2,'0')}</span><p>{String(step.semantic_instruction ?? step.step_id ?? 'procedure step')}</p></div>)}</div>{item.failure_guards.length > 0 && <div className="skill-guards"><small>FAILURE GUARDS</small><p>{item.failure_guards.join(' · ')}</p></div>}{item.stop_conditions.length > 0 && <div className="skill-guards"><small>STOP CONDITIONS</small><p>{item.stop_conditions.join(' · ')}</p></div>}<div className="skill-provenance"><span>{item.provenance_origin}</span><span>{item.validation_ref ?? 'no validation ref'}</span></div></article>)}</div>
  </div>
}

function ExperienceMemory({ learning }: { learning: Awaited<ReturnType<typeof getAgentLearning>> | null }) {
  const stages = [
    ['Trajectory', learning?.trajectory_count ?? 0],
    ['Candidate', learning?.experience_candidate_count ?? 0],
    ['Experience', learning?.experiences.length ?? 0],
    ['Skill Patch', learning?.skills.filter((item) => item.source_type === 'experience_derived').length ?? 0],
  ] as const
  return <div className="experience-body">
    <div className="experience-pipeline">{stages.map(([label, count], index) => <div key={label} className="experience-stage"><span className="experience-stage-icon"><BrainCircuit size={16} /></span><div><small>STAGE {String(index + 1).padStart(2,'0')}</small><strong>{label}</strong><b>{count}</b></div>{index < stages.length - 1 && <ChevronRight size={14} className="experience-arrow" />}</div>)}</div>
    {(learning?.experiences.length ?? 0) === 0 ? <div className="experience-empty"><Orbit size={30} /><div><strong>NO DURABLE EXPERIENCE YET</strong><p>Experience pipeline 已实现，但当前数据库还没有 Trajectory / Experience record。这里明确保持空态，不用 demo memory 冒充学习结果。</p></div></div> : <div className="experience-list">{learning!.experiences.map((item) => <article key={item.experience_version_id}><small>{item.status}</small><strong>{item.name}</strong><span>{item.task_signature}</span><p>{item.recommended_actions.join(' · ')}</p></article>)}</div>}
  </div>
}
