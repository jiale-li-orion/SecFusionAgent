import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useNavigate } from 'react-router-dom'
import { Activity, ArrowDownRight, BrainCircuit, CircleDot, GitFork, TerminalSquare, Waypoints } from 'lucide-react'

import { getAgentTask, type AgentTaskSummary } from '../../lib/api'
import { activeStatuses, rolePresentation } from '../../lib/agentRuntimePresentation'
import { useI18n } from '../../lib/i18n'

function DelegationActivityNode({ parent, predecessor, children, onTaskSelect }: { parent: AgentTaskSummary | null; predecessor: AgentTaskSummary | null; children: AgentTaskSummary[]; onTaskSelect: (runId: string) => void }) {
  const { text } = useI18n()
  const relationCount = children.length + (parent ? 1 : 0) + (predecessor ? 1 : 0)
  return (
    <div className="runtime-activity-node tone-delegation runtime-delegation-node">
      <span>↳</span>
      <div>
        <small>EXECUTION LINKS</small>
        <strong>{text(`${relationCount} 条持久执行关联`, `${relationCount} durable execution link${relationCount === 1 ? '' : 's'}`)}</strong>
        <div className="runtime-delegation-links">
          {predecessor && <button type="button" onClick={() => onTaskSelect(predecessor.run_id)}><b>← PREVIOUS</b><span>{rolePresentation[predecessor.role_id]?.alias ?? predecessor.role_id} · {shortTaskKind(predecessor.task_kind)}</span><em>{predecessor.status}</em></button>}
          {parent && <button type="button" onClick={() => onTaskSelect(parent.run_id)}><b>↑ PARENT</b><span>{rolePresentation[parent.role_id]?.alias ?? parent.role_id} · {shortTaskKind(parent.task_kind)}</span><em>{parent.status}</em></button>}
          {children.map((child) => <button type="button" key={child.run_id} onClick={() => onTaskSelect(child.run_id)}><b>↓ CHILD</b><span>{rolePresentation[child.role_id]?.alias ?? child.role_id} · {shortTaskKind(child.task_kind)}</span><em>{child.status}</em></button>)}
        </div>
      </div>
    </div>
  )
}

function buildRecoveryTrace(events: Array<{ seq: number; event_type: string; producer: string; emitted_at: string }>) {
  const boundaryTypes = new Set(['NeedInput', 'NeedContext', 'TaskBlocked'])
  const boundaryIndex = events.map((event) => boundaryTypes.has(event.event_type)).lastIndexOf(true)
  if (boundaryIndex < 0) return null
  const boundary = events[boundaryIndex]
  const resumed = events.slice(boundaryIndex + 1).find((event) => !boundaryTypes.has(event.event_type)) ?? null
  return { boundary, resumed }
}

function formatBudget(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
}

export function RuntimeActivityView({ detail, onSkillSelect, onTaskSelect }: { detail: Awaited<ReturnType<typeof getAgentTask>>; onSkillSelect: (skillRef: string) => void; onTaskSelect: (runId: string) => void }) {
  const { text } = useI18n()
  const task = detail.task
  const assembly = detail.prompt_assemblies[0] ?? null
  const latestCapability = detail.capabilities.at(-1) ?? null
  const latestEvent = detail.events.at(-1) ?? null
  const recovery = buildRecoveryTrace(detail.events)
  const skills = assembly?.materialized_skill_refs ?? []
  const stateLabel = recovery
    ? recovery.resumed
      ? text('恢复链已落盘', 'RECOVERY TRACE PERSISTED')
      : text('停在恢复边界', 'STOPPED AT RECOVERY BOUNDARY')
    : task.stop_reason ?? latestEvent?.event_type ?? task.status

  return (
    <section className={`runtime-activity-view role-${task.role_id.toLowerCase()} status-${task.status}`}>
      <div className="runtime-activity-caption">
        <small>RUNTIME ACTIVITY VIEW</small>
        <strong>{rolePresentation[task.role_id]?.alias ?? task.role_id} / {task.task_kind}</strong>
        <span className="mono">{task.run_id}</span>
      </div>
      <div className="runtime-activity-spine">
        <RuntimeActivityNode
          index="01"
          label="ROLE ADMISSION"
          primary={`${task.role_id}@${task.role_version}`}
          secondary={task.case_id ? text('durable Case 任务', 'durable Case task') : text('独立 Task', 'standalone Task')}
          tone="role"
        />
        <RuntimeActivityNode
          index="02"
          label="TASK"
          primary={humanize(task.task_kind)}
          secondary={task.status}
          tone={activeStatuses.has(task.status) ? 'live' : task.status === 'failed' ? 'failure' : 'stable'}
        />
        {(detail.parent || detail.predecessor || detail.children.length > 0) && (
          <DelegationActivityNode
            parent={detail.parent}
            predecessor={detail.predecessor ?? null}
            children={detail.children}
            onTaskSelect={onTaskSelect}
          />
        )}
        <div className="runtime-activity-node tone-context">
          <span>03</span>
          <div><small>ASSEMBLY / SKILL</small><strong>{assembly ? text(`${skills.length} 个 materialized Skill`, `${skills.length} materialized skills`) : text('无 PromptAssembly', 'NO PROMPT ASSEMBLY')}</strong></div>
          <div className="runtime-activity-ref">
            {skills.slice(0, 2).map((ref) => <button key={ref} onClick={() => onSkillSelect(ref)}>{ref}</button>)}
            {skills.length > 2 && <em>+{skills.length - 2}</em>}
          </div>
        </div>
        <RuntimeActivityNode
          index="04"
          label="CAPABILITY"
          primary={latestCapability?.capability_id ?? text('无调用', 'NO INVOCATION')}
          secondary={latestCapability ? `${latestCapability.status} · ${latestCapability.tool_impl_id}` : text('当前 Task 没有持久化 CapabilityInvocation', 'no persisted CapabilityInvocation')}
          tone={latestCapability?.status === 'failed' ? 'failure' : latestCapability ? 'capability' : 'muted'}
        />
        <RuntimeActivityNode
          index="05"
          label="STATE / STOP"
          primary={stateLabel}
          secondary={latestEvent ? `seq ${latestEvent.seq} · ${latestEvent.event_type}` : text('无持久化事件', 'no persisted event')}
          tone={recovery && !recovery.resumed ? 'waiting' : task.status === 'failed' ? 'failure' : 'state'}
        />
      </div>
    </section>
  )
}

function RuntimeActivityNode({ index, label, primary, secondary, tone }: { index: string; label: string; primary: string; secondary: string; tone: string }) {
  return (
    <div className={`runtime-activity-node tone-${tone}`}>
      <span>{index}</span>
      <div><small>{label}</small><strong>{primary}</strong><em>{secondary}</em></div>
    </div>
  )
}

export function TaskTopology({ tasks, selectedTask, onSelect, focusedRole }: { tasks: AgentTaskSummary[]; selectedTask: string | null; onSelect: (runId: string) => void; focusedRole: string | null }) {
  const { text } = useI18n()
  const topology = useMemo(() => buildTaskTopology(tasks, selectedTask), [tasks, selectedTask])
  const selectedModel = tasks.find((task) => task.run_id === selectedTask) ?? null
  const selectedCase = selectedModel?.case_id ?? null
  return <div className="task-topology">
    <div className="task-topology-head">
      <div className={`task-role-axis ${focusedRole ? 'single-role-axis' : ''}`}>
        {focusedRole
          ? <span>{rolePresentation[focusedRole]?.alias ?? focusedRole} / {focusedRole}</span>
          : <><span>ORACLE</span><span>ARGUS</span><span>ALCHEMIST</span></>}
      </div>
      <div><small>{text('委派与执行步骤', 'DELEGATION + EXECUTION STEPS')}</small><strong>{text(`${topology.nodes.length} 个可见节点 · ${topology.edges.length} 条执行关联`, `${topology.nodes.length} visible nodes · ${topology.edges.length} execution links`)}</strong></div>
    </div>
    <div className={`task-topology-canvas ${focusedRole ? 'single-role-topology' : ''}`}>
      {focusedRole
        ? <div className={`task-role-column role-focus-column focus-${focusedRole.toLowerCase()}`} />
        : <><div className="task-role-column role-decision" /><div className="task-role-column role-investigation" /><div className="task-role-column role-enrichment" /></>}
      <svg className="task-topology-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {topology.edges.map((edge) => {
          const active = edge.parent.run_id === selectedTask || edge.child.run_id === selectedTask || Boolean(selectedCase && edge.parent.task.case_id === selectedCase && edge.child.task.case_id === selectedCase)
          const delegating = activeStatuses.has(edge.child.task.status)
          return <path key={`${edge.parent.run_id}:${edge.child.run_id}`} className={`${active ? 'active' : selectedTask ? 'dimmed' : ''} ${delegating ? 'delegating' : 'settled'}`} d={`M ${edge.parent.x} ${edge.parent.y} C ${edge.parent.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${edge.child.y}`} />
        })}
      </svg>
      {topology.nodes.map((node) => {
        const task = node.task
        const related = !selectedTask || task.run_id === selectedTask || Boolean(selectedCase && task.case_id === selectedCase)
        return <motion.button
          key={task.run_id}
          className={`task-crystal state-${task.status} ${task.run_id === selectedTask ? 'selected' : ''} ${selectedCase && task.case_id === selectedCase ? 'case-related' : ''} ${related ? '' : 'dimmed'}`}
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          onClick={() => onSelect(task.run_id)}
          initial={{ opacity: 0, scale: .75 }}
          animate={{ opacity: related ? 1 : .68, scale: task.run_id === selectedTask ? 1.1 : 1 }}
          transition={{ type: 'spring', stiffness: 230, damping: 25 }}
          title={`${task.role_id} · ${task.task_kind} · ${task.status}`}
        >
          <span className="task-crystal-core" />
          <span className="task-crystal-copy"><small>{rolePresentation[task.role_id]?.alias ?? task.role_id}</small><strong>{shortTaskKind(task.task_kind)}</strong><em>{task.status}</em></span>
          {(task.parent_run_id || task.predecessor_run_id) && <GitFork size={10} className="task-child-mark" />}
        </motion.button>
      })}
      {topology.nodes.length === 0 && <div className="task-topology-empty">{text('当前读取窗口没有 durable TaskRun。', 'No durable TaskRun in current read window.')}</div>}
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
    const preceding = selected.parent_run_id ?? selected.predecessor_run_id
    if (preceding && allById.has(preceding)) chosen.set(preceding, allById.get(preceding)!)
    for (const task of tasks) if (task.parent_run_id === selected.run_id || (selected.case_id && task.case_id === selected.case_id)) chosen.set(task.run_id, task)
  }
  for (const task of tasks) if (activeStatuses.has(task.status)) chosen.set(task.run_id, task)
  for (const task of tasks) {
    if (chosen.size >= 14) break
    const preceding = task.parent_run_id ?? task.predecessor_run_id
    if (preceding && allById.has(preceding)) {
      chosen.set(preceding, allById.get(preceding)!)
      chosen.set(task.run_id, task)
    }
  }
  for (const task of tasks) {
    if (chosen.size >= 14) break
    chosen.set(task.run_id, task)
  }

  const byRole = new Map<string, AgentTaskSummary[]>()
  for (const task of chosen.values()) byRole.set(task.role_id, [...(byRole.get(task.role_id) ?? []), task])
  const singleRole = byRole.size === 1
  const roleX: Record<string, number> = singleRole
    ? { DecisionRole: 50, InvestigationRole: 50, EnrichmentRole: 50 }
    : { DecisionRole: 17, InvestigationRole: 50, EnrichmentRole: 83 }
  const nodes: TaskTopologyNode[] = []
  for (const [role, roleTasks] of byRole) {
    const sorted = [...roleTasks].sort((a, b) => Number(activeStatuses.has(b.status)) - Number(activeStatuses.has(a.status)) || new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    sorted.slice(0, 6).forEach((task, index) => {
      if (!singleRole) {
        nodes.push({ task, run_id: task.run_id, x: roleX[role] ?? 50, y: 17 + index * 14 })
        return
      }
      const singleRoleLayouts: Record<string, Array<{ x: number; y: number }>> = {
        DecisionRole: [
          { x: 30, y: 18 }, { x: 70, y: 18 }, { x: 38, y: 39 },
          { x: 62, y: 39 }, { x: 44, y: 62 }, { x: 56, y: 76 },
        ],
        InvestigationRole: [
          { x: 37, y: 16 }, { x: 63, y: 28 }, { x: 34, y: 42 },
          { x: 66, y: 56 }, { x: 40, y: 70 }, { x: 60, y: 82 },
        ],
        EnrichmentRole: [
          { x: 39, y: 18 }, { x: 61, y: 18 }, { x: 39, y: 43 },
          { x: 61, y: 43 }, { x: 39, y: 68 }, { x: 61, y: 68 },
        ],
      }
      const point = singleRoleLayouts[role]?.[index] ?? { x: 50, y: 17 + index * 14 }
      nodes.push({ task, run_id: task.run_id, x: point.x, y: point.y })
    })
  }
  const nodeById = new Map(nodes.map((node) => [node.run_id, node]))
  const edges: TaskTopologyEdge[] = []
  for (const node of nodes) {
    const preceding = node.task.parent_run_id ?? node.task.predecessor_run_id
    if (!preceding) continue
    const parent = nodeById.get(preceding)
    if (parent) edges.push({ parent, child: node })
  }
  return { nodes, edges }
}

function shortTaskKind(value: string) {
  const clean = value.replaceAll('_', ' ')
  return clean.length > 18 ? `${clean.slice(0, 16)}…` : clean
}

export function TaskCard({ task, selected, onSelect }: { task: AgentTaskSummary; selected: boolean; onSelect: (runId: string) => void }) {
  const { text } = useI18n()
  const relation = task.parent_run_id ? 'CHILD' : task.predecessor_run_id ? 'STEP' : 'ROOT'
  return (
    <button className={`task-ledger-row ${selected ? 'selected' : ''} state-${task.status}`} onClick={() => onSelect(task.run_id)}>
      <span className="task-role-mark">{rolePresentation[task.role_id]?.alias.slice(0, 2) ?? 'RT'}</span>
      <span className="task-main"><small>{task.role_id} · {relation}</small><strong>{humanize(task.task_kind)}</strong><em>{task.last_event_type ?? text('无事件', 'no event')} · {text(`${task.event_count} 个 events`, `${task.event_count} events`)}</em></span>
      <span className="task-tail"><b>{task.status}</b>{relation === 'ROOT' ? <ArrowDownRight size={12} /> : <GitFork size={12} />}</span>
    </button>
  )
}

export function TaskDossier({ detail, onSkillSelect }: { detail: Awaited<ReturnType<typeof getAgentTask>>; onSkillSelect: (skillRef: string) => void }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [selectedCapability, setSelectedCapability] = useState<string | null>(null)
  const task = detail.task
  const latestAssembly = detail.prompt_assemblies[0] ?? null
  const recoveryTrace = buildRecoveryTrace(detail.events)
  const blockedPreviousEvent = task.status === 'blocked' && detail.events.length > 1 ? detail.events.at(-2) ?? null : null
  return (
    <div className="task-dossier-body">
      <div className="task-identity">
        <small>RUN ID</small><strong className="mono">{task.run_id}</strong>
        <div><span>{rolePresentation[task.role_id]?.alias ?? task.role_id}</span><span>{task.role_id}@{task.role_version}</span></div>
      </div>
      {(task.case_id || task.parent_run_id || task.predecessor_run_id) && (
        <div className="task-coordinate-links">
          {task.case_id && <button onClick={() => {
            const query = new URLSearchParams({ case: task.case_id!, from: 'task', run: task.run_id })
            navigate(`/investigations?${query.toString()}`)
          }}><Waypoints size={11} /> {text('打开所属 Case', 'OPEN CASE')}<span className="mono">{task.case_id}</span></button>}
          {task.predecessor_run_id && <button onClick={() => navigate(`/agents?run=${encodeURIComponent(task.predecessor_run_id!)}`)}><Waypoints size={11} /> {text('上一步调查任务', 'PREVIOUS INVESTIGATION TASK')}<span className="mono">{task.predecessor_run_id}</span></button>}
          {task.parent_run_id && <button onClick={() => navigate(`/agents?run=${encodeURIComponent(task.parent_run_id!)}`)}><GitFork size={11} /> {text('打开 Parent Task', 'OPEN PARENT TASK')}<span className="mono">{task.parent_run_id}</span></button>}
        </div>
      )}
      <div className="task-facts">
        <TaskFact label="CASE" value={task.case_id ?? text('独立 Task', 'standalone')} mono />
        <TaskFact label="PARENT" value={task.parent_run_id ?? text('根 Task', 'root task')} mono />
        <TaskFact label="PREVIOUS STEP" value={task.predecessor_run_id ?? text('无前序执行', 'none')} mono />
        <TaskFact label="STOP REASON" value={task.stop_reason ?? (activeStatuses.has(task.status) ? text('执行中', 'in progress') : text('未指定', 'unspecified'))} />
        <TaskFact label="UPDATED" value={new Date(task.updated_at).toLocaleString()} />
      </div>
      {task.status === 'blocked' && (
        <section className="task-blocked-boundary">
          <div className="task-blocked-mark"><TerminalSquare size={19} /><i /></div>
          <div className="task-blocked-copy">
            <small>{text('运行阻塞边界', 'RUNTIME BLOCK BOUNDARY')}</small>
            <strong>{blockedBoundaryTitle(task.stop_reason, text)}</strong>
            <p>{blockedBoundaryNarrative(task.stop_reason, text)}</p>
            <span className="mono">{task.stop_reason ?? 'blocked'}</span>
          </div>
          <div className="task-blocked-evidence">
            <div><small>{text('前一持久事件', 'PREVIOUS PERSISTED EVENT')}</small><strong>{blockedPreviousEvent?.event_type ?? '—'}</strong><span>{blockedPreviousEvent ? 'seq ' + blockedPreviousEvent.seq + ' · ' + blockedPreviousEvent.producer : text('无前序事件', 'no prior event')}</span></div>
            <div><small>CAPABILITY INVOCATION</small><strong>{detail.capabilities.length}</strong><span>{detail.capabilities.length ? text('存在持久调用记录', 'persisted invocation records exist') : text('阻塞前未出现调用记录', 'no invocation recorded before block')}</span></div>
            <div><small>BUDGET ACCOUNT</small><strong>{detail.budget ? text('已建立', 'PRESENT') : text('未建立', 'ABSENT')}</strong><span>{detail.budget?.account_id ?? text('当前 Task 没有 BudgetAccount', 'no BudgetAccount for this Task')}</span></div>
            <div><small>{text('终止事件', 'TERMINAL EVENT')}</small><strong>{task.last_event_type ?? 'TaskBlocked'}</strong><span>{task.last_event_at ? new Date(task.last_event_at).toLocaleString() : text('无时间戳', 'no timestamp')}</span></div>
          </div>
        </section>
      )}
      {recoveryTrace && (
        <section className={`task-recovery ${recoveryTrace.resumed ? 'resumed' : 'open-boundary'}`}>
          <div className="task-recovery-head">
            <div><small>{text('恢复边界', 'RECOVERY BOUNDARY')}</small><strong>{humanize(recoveryTrace.boundary.event_type)}</strong></div>
            <span>{recoveryTrace.resumed ? text('后续事件已出现', 'SUBSEQUENT EVENT OBSERVED') : text('等待后续事件', 'AWAITING SUBSEQUENT EVENT')}</span>
          </div>
          <div className="task-recovery-track">
            <div className="task-recovery-node boundary">
              <i />
              <span><small>SEQ {recoveryTrace.boundary.seq}</small><strong>{recoveryTrace.boundary.event_type}</strong><em>{new Date(recoveryTrace.boundary.emitted_at).toLocaleTimeString()}</em></span>
            </div>
            <div className="task-recovery-line"><b className={recoveryTrace.resumed ? 'resolved' : ''} /></div>
            {recoveryTrace.resumed ? (
              <div className="task-recovery-node resumed">
                <i />
                <span><small>SEQ {recoveryTrace.resumed.seq}</small><strong>{recoveryTrace.resumed.event_type}</strong><em>{new Date(recoveryTrace.resumed.emitted_at).toLocaleTimeString()}</em></span>
              </div>
            ) : (
              <div className="task-recovery-node unresolved">
                <i />
                <span><small>{text('无后续 persisted event', 'NO SUBSEQUENT PERSISTED EVENT')}</small><strong>{task.status}</strong><em>{text('当前读取窗口', 'current read window')}</em></span>
              </div>
            )}
          </div>
          <p>{recoveryTrace.resumed
            ? text('恢复链来自同一 TaskRun 的事件顺序；界面不推断未记录的执行步骤。', 'Recovery trace follows persisted event order in the same TaskRun; unrecorded execution steps are not inferred.')
            : text('Task 在此边界停住。页面保留事实缺口，不把 blocked / waiting 状态伪装成已恢复。', 'The Task stops at this boundary. The UI preserves the gap instead of presenting blocked / waiting as recovered.')}</p>
        </section>
      )}
      <div className="task-events-title"><BrainCircuit size={14} /><strong>{text('PROMPT 装配', 'PROMPT ASSEMBLY')}</strong><span>{detail.prompt_assemblies.length}</span></div>
      {latestAssembly ? (
        <div className="task-assembly">
          <div className="task-assembly-coordinate">
            <span><small>EXECUTION</small><strong className="mono">{latestAssembly.execution_id}</strong></span>
            <span><small>ROLE REVISION</small><strong>{latestAssembly.role_revision}</strong></span>
            <span><small>PROFILE REVISION</small><strong>{latestAssembly.execution_profile_revision}</strong></span>
          </div>
          <div className="task-materialized">
            <div><small>MATERIALIZED SKILLS</small><strong>{latestAssembly.materialized_skill_refs.length}</strong></div>
            <div className="task-ref-list">
              {latestAssembly.materialized_skill_refs.length ? latestAssembly.materialized_skill_refs.map((ref) => <button key={ref} onClick={() => onSkillSelect(ref)}>{ref}</button>) : <span>{text('没有 materialized Skill', 'no materialized skill')}</span>}
            </div>
          </div>
          <div className="task-materialized">
            <div><small>CAPABILITY VIEW</small><strong>{latestAssembly.materialized_capability_view_refs.length}</strong></div>
            <div className="task-ref-list">
              {latestAssembly.materialized_capability_view_refs.length ? latestAssembly.materialized_capability_view_refs.map((ref) => <span key={ref}>{ref}</span>) : <span>{text('没有 materialized Capability view', 'no materialized capability view')}</span>}
            </div>
          </div>
          <div className="task-assembly-footer"><span>{text(`${latestAssembly.percept_refs.length} 条 percept refs`, `${latestAssembly.percept_refs.length} percept refs`)}</span><span className="mono">{latestAssembly.materialized_ref_set_digest.slice(0, 18)}…</span></div>
        </div>
      ) : <div className="capability-empty">{text('当前 Task 没有持久化 PromptAssemblyRecord。', 'No persisted PromptAssemblyRecord for this Task.')}</div>}
      <div className="task-events-title"><CircleDot size={14} /><strong>{text('预算控制', 'BUDGET GOVERNOR')}</strong><span>{detail.budget ? Object.keys(detail.budget.limits).length : 0}</span></div>
      {detail.budget ? (
        <div className="task-budget">
          {Object.entries(detail.budget.limits).map(([resource, limit]) => {
            const committed = detail.budget!.committed[resource] ?? 0
            const reserved = detail.budget!.reserved[resource] ?? 0
            const remaining = detail.budget!.remaining[resource] ?? Math.max(0, limit - committed - reserved)
            const consumed = Math.max(0, limit - remaining)
            const ratio = limit > 0 ? Math.min(consumed / limit, 1) : 0
            return (
              <div key={resource}>
                <span><small>{resource}</small><strong>{formatBudget(consumed)} / {formatBudget(limit)}</strong></span>
                <i><b style={{ width: `${ratio * 100}%` }} /></i>
                <em>{text(`${formatBudget(remaining)} 剩余${reserved ? ` · ${formatBudget(reserved)} 已预留` : ''}`, `${formatBudget(remaining)} remaining${reserved ? ` · ${formatBudget(reserved)} reserved` : ''}`)}</em>
              </div>
            )
          })}
          <div className="task-budget-coordinate mono">{detail.budget.account_id}</div>
        </div>
      ) : <div className="capability-empty">{text('当前 Task 没有持久化 BudgetAccount。', 'No persisted BudgetAccount for this Task.')}</div>}
      <div className="task-events-title"><Activity size={14} /><strong>{text('事件时间线', 'EVENT TIMELINE')}</strong><span>{detail.events.length}</span></div>
      <div className="event-timeline">
        {detail.events.map((event, index) => (
          <motion.div key={event.event_id} className="event-row" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(index * .03, .25) }}>
            <span className="event-seq">{String(event.seq).padStart(2, '0')}</span>
            <span className="event-node" />
            <div><strong>{event.event_type}</strong><small>{event.producer} · {new Date(event.emitted_at).toLocaleTimeString()}</small></div>
          </motion.div>
        ))}
      </div>
      <div className="task-events-title"><TerminalSquare size={14} /><strong>{text('CAPABILITY 活动', 'CAPABILITY ACTIVITY')}</strong><span>{detail.capabilities.length}</span></div>
      {detail.capabilities.length ? <div className="capability-stack">{detail.capabilities.map((item) => {
        const open = selectedCapability === item.invocation_id
        return (
          <article key={item.invocation_id} className={`capability-row status-${item.status} ${open ? 'open' : ''}`}>
            <button onClick={() => setSelectedCapability(open ? null : item.invocation_id)}>
              <span className="capability-index">{String(detail.capabilities.indexOf(item) + 1).padStart(2, '0')}</span>
              <div><small>{item.capability_id}</small><strong>{item.tool_impl_id}</strong><em>{item.observation_class ?? text('无 observation class', 'no observation class')}</em></div>
              <span className="capability-state">{item.status}</span>
            </button>
            <AnimatePresence initial={false}>
              {open && <motion.div className="capability-detail" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                <TaskFact label="INVOCATION" value={item.invocation_id} mono />
                <TaskFact label="POLICY" value={item.policy_decision_ref ?? text('未关联', 'not linked')} mono />
                <TaskFact label="OUTPUT" value={item.canonical_output_ref ?? text('无', 'none')} mono />
                <TaskFact label="RAW ARTIFACT" value={item.raw_artifact_ref ?? text('无', 'none')} mono />
                <TaskFact label="EFFECT RECEIPT" value={item.effect_receipt_ref ?? text('无', 'none')} mono />
                {(item.failure_code || item.failure_detail) && <div className="capability-failure"><small>{item.failure_code ?? text('失败', 'failure')}</small><strong>{item.failure_detail ?? text('无失败详情', 'no failure detail')}</strong></div>}
              </motion.div>}
            </AnimatePresence>
          </article>
        )
      })}</div> : <div className="capability-empty">{text('当前 Task 没有持久化 CapabilityInvocation。', 'No persisted CapabilityInvocation for this Task.')}</div>}
    </div>
  )
}

function TaskFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

function blockedBoundaryTitle(stopReason: string | null, text: (zh: string, en: string) => string) {
  if (stopReason === 'no_eligible_enrichment_operator') return text('未找到符合条件的 Enrichment Operator', 'NO ELIGIBLE ENRICHMENT OPERATOR')
  return text('Task 在运行边界停止', 'TASK STOPPED AT A RUNTIME BOUNDARY')
}

function blockedBoundaryNarrative(stopReason: string | null, text: (zh: string, en: string) => string) {
  if (stopReason === 'no_eligible_enrichment_operator') {
    return text(
      'ALCHEMIST 已进入 EnrichmentState，但 operator eligibility 没有产生可执行候选；运行在 CapabilityInvocation 之前终止。',
      'ALCHEMIST reached EnrichmentState, but operator eligibility produced no executable candidate; the run terminated before CapabilityInvocation.',
    )
  }
  return text(
    '页面按持久化 stop reason 与事件顺序呈现阻塞位置；未记录的恢复步骤不会被补写。',
    'The surface presents the block from persisted stop reason and event order; unrecorded recovery steps are not inferred.',
  )
}

function humanize(value: string) { return value.replaceAll('_', ' ').toUpperCase() }
