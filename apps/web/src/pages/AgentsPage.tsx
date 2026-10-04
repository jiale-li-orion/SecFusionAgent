import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import {
  Activity,
  ArrowDownRight,
  CircleDot,
  GitFork,
  Orbit,
  Radio,
  Sparkles,
  TerminalSquare,
  TimerReset,
  Waypoints,
  XCircle,
} from 'lucide-react'
import { getAgentRuntime, getAgentTask, type AgentRoleRuntime, type AgentTaskSummary } from '../lib/api'

const rolePresentation: Record<string, { alias: string; cn: string; tone: string; copy: string }> = {
  DecisionRole: { alias: 'ORACLE', cn: '判谕者', tone: 'cyan', copy: '把已验证 Context 收束为 Evidence-bounded Decision。' },
  InvestigationRole: { alias: 'ARGUS', cn: '百眼调查者', tone: 'violet', copy: '围绕 EvidenceNeed 调查、等待、恢复并决定是否委派。' },
  EnrichmentRole: { alias: 'ALCHEMIST', cn: '炼证者', tone: 'amber', copy: '运行富化 operator，把缺失事实推进 Evidence / Knowledge。' },
}

const activeStatuses = new Set(['submitted', 'queued', 'running', 'waiting_input', 'waiting_dependency'])

export function AgentsPage() {
  const runtimeQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 12_000 })
  const runtime = runtimeQuery.data
  const initialTask = runtime?.recent_tasks.find((task) => activeStatuses.has(task.status))?.run_id ?? runtime?.recent_tasks[0]?.run_id ?? null
  const [selectedTaskOverride, setSelectedTaskOverride] = useState<string | null>(null)
  const selectedTask = selectedTaskOverride ?? initialTask
  const detailQuery = useQuery({ queryKey: ['agent-task', selectedTask], queryFn: () => getAgentTask(selectedTask!), enabled: Boolean(selectedTask), refetchInterval: selectedTask ? 10_000 : false })
  const activeTasks = useMemo(() => runtime?.recent_tasks.filter((task) => activeStatuses.has(task.status)) ?? [], [runtime?.recent_tasks])
  const recentTasks = useMemo(() => runtime?.recent_tasks.filter((task) => !activeStatuses.has(task.status)).slice(0, 22) ?? [], [runtime?.recent_tasks])

  return (
    <section className="page agents-page">
      <div className="page-heading agent-heading">
        <div>
          <p className="eyebrow">ROLE · TASK · DELEGATION · RECOVERY · CAPABILITY</p>
          <h1>AGENT OPERATIONS</h1>
          <p className="lede">三个 canonical Role 的 durable runtime。活跃任务才被标记为 LIVE，终态任务作为最近执行历史保留。</p>
        </div>
        <div className="agent-runtime-stamp">
          <span className="live-dot" /> RUNTIME
          <strong>{runtime ? runtime.roles.reduce((sum, role) => sum + role.active_tasks, 0) : '—'}</strong>
          <small>ACTIVE TASKS</small>
        </div>
      </div>

      <div className="role-constellation">
        {(runtime?.roles ?? []).map((role, index) => <RoleCard key={role.role_id} role={role} index={index} />)}
        {runtimeQuery.isLoading && [0,1,2].map((item) => <div key={item} className="role-card role-loading panel-glass" />)}
      </div>

      <div className="agent-workspace">
        <section className="task-field panel-glass">
          <div className="section-title-row">
            <div><small>DURABLE TASK FIELD</small><strong>LIVE + RECENT EXECUTION</strong></div>
            <span>{runtime?.recent_tasks.length ?? 0} loaded · {runtime?.recent_capabilities.length ?? 0} capability invocations</span>
          </div>

          <div className="task-lanes">
            <div className="task-lane live-lane">
              <div className="task-lane-title"><CircleDot size={13} /><strong>LIVE</strong><span>{activeTasks.length}</span></div>
              <div className="task-stack">
                {activeTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={setSelectedTaskOverride} />)}
                {runtime && activeTasks.length === 0 && <div className="task-empty">No active durable tasks.</div>}
              </div>
            </div>
            <div className="task-lane history-lane">
              <div className="task-lane-title"><TimerReset size={13} /><strong>RECENT HISTORY</strong><span>{recentTasks.length}</span></div>
              <div className="task-stack history-stack">
                {recentTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={setSelectedTaskOverride} />)}
              </div>
            </div>
          </div>
        </section>

        <aside className="task-dossier panel-glass">
          <div className="inspector-head">
            <div><small>SELECTED TASK</small><strong>{detailQuery.data?.task.task_kind ?? 'Select a task'}</strong></div>
            {detailQuery.data && <span className={`task-state state-${detailQuery.data.task.status}`}>{detailQuery.data.task.status}</span>}
          </div>
          {detailQuery.data ? <TaskDossier detail={detailQuery.data} /> : <div className="inspector-empty"><Waypoints size={36} /><strong>Task runtime dossier</strong><p>选择一个 Task，查看 canonical Role、parent linkage、事件序列和 Capability activity。</p></div>}
        </aside>
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
    <motion.article className={`role-card panel-glass tone-${presentation.tone} ${live ? 'role-live' : ''}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .08 }}>
      <RoleSigil role={role.role_id} live={live} />
      <div className="role-name"><small>{presentation.cn}</small><strong>{presentation.alias}</strong><span className="mono">{role.role_id}@{role.version}</span></div>
      <p>{presentation.copy}</p>
      <div className="role-runtime-line">
        <span className={live ? 'role-live-label' : ''}>{live ? `${role.active_tasks} LIVE` : 'IDLE'}</span>
        <span>{role.total_tasks} durable runs</span>
        {(failed > 0 || blocked > 0) && <span>{failed} failed · {blocked} blocked</span>}
      </div>
      <div className="role-coordinates"><span>{role.planner_profile}</span><span>{role.state_model}</span><span>{role.default_execution_profile}</span></div>
    </motion.article>
  )
}

function RoleSigil({ role, live }: { role: string; live: boolean }) {
  if (role === 'DecisionRole') return <div className={`role-sigil oracle-sigil ${live ? 'live' : ''}`}><div className="orbit orbit-a" /><div className="orbit orbit-b" /><Sparkles size={22} /></div>
  if (role === 'InvestigationRole') return <div className={`role-sigil argus-sigil ${live ? 'live' : ''}`}><div className="argus-eye"><Radio size={22} /></div><i /><i /><i /></div>
  return <div className={`role-sigil alchemist-sigil ${live ? 'live' : ''}`}><div /><div /><div /><div /><Orbit size={20} /></div>
}

function TaskCard({ task, selected, onSelect }: { task: AgentTaskSummary; selected: boolean; onSelect: (runId: string) => void }) {
  const child = Boolean(task.parent_run_id)
  return (
    <button className={`task-card ${selected ? 'selected' : ''} state-${task.status}`} onClick={() => onSelect(task.run_id)}>
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
