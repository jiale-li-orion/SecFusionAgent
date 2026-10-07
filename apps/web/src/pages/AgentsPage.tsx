import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'motion/react'
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
import { getAgentExperiences, getAgentLearning, getAgentRuntime, getAgentSkill, getAgentSkills, getAgentTask, type AgentRoleRuntime } from '../lib/api'
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

function RoleBlueprint({
  blueprint,
  index,
  loading,
  focusedRole,
  onFocus,
}: {
  blueprint: (typeof roleBlueprints)[number]
  index: number
  loading: boolean
  focusedRole: string | null
  onFocus: (role: string | null) => void
}) {
  const { text } = useI18n()
  const presentation = rolePresentation[blueprint.role_id]
  return (
    <motion.button
      className={`role-entity role-${blueprint.role_id.toLowerCase()} tone-${blueprint.tone} role-blueprint ${focusedRole === blueprint.role_id ? 'role-focused' : ''} ${focusedRole && focusedRole !== blueprint.role_id ? 'role-dimmed' : ''}`}
      onClick={() => onFocus(focusedRole === blueprint.role_id ? null : blueprint.role_id)}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: focusedRole && focusedRole !== blueprint.role_id ? .28 : 1, y: 0, scale: focusedRole === blueprint.role_id ? 1.025 : 1 }}
      transition={{ delay: index * .06 }}
    >
      <RoleSigil role={blueprint.role_id} live={false} />
      <div className="role-entity-copy">
        <small>{text(blueprint.cn, blueprint.role_id)} / {blueprint.role_id}@1</small>
        <strong>{blueprint.alias}</strong>
        <p>{presentation ? text(presentation.copy, presentation.copyEn) : blueprint.state}</p>
        <div className="role-coordinates"><span>{blueprint.profile}</span><span>{blueprint.state}</span><span>{text('规范 Role', 'CANONICAL ROLE')}</span></div>
      </div>
      <div className="role-entity-runtime blueprint">
        <b>—</b>
        <small>{loading ? text('解析中', 'RESOLVING') : text('RUNTIME 离线', 'RUNTIME OFFLINE')}</small>
        <span>{text('结构保持可见', 'structure remains visible')}</span>
      </div>
    </motion.button>
  )
}

function TaskTopologyBlueprint({ loading }: { loading: boolean }) {
  const { text } = useI18n()
  const nodes = [
    { x: 17, y: 30, role: 'ORACLE', label: 'Decision Task' },
    { x: 50, y: 24, role: 'ARGUS', label: 'Investigation Task' },
    { x: 50, y: 62, role: 'ARGUS', label: 'Waiting / Recovery' },
    { x: 83, y: 42, role: 'ALCHEMIST', label: 'Enrichment Child' },
  ]
  return (
    <div className="task-topology task-topology-blueprint">
      <div className="task-topology-head">
        <div className="task-role-axis"><span>ORACLE</span><span>ARGUS</span><span>ALCHEMIST</span></div>
        <div><small>{text('规范执行拓扑', 'CANONICAL EXECUTION TOPOLOGY')}</small><strong>{loading ? text('解析 durable TaskRun…', 'resolving durable TaskRun…') : text('runtime 读取失败 · 保留结构场', 'runtime read failed · structural field retained')}</strong></div>
      </div>
      <div className="task-topology-canvas">
        <div className="task-role-column role-decision" /><div className="task-role-column role-investigation" /><div className="task-role-column role-enrichment" />
        <svg className="task-topology-edges blueprint" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path d="M 50 24 C 62 24, 70 34, 83 42" />
          <path d="M 83 42 C 70 52, 62 62, 50 62" />
          <path d="M 50 62 C 35 62, 26 44, 17 30" />
        </svg>
        {nodes.map((node) => (
          <div
            key={node.label}
            className="task-crystal task-crystal-blueprint"
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
          >
            <span className="task-crystal-core" />
            <span className="task-crystal-copy"><small>{node.role}</small><strong>{node.label}</strong><em>{text('结构位置', 'schema position')}</em></span>
          </div>
        ))}
        <div className="task-topology-watermark">{text('TASK / 委派 / 恢复场', 'TASK / DELEGATION / RECOVERY FIELD')}</div>
      </div>
    </div>
  )
}

function TaskLensBlueprint() {
  const { text } = useI18n()
  return (
    <div className="task-lens-blueprint">
      <Waypoints size={30} />
      <small>{text('选中 Task 档案', 'SELECTED TASK DOSSIER')}</small>
      <strong>{text('Task 运行镜片', 'Task runtime lens')}</strong>
      <div className="task-lens-schema">
        <span>ROLE / PROFILE</span><span>{text('父子关系', 'PARENT / CHILD')}</span><span>{text('事件时间线', 'EVENT TIMELINE')}</span><span>{text('能力调用', 'CAPABILITY INVOCATION')}</span>
      </div>
      <p>{text('选中真实 Task 后展开 durable events、CapabilityInvocation、budget、stop reason 与 evidence refs。', 'Select a real Task to inspect durable events, CapabilityInvocation, budget, stop reason, and evidence refs.')}</p>
    </div>
  )
}

function SkillBlueprintList() {
  const { text } = useI18n()
  return (
    <>
      {['VerifyFixBoundary', 'ResolveSourceConflict', 'TraceIncidentEvidence', 'AssessApplicability'].map((label, index) => (
        <div key={label} className="skill-blueprint-row">
          <span className="skill-glyph"><BookOpenCheck size={14} /></span>
          <span><small>{text('候选 / 种子家族', 'CANDIDATE / SEED FAMILY')}</small><strong>{label}</strong><em>{text('durable procedure 槽位', 'durable procedure slot')}</em></span>
          <b>{String(index + 1).padStart(2, '0')}</b>
        </div>
      ))}
    </>
  )
}

function SkillBlueprintDetail() {
  const { text } = useI18n()
  return (
    <div className="skill-blueprint-detail">
      <BrainCircuit size={30} />
      <small>{text('SKILL 版本 / 程序记忆', 'SKILL VERSION / PROCEDURAL MEMORY')}</small>
      <strong>{text('Skill Codex 结构', 'Skill Codex structure')}</strong>
      <div><span>{text('触发', 'trigger')}</span><span>{text('前置条件', 'preconditions')}</span><span>{text('程序', 'procedure')}</span><span>{text('验证', 'validation')}</span></div>
      <p>{text('Skill 保存可复用调查程序；事实读取始终回到当前 Evidence World。', 'Skill stores reusable investigation procedure; factual authority remains in the current Evidence World.')}</p>
    </div>
  )
}

function ExperienceBlueprint() {
  const { text } = useI18n()
  return (
    <div className="experience-blueprint">
      {['TRAJECTORY', 'EXPERIENCE CANDIDATE', 'EXPERIENCE PATTERN', 'SKILL PATCH', 'M7 REPLAY'].map((label, index) => (
        <div key={label} className="experience-blueprint-stage">
          <span>{String(index + 1).padStart(2, '0')}</span>
          <strong>{label}</strong>
          <small>{index === 4 ? text('promotion 前验证', 'validate before promotion') : text('durable 演化阶段', 'durable evolution stage')}</small>
        </div>
      ))}
    </div>
  )
}

const roleBlueprints = [
  { role_id: 'DecisionRole', alias: 'ORACLE', cn: '判谕者', tone: 'cyan', profile: 'DIRECT / RETRIEVE', state: 'M4.LightweightContext' },
  { role_id: 'InvestigationRole', alias: 'ARGUS', cn: '百眼调查者', tone: 'violet', profile: 'VERIFY / INVESTIGATE / WATCH', state: 'M4.InvestigationState' },
  { role_id: 'EnrichmentRole', alias: 'ALCHEMIST', cn: '炼证者', tone: 'amber', profile: 'ENRICHMENT', state: 'M3.EnrichmentState' },
] as const

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
  const focusedRecentTasks = useMemo(() => visibleTasks.filter((task) => !activeStatuses.has(task.status)).slice(0, 22), [visibleTasks])
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
    setParams(nextParams, { replace: true })
  }

  function inspectSkillRef(skillRef: string) {
    const key = skillFamilyKeyFromRef(skillRef)
    if (key) setSelectedSkillFamily(key)
    requestAnimationFrame(() => document.getElementById('skill-codex')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }

  return (
    <section className={`agents-space ${runtime ? 'runtime-loaded' : 'runtime-unresolved'}`}>
      <header className="runtime-stage-caption">
        <div>
          <p>{text('三种 Role，一条可追溯的行动链', 'THREE ROLES; ONE TRACEABLE CHAIN OF ACTION')}</p>
          <h1>{text('智能体', 'AGENT')} <span>{text('运行场', 'MACHINE')}</span></h1>
          <small>{text(
            'DecisionRole、InvestigationRole、EnrichmentRole 通过 Task、父子委派、CapabilityInvocation、Skill 与 Experience 串成一条持久执行链。',
            'DecisionRole, InvestigationRole, and EnrichmentRole connect through Task, parent-child delegation, CapabilityInvocation, Skill, and Experience into one durable execution chain.',
          )}</small>
        </div>
        <div className="agent-runtime-readout">
          <span className={activeCount > 0 ? 'live' : ''} />
          <div><small>{text('活跃任务', 'ACTIVE TASKS')}</small><strong>{runtime ? activeCount : '—'}</strong></div>
          <div><small>{text('持久运行', 'DURABLE RUNS')}</small><strong>{runtime ? totalRuns : '—'}</strong></div>
          <div><small>{text('能力调用', 'CAPABILITY INVOCATIONS')}</small><strong>{runtime?.recent_capabilities.length ?? '—'}</strong></div>
        </div>
      </header>
      {origin === 'case' && originCaseRef && (
        <div className="agent-origin case-origin">
          <span>CASE → TASK</span>
          <strong className="mono">{originCaseRef}</strong>
          <button onClick={() => navigate(`/investigations?case=${encodeURIComponent(originCaseRef)}`)}>{text('返回 Case', 'BACK TO CASE')}</button>
        </div>
      )}

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

      <div className={`role-theater ${focusedRole ? `has-role-focus focus-${focusedRole.toLowerCase()}` : ''}`}>
        <div className="role-axis" />
        {roleBlueprints.map((blueprint, index) => {
          const role = runtime?.roles.find((item) => item.role_id === blueprint.role_id)
          return role
            ? <RoleCard key={role.role_id} role={role} index={index} focusedRole={focusedRole} taskOwner={selectedTaskRole === role.role_id} onFocus={focusRole} reduceMotion={reduceMotion} />
            : <RoleBlueprint key={blueprint.role_id} blueprint={blueprint} index={index} loading={runtimeQuery.isLoading} focusedRole={focusedRole} onFocus={focusRole} />
        })}
      </div>

      {runtime && <ModelRuntimeRibbon runtime={runtime} />}
      {detailQuery.data && <RuntimeActivityView detail={detailQuery.data} onSkillSelect={inspectSkillRef} onTaskSelect={selectTask} />}

      <div id="agent-runtime-field" className={`agent-runtime-grid ${focusedRole ? `runtime-focus-${focusedRole.toLowerCase()}` : ''}`}>
        <section className={`task-field ${focusedRole ? 'role-owned-field' : ''}`}>
          <div className="instrument-section-head">
            <div><small>{text('持久 Task 场', 'DURABLE TASK FIELD')}</small><strong>{text('执行 / 委派拓扑', 'EXECUTION / DELEGATION TOPOLOGY')}</strong></div>
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
                {runtime && focusedActiveTasks.length === 0 && <div className="task-ledger-empty">{text('当前 Role focus 没有活动 durable Task。', 'No active durable tasks in current role focus.')}</div>}
              </div>
            </div>
            <div className="task-ledger-column history">
              <div className="task-ledger-title"><TimerReset size={12} /><strong>{text('近期终态历史', 'RECENT TERMINAL HISTORY')}</strong><span>{focusedRecentTasks.length}</span></div>
              <div>
                {focusedRecentTasks.map((task) => <TaskCard key={task.run_id} task={task} selected={task.run_id === selectedTask} onSelect={selectTask} />)}
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

      <div id="agent-memory-field" className="agent-memory-complex">
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
      </div>
    </section>
  )
}

function RoleCard({ role, index, focusedRole, taskOwner, onFocus, reduceMotion }: { role: AgentRoleRuntime; index: number; focusedRole: string | null; taskOwner: boolean; onFocus: (role: string | null) => void; reduceMotion: boolean }) {
  const { text } = useI18n()
  const presentation = rolePresentation[role.role_id] ?? { alias: role.role_id, cn: '', tone: 'cyan', copy: role.state_model, copyEn: role.state_model }
  const live = role.active_tasks > 0
  const failed = role.status_counts.failed ?? 0
  const blocked = role.status_counts.blocked ?? 0
  return (
    <motion.button
      className={`role-entity role-${role.role_id.toLowerCase()} tone-${presentation.tone} ${live ? 'role-live' : ''} ${taskOwner ? 'task-owner' : ''} ${focusedRole === role.role_id ? 'role-focused' : ''} ${focusedRole && focusedRole !== role.role_id ? 'role-dimmed' : ''}`}
      onClick={() => onFocus(focusedRole === role.role_id ? null : role.role_id)}
      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: focusedRole && focusedRole !== role.role_id ? .28 : 1, y: 0, scale: focusedRole === role.role_id ? 1.025 : 1 }}
      transition={{ delay: reduceMotion ? 0 : index * .08, duration: reduceMotion ? 0 : undefined }}
    >
      <RoleSigil role={role.role_id} live={live} />
      <div className="role-entity-copy">
        <small>{text(presentation.cn, role.role_id)} / {role.role_id}@{role.version}{taskOwner ? ' · TASK OWNER' : ''}</small>
        <strong>{presentation.alias}</strong>
        <p>{text(presentation.copy, presentation.copyEn)}</p>
        <div className="role-coordinates"><span>{role.planner_profile}</span><span>{role.state_model}</span><span>{role.default_execution_profile}</span></div>
      </div>
      <div className="role-entity-runtime">
        <b>{role.active_tasks}</b>
        <small>{live ? text('活动任务', 'ACTIVE TASKS') : text('空闲', 'IDLE')}</small>
        <span>{text(`${role.total_tasks} 次 durable run`, `${role.total_tasks} durable runs`)}</span>
        {(failed > 0 || blocked > 0) && <em>{text(`${failed} 失败 · ${blocked} 阻塞`, `${failed} failed · ${blocked} blocked`)}</em>}
      </div>
    </motion.button>
  )
}

function RoleSigil({ role, live }: { role: string; live: boolean }) {
  if (role === 'DecisionRole') {
    return (
      <div className={`role-sigil oracle-sigil ${live ? 'live' : ''}`} aria-hidden="true">
        <svg className="role-sigil-svg" viewBox="0 0 120 120">
          <circle className="sigil-field" cx="60" cy="60" r="47" />
          <path className="oracle-axis" d="M60 7V113" />
          <path className="oracle-axis oracle-axis-horizontal" d="M12 60H108" />
          <ellipse className="oracle-orbit orbit-a" cx="60" cy="60" rx="45" ry="17" transform="rotate(-18 60 60)" />
          <ellipse className="oracle-orbit orbit-b" cx="60" cy="60" rx="45" ry="17" transform="rotate(56 60 60)" />
          <circle className="oracle-eclipse-outer" cx="60" cy="60" r="20" />
          <circle className="oracle-eclipse-inner" cx="60" cy="60" r="11" />
          <circle className="sigil-node node-north" cx="60" cy="13" r="2" />
          <circle className="sigil-node node-east" cx="106" cy="60" r="2" />
          <circle className="sigil-node node-south" cx="60" cy="107" r="2" />
          <circle className="sigil-node node-west" cx="14" cy="60" r="2" />
        </svg>
      </div>
    )
  }
  if (role === 'InvestigationRole') {
    return (
      <div className={`role-sigil argus-sigil ${live ? 'live' : ''}`} aria-hidden="true">
        <svg className="role-sigil-svg" viewBox="0 0 120 120">
          <circle className="sigil-field" cx="60" cy="60" r="47" />
          <path className="argus-eye-shell" d="M15 60Q36 31 60 31Q84 31 105 60Q84 89 60 89Q36 89 15 60Z" />
          <ellipse className="argus-lens" cx="60" cy="60" rx="20" ry="28" />
          <circle className="argus-pupil" cx="60" cy="60" r="8" />
          <path className="argus-scan scan-a" d="M28 39Q60 12 92 39" />
          <path className="argus-scan scan-b" d="M28 81Q60 108 92 81" />
          <g className="argus-apertures">
            <circle cx="29" cy="35" r="4" /><circle cx="91" cy="35" r="4" />
            <circle cx="18" cy="72" r="3.5" /><circle cx="102" cy="72" r="3.5" />
            <circle cx="60" cy="104" r="4" />
          </g>
          <path className="argus-focal-axis" d="M60 8V25M60 95V112" />
        </svg>
      </div>
    )
  }
  return (
    <div className={`role-sigil alchemist-sigil ${live ? 'live' : ''}`} aria-hidden="true">
      <svg className="role-sigil-svg" viewBox="0 0 120 120">
        <circle className="sigil-field" cx="60" cy="60" r="47" />
        <g className="alchemist-processors">
          <circle className="processor-segment processor-deterministic" cx="60" cy="60" r="41" pathLength="100" />
          <circle className="processor-segment processor-graph" cx="60" cy="60" r="41" pathLength="100" />
          <circle className="processor-segment processor-semantic" cx="60" cy="60" r="41" pathLength="100" />
          <circle className="processor-segment processor-provider" cx="60" cy="60" r="41" pathLength="100" />
        </g>
        <path className="alchemist-lattice" d="M60 31L89 60L60 89L31 60Z" />
        <path className="alchemist-lattice inner" d="M60 43L77 60L60 77L43 60Z" />
        <path className="alchemist-cross" d="M60 18V43M102 60H77M60 102V77M18 60H43" />
        <circle className="alchemist-core" cx="60" cy="60" r="7" />
        <circle className="sigil-node node-north" cx="60" cy="18" r="2" />
        <circle className="sigil-node node-east" cx="102" cy="60" r="2" />
        <circle className="sigil-node node-south" cx="60" cy="102" r="2" />
        <circle className="sigil-node node-west" cx="18" cy="60" r="2" />
      </svg>
    </div>
  )
}
