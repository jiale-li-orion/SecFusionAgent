import { RoleConstellation } from '../components/agents/RoleConstellation'
import { SpaceHeading } from '../components/instrument/SpaceHeading'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useReducedMotion } from 'motion/react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  BookOpenCheck,
  BrainCircuit,
  ChevronRight,
  CircleDot,
  TerminalSquare,
  TimerReset,
  Waypoints,
} from 'lucide-react'
import { getAgentExperiences, getAgentLearning, getAgentRuntime, getAgentSkill, getAgentSkills, getAgentTask } from '../lib/api'
import { ExperienceMemory, SkillFamilyDetail } from '../components/agents/LearningSurfaces'
import { RuntimeActivityView, TaskCard, TaskDossier, TaskTopology } from '../components/agents/RuntimeSurfaces'
import { groupSkillFamilies, skillFamilyKeyFromRef } from '../lib/agentLearning'
import { activeStatuses, rolePresentation } from '../lib/agentRuntimePresentation'
import { useI18n } from '../lib/i18n'
import { dominantRuntimeName, rankRuntimeCounts, runtimeToken } from '../lib/runtimePresentation'

function ModelRuntimeRibbon({ runtime }: { runtime: Awaited<ReturnType<typeof getAgentRuntime>> }) {
  const { text } = useI18n()
  const model = runtime.model_runtime
  const control = runtime.control_runtime
  const provider = dominantRuntimeName(model.provider_counts)
  const actualModel = dominantRuntimeName(model.model_counts)
  const stopReasons = rankRuntimeCounts(control.stop_reason_counts, 3)
  return (
    <section className="agent-model-runtime-ribbon">
      <div className="agent-model-runtime-title">
        <BrainCircuit size={14} />
        <div><small>{text('最近持久 MODEL 执行', 'RECENT PERSISTED MODEL EXECUTION')}</small><strong>{model.scope.replaceAll('_', ' ')}</strong></div>
        <span>{text(`最近 ${model.request_limit} 个请求上限`, `latest ${model.request_limit} request limit`)}</span>
      </div>
      <div className="agent-model-runtime-flow">
        <div><small>REQUESTS</small><strong>{model.request_count}</strong><span>{model.attempt_count} attempts</span></div>
        <i />
        <div><small>RETRY ATTEMPTS</small><strong>{model.retry_attempt_count}</strong><span>{model.retry_scheduled_count} scheduled</span></div>
        <i />
        <div><small>FAILED / UNKNOWN</small><strong>{model.failed_attempt_count} / {model.unknown_after_dispatch_count}</strong><span>{model.p95_latency_ms == null ? 'p95 not measured' : `p95 ${model.p95_latency_ms} ms`}</span></div>
        <i />
        <div><small>PROVIDER / MODEL</small><strong>{provider ?? '—'}</strong><span>{actualModel ?? '—'}</span></div>
      </div>
      <div className="agent-control-runtime-line">
        <span><b>{control.dependency_wake_count}</b> dependency wakes</span>
        <span><b>{control.waiting_event_count}</b> waiting boundaries</span>
        <span><b>{control.wake_latency_measurement === 'unavailable' ? 'NOT MEASURED' : control.wake_latency_measurement.toUpperCase()}</b> wake latency</span>
        {stopReasons.map(([reason, count]) => <span key={reason}><b>{count}</b> {runtimeToken(reason)}</span>)}
      </div>
    </section>
  )
}

function TaskTopologyBlueprint({ loading }: { loading: boolean }) {
  const { text } = useI18n()
  return <div className="task-ledger-empty">{loading ? text('读取执行记录…', 'Loading execution records…') : text('暂无可读执行记录。', 'No execution records available.')}</div>
}

function TaskLensBlueprint() {
  const { text } = useI18n()
  return <div className="memory-empty"><Waypoints size={28} /><strong>{text('打开一次真实执行', 'Inspect a real execution')}</strong><p>{text('选择任务，查看角色协作、调用过程、证据与终止原因。', 'Select a task to inspect collaboration, calls, evidence and its stop reason.')}</p></div>
}

function SkillBlueprintList() {
  const { text } = useI18n()
  return <p className="memory-empty">{text('暂无已保存的技能。', 'No saved skills yet.')}</p>
}

function SkillBlueprintDetail() {
  const { text } = useI18n()
  return <div className="memory-empty"><BrainCircuit size={25} /><strong>{text('可复用的调查方法', 'Reusable investigation methods')}</strong><p>{text('选择已保存的技能，查看它的适用条件、执行步骤和版本记录。', 'Select a saved skill to read its conditions, procedure and version history.')}</p></div>
}

function ExperienceBlueprint() {
  const { text } = useI18n()
  return <p className="memory-empty">{text('暂无已保存的经验。调查产生的经验经评估后会保留在这里。', 'No saved experiences yet. Evaluated investigation experience will appear here.')}</p>
}

export function AgentsPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const sectionParam = params.get('section')
  const roleParam = params.get('role')
  const origin = params.get('from')
  const originCaseRef = params.get('caseRef')
  const runtimeQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 12_000 })
  const runtime = runtimeQuery.data
  const learningQuery = useQuery({ queryKey: ['agent-learning'], queryFn: getAgentLearning, refetchInterval: 30_000 })
  const learning = learningQuery.data
  const skillsQuery = useQuery({ queryKey: ['agent-skills'], queryFn: getAgentSkills, refetchInterval: 30_000 })
  const experiencesQuery = useQuery({ queryKey: ['agent-experiences'], queryFn: getAgentExperiences, refetchInterval: 30_000 })
  const initialTask = runtime?.recent_tasks.find((task) => activeStatuses.has(task.status))?.run_id ?? runtime?.recent_tasks[0]?.run_id ?? null
  const requestedRun = params.get('run')
  const selectedTask = requestedRun ?? initialTask
  const detailQuery = useQuery({ queryKey: ['agent-task', selectedTask], queryFn: () => getAgentTask(selectedTask!), enabled: Boolean(selectedTask), refetchInterval: selectedTask ? 10_000 : false })
  const selectedTaskRole = detailQuery.data?.task.role_id
    ?? runtime?.recent_tasks.find((task) => task.run_id === selectedTask)?.role_id
    ?? null
  const skillFamilies = useMemo(() => groupSkillFamilies(skillsQuery.data ?? []), [skillsQuery.data])
  const [selectedSkillFamily, setSelectedSkillFamily] = useState<string | null>(null)
  const focusedRole = roleParam && rolePresentation[roleParam] ? roleParam : null
  const selectedSkill = skillFamilies.find((item) => item.key === (selectedSkillFamily ?? skillFamilies[0]?.key)) ?? null
  const selectedSkillRef = selectedSkill?.records[0]?.skill_ref ?? null
  const selectedSkillDetailQuery = useQuery({
    queryKey: ['agent-skill', selectedSkillRef],
    queryFn: () => getAgentSkill(selectedSkillRef!),
    enabled: Boolean(selectedSkillRef),
    staleTime: 30_000,
  })
  const visibleTasks = useMemo(
    () => runtime?.recent_tasks.filter((task) => !focusedRole || task.role_id === focusedRole) ?? [],
    [focusedRole, runtime?.recent_tasks],
  )
  const focusedActiveTasks = useMemo(() => visibleTasks.filter((task) => activeStatuses.has(task.status)), [visibleTasks])
  const [historyExpanded, setHistoryExpanded] = useState(false)
  const focusedRecentTasks = useMemo(() => visibleTasks.filter((task) => !activeStatuses.has(task.status)).slice(0, historyExpanded ? 22 : 6), [visibleTasks, historyExpanded])
  const activeCount = runtime?.roles.reduce((sum, role) => sum + role.active_tasks, 0) ?? 0
  const totalRuns = runtime?.roles.reduce((sum, role) => sum + role.total_tasks, 0) ?? 0

  useEffect(() => {
    if (sectionParam !== 'memory') return
    const frame = window.requestAnimationFrame(() => document.getElementById('agent-memory-field')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    return () => window.cancelAnimationFrame(frame)
  }, [sectionParam])

  function focusRole(roleId: string | null) {
    const nextParams = new URLSearchParams(params)
    if (roleId) nextParams.set('role', roleId)
    else nextParams.delete('role')
    if (roleId) {
      const firstTask = runtime?.recent_tasks.find((task) => task.role_id === roleId)
      if (firstTask) nextParams.set('run', firstTask.run_id)
    }
    setParams(nextParams, { replace: true })
  }

  function selectTask(runId: string) {
    const nextParams = new URLSearchParams(params)
    nextParams.set('run', runId)
    nextParams.delete('role')
    setParams(nextParams, { replace: true })
  }

  function inspectSkillRef(skillRef: string) {
    const key = skillFamilyKeyFromRef(skillRef)
    if (key) setSelectedSkillFamily(key)
    const next = new URLSearchParams(params)
    next.set('section', 'memory')
    setParams(next, { replace: true })
    requestAnimationFrame(() => document.getElementById('skill-codex')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }

  return (
    <section className={`agents-space studio-agents ${runtime ? 'runtime-loaded' : 'runtime-unresolved'}`}>
      <SpaceHeading index="04" eyebrow="AGENTS / EXECUTION" title={text('智能体协作', 'Agents')} description={text('观察研判、调查与富化如何接力，追踪每一次真实执行。', 'Follow reasoning, investigation and enrichment through their actual execution.')}>
        <div className="agent-runtime-readout">
          <span className={activeCount > 0 ? 'live' : ''} />
          <p>{runtime ? text(
            `${activeCount} 个任务正在执行 · 累计 ${totalRuns} 次运行。选中任务，查看执行过程和终止原因。`,
            `${activeCount} tasks are active now, while ${totalRuns} durable runs remain inspectable. The current projection contains ${runtime.recent_capabilities.length} persisted CapabilityInvocation records. Select any task to inspect why it stopped, which capabilities it invoked, what budget it consumed, and how it relates to a preceding investigation or delegated child task.`,
          ) : text('正在读取持久 Task、Role 与 Capability 运行事实。', 'Reading durable Task, Role, and Capability runtime facts.')}</p>
        </div>
      </SpaceHeading>
      {origin === 'case' && originCaseRef && (
        <div className="agent-origin case-origin">
          <span>CASE → TASK</span>
          <strong className="mono">{originCaseRef}</strong>
          <button onClick={() => navigate(`/investigations?case=${encodeURIComponent(originCaseRef)}`)}>{text('返回 Case', 'BACK TO CASE')}</button>
        </div>
      )}

      <div className="studio-section-switch"><button className={sectionParam !== 'memory' ? 'active' : ''} onClick={() => { const next = new URLSearchParams(params); next.delete('section'); setParams(next, { replace: true }); document.getElementById('agent-runtime-field')?.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth' }) }}>{text('任务与协作', 'Execution & collaboration')}</button><button className={sectionParam === 'memory' ? 'active' : ''} onClick={() => { const next = new URLSearchParams(params); next.set('section', 'memory'); setParams(next, { replace: true }) }}>{text('技能与经验', 'Skills & experience')}</button></div>
      {(runtimeQuery.isError || learningQuery.isError || skillsQuery.isError || experiencesQuery.isError) && (
        <div className="agent-seam-fault">
          <TerminalSquare size={14} />
          <div>
            <small>{text('产品读取降级', 'PRODUCT READ DEGRADED')}</small>
            <strong>{runtimeQuery.isError
              ? text('Agent Runtime 当前不可读；三 Role 权威结构保持可见。', 'Agent Runtime is unreadable; the three canonical Roles remain visible.')
              : text('Skill / Experience read 读取失败；Task Runtime 保持独立可读。', 'Skill / Experience read failed; Task Runtime remains independently readable.')}</strong>
          </div>
          <span>{runtimeQuery.isError ? 'runtime seam' : 'learning seam'}</span>
          <button className="recovery-action" onClick={() => {
            if (runtimeQuery.isError) void runtimeQuery.refetch()
            else void Promise.all([learningQuery.refetch(), skillsQuery.refetch(), experiencesQuery.refetch()])
          }}>{runtimeQuery.isError ? text('重试 Runtime read', 'RETRY RUNTIME READ') : text('重试 Learning read', 'RETRY LEARNING READ')}</button>
        </div>
      )}

      {sectionParam !== 'memory' && <>
      <RoleConstellation runtime={runtime?.roles} selected={selectedTaskRole} focused={focusedRole} onFocus={focusRole} />

      {runtime && <details className="agent-model-details"><summary>{text("模型与运行统计", "Model and runtime statistics")}</summary><ModelRuntimeRibbon runtime={runtime} /></details>}
      {detailQuery.data && <RuntimeActivityView detail={detailQuery.data} onSkillSelect={inspectSkillRef} onTaskSelect={selectTask} />}

      <div id="agent-runtime-field" className={`agent-runtime-grid ${focusedRole ? `runtime-focus-${focusedRole.toLowerCase()}` : ''}`}>
        <section className={`task-field ${focusedRole ? 'role-owned-field' : ''}`}>
          <div className="instrument-section-head">
            <div><small>{text('任务执行', 'DURABLE TASK FIELD')}</small><strong>{text('执行与协作', 'EXECUTION / DELEGATION TOPOLOGY')}</strong></div>
            <span>{focusedRole ? text(`${visibleTasks.length} 个 ${rolePresentation[focusedRole]?.alias ?? focusedRole} Task · 再点 Role 解除聚焦`, `${visibleTasks.length} ${rolePresentation[focusedRole]?.alias ?? focusedRole} tasks · click role again to release`) : text(`已加载 ${runtime?.recent_tasks.length ?? 0} 个 Task · 仅展示真实 parent/child 边`, `${runtime?.recent_tasks.length ?? 0} loaded · real parent/child edges only`)}</span>
          </div>

          {(runtime?.recent_tasks.length ?? 0) > 0
            ? <TaskTopology tasks={visibleTasks} selectedTask={selectedTask} onSelect={selectTask} focusedRole={focusedRole} />
            : <TaskTopologyBlueprint loading={runtimeQuery.isLoading} />}

          <div className="task-ledger">
            <div className="task-ledger-column live">
              <div className="task-ledger-title"><CircleDot size={12} /><strong>{text('实时执行', 'LIVE EXECUTION')}</strong><span>{focusedActiveTasks.length}</span></div>
              <div>
                {focusedActiveTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={selectTask} />)}
                {runtime && focusedActiveTasks.length === 0 && <div className="task-ledger-empty">{text('当前所选角色没有执行中的任务。', 'No active durable tasks in current role focus.')}</div>}
              </div>
            </div>
            <div className="task-ledger-column history">
              <div className="task-ledger-title"><TimerReset size={12} /><strong>{text('近期执行', 'RECENT TERMINAL HISTORY')}</strong><span>{focusedRecentTasks.length}</span></div>
              <div>
                {focusedRecentTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={selectTask} />)}
                {visibleTasks.filter(task => !activeStatuses.has(task.status)).length > 6 && <button className="agent-history-toggle" onClick={() => setHistoryExpanded(v => !v)}>{historyExpanded ? text("收起历史", "Less history") : text("查看更多运行", "More runs")}</button>}
              </div>
            </div>
          </div>
        </section>

        <aside className="task-runtime-lens">
          <div className="task-lens-head">
            <div><small>{text('选中 Task', 'SELECTED TASK')}</small><strong>{detailQuery.data?.task.task_kind ?? text('选择一个 Task', 'Select a task')}</strong></div>
            {detailQuery.data && <span className={`task-state state-${detailQuery.data.task.status}`}>{detailQuery.data.task.status}</span>}
          </div>
          {detailQuery.data ? <TaskDossier detail={detailQuery.data} onSkillSelect={inspectSkillRef} /> : <TaskLensBlueprint />}
        </aside>
      </div>

      </>}
      {sectionParam === 'memory' && <div id="agent-memory-field" className="agent-memory-complex">
        <section id="skill-codex" className="skill-codex">
          <div className="instrument-section-head"><div><small>{text('SKILL 典藏', 'SKILL CODEX')}</small><strong>{text('持久程序记忆', 'DURABLE PROCEDURAL MEMORY')}</strong></div><span>{text(String(skillsQuery.data?.length ?? 0) + ' 条记录 · ' + String(skillFamilies.length) + ' 个家族', String(skillsQuery.data?.length ?? 0) + ' records · ' + String(skillFamilies.length) + ' families')}</span></div>
          <div className="skill-codex-body">
            <div className="skill-family-list">
              {skillFamilies.length
                ? skillFamilies.map((family) => <button key={family.key} className={family.key === selectedSkill?.key ? 'selected' : ''} onClick={() => setSelectedSkillFamily(family.key)}><span className="skill-glyph"><BookOpenCheck size={15} /></span><span><small>{family.records.map((item) => item.status).join(' · ')}</small><strong>{family.label}</strong><em>{text(`${family.records.length} 条 durable 记录`, `${family.records.length} durable records`)}</em></span><ChevronRight size={14} /></button>)
                : <SkillBlueprintList />}
            </div>
            <div className="skill-detail">
              {selectedSkill ? <SkillFamilyDetail family={selectedSkill} primaryDetail={selectedSkillDetailQuery.data ?? null} /> : <SkillBlueprintDetail />}
            </div>
          </div>
        </section>

        <section className="experience-memory">
          <div className="instrument-section-head"><div><small>{text('经验记忆', 'EXPERIENCE MEMORY')}</small><strong>TRAJECTORY → EXPERIENCE → SKILL</strong></div><span>{text(`${experiencesQuery.data?.length ?? 0} 条 durable Experience`, `${experiencesQuery.data?.length ?? 0} durable experiences`)}</span></div>
          {learning && experiencesQuery.data && skillsQuery.data
            ? <ExperienceMemory stats={learning} experiences={experiencesQuery.data} skills={skillsQuery.data} />
            : <ExperienceBlueprint />}
        </section>
      </div>}
    </section>
  )
}
