import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Activity,
  BookOpenCheck,
  BrainCircuit,
  ChevronRight,
  ArrowDownRight,
  CircleDot,
  GitFork,
  Orbit,
  TerminalSquare,
  TimerReset,
  Waypoints,
} from 'lucide-react'
import { getAgentControlledProof, getAgentLearning, getAgentRuntime, getAgentTask, getCompetitionProofRun, type AgentControlledProofCase, type AgentRoleRuntime, type AgentTaskSummary, type ProductSkill, type ProofRunDetail } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { dominantRuntimeName, rankRuntimeCounts, runtimeToken } from '../lib/runtimePresentation'

const rolePresentation: Record<string, { alias: string; cn: string; tone: string; copy: string; copyEn: string }> = {
  DecisionRole: { alias: 'ORACLE', cn: '判谕者', tone: 'cyan', copy: '证据进入收束阶段后，ORACLE 生成 Decision，并保留引用、冲突与未决项。', copyEn: 'ORACLE closes verified context into a Decision while preserving citations, conflicts, and unknowns.' },
  InvestigationRole: { alias: 'ARGUS', cn: '百眼调查者', tone: 'violet', copy: 'ARGUS 围绕 EvidenceNeed 推进持久 Case，选择 Skill 与 Capability；需要补证时委派 Enrichment。', copyEn: 'ARGUS advances a durable Case around EvidenceNeed, selects Skill and Capability, and delegates Enrichment when required.' },
  EnrichmentRole: { alias: 'ALCHEMIST', cn: '炼证者', tone: 'amber', copy: 'ALCHEMIST 接收 Enrichment 子任务，把缺失维度补成新的 Evidence 与 Knowledge。', copyEn: 'ALCHEMIST receives Enrichment child tasks and turns missing dimensions into new Evidence and Knowledge.' },
}

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
        <div><small>FAILED / UNKNOWN</small><strong>{model.failed_attempt_count} / {model.unknown_after_dispatch_count}</strong><span>{model.p95_latency_ms == null ? 'p95 unavailable' : `p95 ${model.p95_latency_ms} ms`}</span></div>
        <i />
        <div><small>PROVIDER / MODEL</small><strong>{provider ?? '—'}</strong><span>{actualModel ?? '—'}</span></div>
      </div>
      <div className="agent-control-runtime-line">
        <span><b>{control.dependency_wake_count}</b> dependency wakes</span>
        <span><b>{control.waiting_event_count}</b> waiting boundaries</span>
        <span><b>{control.wake_latency_measurement.toUpperCase()}</b> wake latency</span>
        {stopReasons.map(([reason, count]) => <span key={reason}><b>{count}</b> {runtimeToken(reason)}</span>)}
      </div>
    </section>
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
        <div><small>{text('规范执行拓扑', 'CANONICAL EXECUTION TOPOLOGY')}</small><strong>{loading ? text('解析 durable TaskRun…', 'resolving durable TaskRun…') : text('runtime 不可用 · 保留结构场', 'runtime unavailable · structural field retained')}</strong></div>
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

const activeStatuses = new Set(['submitted', 'queued', 'running', 'waiting_input', 'waiting_dependency'])
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
  const proofRunRef = params.get('proofRun')
  const caseRunRef = params.get('caseRun')
  const originCaseRef = params.get('caseRef')
  const runtimeQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 12_000 })
  const runtime = runtimeQuery.data
  const learningQuery = useQuery({ queryKey: ['agent-learning'], queryFn: getAgentLearning, refetchInterval: 30_000 })
  const learning = learningQuery.data
  const proofQuery = useQuery({ queryKey: ['agent-controlled-proof'], queryFn: getAgentControlledProof, staleTime: 60_000 })
  const proofRunQuery = useQuery({
    queryKey: ['agent-controlled-proof-run', proofQuery.data?.benchmark_run_id],
    queryFn: () => getCompetitionProofRun(proofQuery.data!.benchmark_run_id),
    enabled: Boolean(proofQuery.data?.benchmark_run_id),
    staleTime: 60_000,
  })
  const initialTask = runtime?.recent_tasks.find((task) => activeStatuses.has(task.status))?.run_id ?? runtime?.recent_tasks[0]?.run_id ?? null
  const requestedRun = params.get('run')
  const selectedTask = requestedRun ?? initialTask
  const detailQuery = useQuery({ queryKey: ['agent-task', selectedTask], queryFn: () => getAgentTask(selectedTask!), enabled: Boolean(selectedTask), refetchInterval: selectedTask ? 10_000 : false })
  const selectedTaskRole = detailQuery.data?.task.role_id
    ?? runtime?.recent_tasks.find((task) => task.run_id === selectedTask)?.role_id
    ?? null
  const skillFamilies = useMemo(() => groupSkillFamilies(learning?.skills ?? []), [learning?.skills])
  const [selectedSkillFamily, setSelectedSkillFamily] = useState<string | null>(null)
  const focusedRole = roleParam && rolePresentation[roleParam] ? roleParam : null
  const selectedSkill = skillFamilies.find((item) => item.key === (selectedSkillFamily ?? skillFamilies[0]?.key)) ?? null
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
      {origin === 'proof' && (proofRunRef || caseRunRef) && (
        <div className="agent-origin">
          <span>PROOF → TASK</span>
          <strong className="mono">{proofRunRef ?? 'benchmark-run'}</strong>
          {caseRunRef && <em className="mono">{caseRunRef}</em>}
          <button onClick={() => navigate(`/observatory?mode=proof&run=${encodeURIComponent(proofRunRef ?? '')}`)}>{text('返回 PROOF', 'BACK TO PROOF')}</button>
        </div>
      )}
      {origin === 'case' && originCaseRef && (
        <div className="agent-origin case-origin">
          <span>CASE → TASK</span>
          <strong className="mono">{originCaseRef}</strong>
          <button onClick={() => navigate(`/investigations?case=${encodeURIComponent(originCaseRef)}`)}>{text('返回 Case', 'BACK TO CASE')}</button>
        </div>
      )}

      {(runtimeQuery.isError || learningQuery.isError) && (
        <div className="agent-seam-fault">
          <TerminalSquare size={14} />
          <div>
            <small>{text('产品读取降级', 'PRODUCT READ DEGRADED')}</small>
            <strong>{runtimeQuery.isError
              ? text('Agent Runtime 当前不可读；三 Role 权威结构保持可见。', 'Agent Runtime is unreadable; the three canonical Roles remain visible.')
              : text('Skill / Experience read 当前不可用；Task Runtime 保持独立可读。', 'Skill / Experience read is unavailable; Task Runtime remains independently readable.')}</strong>
          </div>
          <span>{runtimeQuery.isError ? 'runtime seam' : 'learning seam'}</span>
          <button className="recovery-action" onClick={() => void (runtimeQuery.isError ? runtimeQuery.refetch() : learningQuery.refetch())}>{runtimeQuery.isError ? text('重试 Runtime read', 'RETRY RUNTIME READ') : text('重试 Learning read', 'RETRY LEARNING READ')}</button>
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
      {detailQuery.data && <RuntimeActivityView detail={detailQuery.data} onSkillSelect={inspectSkillRef} />}
      {proofQuery.data && <AgentControlledProof proof={proofQuery.data} detail={proofRunQuery.data ?? null} />}

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
          <div className="instrument-section-head"><div><small>{text('SKILL 典藏', 'SKILL CODEX')}</small><strong>{text('持久程序记忆', 'DURABLE PROCEDURAL MEMORY')}</strong></div><span>{text(String(learning?.skills.length ?? 0) + ' 条记录 · ' + String(skillFamilies.length) + ' 个家族', String(learning?.skills.length ?? 0) + ' records · ' + String(skillFamilies.length) + ' families')}</span></div>
          <div className="skill-codex-body">
            <div className="skill-family-list">
              {skillFamilies.length
                ? skillFamilies.map((family) => <button key={family.key} className={family.key === selectedSkill?.key ? 'selected' : ''} onClick={() => setSelectedSkillFamily(family.key)}><span className="skill-glyph"><BookOpenCheck size={15} /></span><span><small>{family.records.map((item) => item.status).join(' · ')}</small><strong>{family.label}</strong><em>{text(`${family.records.length} 条 durable 记录`, `${family.records.length} durable records`)}</em></span><ChevronRight size={14} /></button>)
                : <SkillBlueprintList />}
            </div>
            <div className="skill-detail">
              {selectedSkill ? <SkillFamilyDetail family={selectedSkill} /> : <SkillBlueprintDetail />}
            </div>
          </div>
        </section>

        <section className="experience-memory">
          <div className="instrument-section-head"><div><small>{text('经验记忆', 'EXPERIENCE MEMORY')}</small><strong>TRAJECTORY → EXPERIENCE → SKILL</strong></div><span>{text(`${learning?.experiences.length ?? 0} 条 durable Experience`, `${learning?.experiences.length ?? 0} durable experiences`)}</span></div>
          {learning ? <ExperienceMemory learning={learning} /> : <ExperienceBlueprint />}
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

function RuntimeActivityView({ detail, onSkillSelect }: { detail: Awaited<ReturnType<typeof getAgentTask>>; onSkillSelect: (skillRef: string) => void }) {
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

function AgentControlledProof({ proof, detail }: { proof: Awaited<ReturnType<typeof getAgentControlledProof>>; detail: ProofRunDetail | null }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  return (
    <section className="agent-controlled-proof">
      <div className="agent-proof-seal"><BookOpenCheck size={17} /><span>FROZEN PROOF</span></div>
      <div className="agent-proof-copy">
        <small>{text('AGENT 受控运行回归', 'AGENT CONTROLLED RUNTIME REGRESSION')}</small>
        <strong>{proof.suite_ref}</strong>
        <span>{text('这组结果来自 M5 frozen controlled benchmark；它证明机制，不代表当前 LIVE Agent 成功率。', 'This result comes from the frozen M5 controlled benchmark. It proves mechanisms, not the current LIVE Agent success rate.')}</span>
      </div>
      <div className="agent-proof-score"><strong>{proof.cases.length}/{proof.cases.length}</strong><small>CONTROLLED CASES</small></div>
      <div className="agent-proof-cases">
        {proof.cases.map((item) => <AgentProofCase key={item.case_id} item={item} proof={proof} detail={detail} />)}
      </div>
      <button className="agent-proof-open" onClick={() => navigate(`/observatory?mode=proof&run=${encodeURIComponent(proof.benchmark_run_id)}`)}>{text('打开完整冻结 Run', 'OPEN FULL FROZEN RUN')}</button>
    </section>
  )
}

function AgentProofCase({ item, proof, detail }: { item: AgentControlledProofCase; proof: Awaited<ReturnType<typeof getAgentControlledProof>>; detail: ProofRunDetail | null }) {
  const navigate = useNavigate()
  const metric = Object.entries(item.metrics)[0]
  const taskCoordinate = item.task_run_ids[0] ?? null
  const caseRun = detail?.cases.find((candidate) => candidate.case_ref.split('@', 1)[0] === item.case_id) ?? null
  return (
    <button
      type="button"
      disabled={!caseRun}
      onClick={() => caseRun && navigate(`/observatory?${new URLSearchParams({ mode: 'proof', run: proof.benchmark_run_id, caseRun: caseRun.case_run_id }).toString()}`)}
    >
      <i className="state-passed" />
      <span>
        <small>{item.case_id}</small>
        <strong>{metric ? `${shortMetricName(metric[0])} ${formatProofMetric(metric[1])}` : 'measured'}</strong>
      </span>
      <em title={taskCoordinate ?? item.subsystem ?? undefined}>{taskCoordinate ? `Task ${taskCoordinate.slice(0, 8)} · frozen` : item.subsystem ?? 'controlled runtime'}</em>
    </button>
  )
}

function shortMetricName(value: string) {
  return value.replace(/^agent\./, '').replaceAll('_', ' ').toUpperCase()
}

function formatProofMetric(value: number) {
  if (value === 0 || value === 1) return value.toFixed(1)
  return value.toFixed(3)
}

function TaskTopology({ tasks, selectedTask, onSelect, focusedRole }: { tasks: AgentTaskSummary[]; selectedTask: string | null; onSelect: (runId: string) => void; focusedRole: string | null }) {
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
      <div><small>{text('真实 parent / child 关系', 'REAL PARENT / CHILD LINKS ONLY')}</small><strong>{text(`${topology.nodes.length} 个可见节点 · ${topology.edges.length} 条委派关系`, `${topology.nodes.length} visible nodes · ${topology.edges.length} delegation links`)}</strong></div>
    </div>
    <div className={`task-topology-canvas ${focusedRole ? 'single-role-topology' : ''}`}>
      {focusedRole
        ? <div className={`task-role-column role-focus-column focus-${focusedRole.toLowerCase()}`} />
        : <><div className="task-role-column role-decision" /><div className="task-role-column role-investigation" /><div className="task-role-column role-enrichment" /></>}
      <svg className="task-topology-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {topology.edges.map((edge) => {
          const active = edge.parent.run_id === selectedTask || edge.child.run_id === selectedTask || Boolean(selectedCase && edge.parent.task.case_id === selectedCase && edge.child.task.case_id === selectedCase)
          const delegating = activeStatuses.has(edge.child.task.status)
          return <path key={`${edge.parent.run_id}:${edge.child.run_id}`} className={`${active ? 'active' : selectedTask ? 'dimmed' : ''} ${delegating ? 'delegating' : 'frozen'}`} d={`M ${edge.parent.x} ${edge.parent.y} C ${edge.parent.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${(edge.parent.y + edge.child.y) / 2}, ${edge.child.x} ${edge.child.y}`} />
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
          animate={{ opacity: related ? 1 : .2, scale: task.run_id === selectedTask ? 1.1 : 1 }}
          transition={{ type: 'spring', stiffness: 230, damping: 25 }}
          title={`${task.role_id} · ${task.task_kind} · ${task.status}`}
        >
          <span className="task-crystal-core" />
          <span className="task-crystal-copy"><small>{rolePresentation[task.role_id]?.alias ?? task.role_id}</small><strong>{shortTaskKind(task.task_kind)}</strong><em>{task.status}</em></span>
          {task.parent_run_id && <GitFork size={10} className="task-child-mark" />}
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
  const { text } = useI18n()
  const child = Boolean(task.parent_run_id)
  return (
    <button className={`task-ledger-row ${selected ? 'selected' : ''} state-${task.status}`} onClick={() => onSelect(task.run_id)}>
      <span className="task-role-mark">{rolePresentation[task.role_id]?.alias.slice(0, 2) ?? 'RT'}</span>
      <span className="task-main"><small>{task.role_id} · {child ? 'CHILD' : 'ROOT'}</small><strong>{humanize(task.task_kind)}</strong><em>{task.last_event_type ?? text('无事件', 'no event')} · {text(`${task.event_count} 个 events`, `${task.event_count} events`)}</em></span>
      <span className="task-tail"><b>{task.status}</b>{child ? <GitFork size={12} /> : <ArrowDownRight size={12} />}</span>
    </button>
  )
}

function TaskDossier({ detail, onSkillSelect }: { detail: Awaited<ReturnType<typeof getAgentTask>>; onSkillSelect: (skillRef: string) => void }) {
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
      {(task.case_id || task.parent_run_id) && (
        <div className="task-coordinate-links">
          {task.case_id && <button onClick={() => {
            const query = new URLSearchParams({ case: task.case_id!, from: 'task', run: task.run_id })
            navigate(`/investigations?${query.toString()}`)
          }}><Waypoints size={11} /> {text('打开所属 Case', 'OPEN CASE')}<span className="mono">{task.case_id}</span></button>}
          {task.parent_run_id && <button onClick={() => navigate(`/agents?run=${encodeURIComponent(task.parent_run_id!)}`)}><GitFork size={11} /> {text('打开 Parent Task', 'OPEN PARENT TASK')}<span className="mono">{task.parent_run_id}</span></button>}
        </div>
      )}
      <div className="task-facts">
        <TaskFact label="CASE" value={task.case_id ?? text('独立 Task', 'standalone')} mono />
        <TaskFact label="PARENT" value={task.parent_run_id ?? text('根 Task', 'root task')} mono />
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
                <TaskFact label="POLICY" value={item.policy_decision_ref ?? text('不可用', 'unavailable')} mono />
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

function skillFamilyKeyFromRef(ref: string) {
  const id = ref.replace(/^skill:/, '').replace(/@\d+$/, '')
  const tail = id.split('.').at(-1) ?? id
  return tail.replaceAll('_', '').toLowerCase()
}


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
  const { text } = useI18n()
  const primary = family.records[0]
  return <div className="skill-detail-stack">
    <div className="skill-detail-head">
      <div><small>{text('SKILL 家族', 'SKILL FAMILY')}</small><strong>{family.label}</strong><span className="mono">{primary.skill_ref}</span></div>
      <div className="skill-status-stack">{family.records.map((item) => <span key={item.skill_ref} className={`skill-status status-${item.status}`}>{item.status}</span>)}</div>
    </div>
    <div className="skill-record-stack">{family.records.map((item) => (
      <article key={item.skill_ref} className={`skill-record status-${item.status}`}>
        <div className="skill-record-title">
          <div><small>{item.source_type}</small><strong>{item.skill_id}@{item.version}</strong><span className="mono">{item.skill_ref}</span></div>
          <b>{item.status}</b>
        </div>
        {item.status === 'candidate' && (
          <div className="skill-candidate-boundary">
            <span>CANDIDATE</span>
            <p>{text('候选程序仍等待 validation / promotion；页面不把 seed presence 写成在线生效。', 'Candidate procedure awaits validation / promotion; seed presence is not presented as online activation.')}</p>
          </div>
        )}
        <div className="skill-record-body">
          <section className="skill-procedure-pane">
            <div className="skill-chips">{item.task_patterns.map((value) => <span key={value}>{value}</span>)}{item.required_capability_classes.map((value) => <span key={value}>{value}</span>)}</div>
            <div className="skill-procedure">{item.steps.map((step, index) => <div key={String(step.step_id ?? index)}><span>{String(index + 1).padStart(2,'0')}</span><p>{String(step.semantic_instruction ?? step.step_id ?? text('流程步骤', 'procedure step'))}</p></div>)}</div>
            {item.failure_guards.length > 0 && <div className="skill-guards"><small>{text('失败护栏', 'FAILURE GUARDS')}</small><p>{item.failure_guards.join(' · ')}</p></div>}
            {item.fallbacks.length > 0 && <div className="skill-guards"><small>{text('回退路径', 'FALLBACKS')}</small><p>{item.fallbacks.join(' · ')}</p></div>}
            {item.stop_conditions.length > 0 && <div className="skill-guards"><small>{text('停止条件', 'STOP CONDITIONS')}</small><p>{item.stop_conditions.join(' · ')}</p></div>}
          </section>
          <aside className="skill-governance">
            <SkillGovernanceRef label="VALIDATION" values={item.validation_ref ? [item.validation_ref] : []} empty={text('尚无 validation ref', 'no validation ref')} />
            <SkillGovernanceRef label="SUPPORT TRAJECTORY" values={item.supporting_trajectory_refs} empty="—" />
            <SkillGovernanceRef label="EXPERIENCE PATTERN" values={item.supporting_experience_pattern_refs} empty="—" />
            <SkillGovernanceRef label="VALIDATION CASE" values={item.validation_case_refs} empty="—" />
            <SkillGovernanceRef label="PROMOTION HISTORY" values={item.promotion_history} empty="—" />
            <div className="skill-origin"><small>PROVENANCE ORIGIN</small><strong>{item.provenance_origin}</strong></div>
          </aside>
        </div>
      </article>
    ))}</div>
  </div>
}

function SkillGovernanceRef({ label, values, empty }: { label: string; values: string[]; empty: string }) {
  return (
    <div className="skill-governance-ref">
      <small>{label}</small>
      {values.length ? values.slice(0, 4).map((value) => <span key={value} className="mono">{value}</span>) : <em>{empty}</em>}
    </div>
  )
}

function ExperienceMemory({ learning }: { learning: Awaited<ReturnType<typeof getAgentLearning>> | null }) {
  const { text } = useI18n()
  const [selectedExperienceId, setSelectedExperienceId] = useState<string | null>(null)
  const stages = [
    ['Trajectory', learning?.trajectory_count ?? 0],
    ['Candidate', learning?.experience_candidate_count ?? 0],
    ['Experience', learning?.experiences.length ?? 0],
    ['Skill Patch', learning?.skills.filter((item) => item.source_type === 'experience_derived').length ?? 0],
  ] as const
  const selectedExperience = learning?.experiences.find((item) => item.experience_version_id === selectedExperienceId) ?? learning?.experiences[0] ?? null
  const supportTrajectories = selectedExperience?.support_records.filter((item) => item.outcome !== 'failure') ?? []
  const counterexampleTrajectories = selectedExperience?.support_records.filter((item) => item.outcome === 'failure') ?? []
  const linkedSkills = selectedExperience ? (learning?.skills ?? []).filter((skill) => {
    const aliases = new Set([
      selectedExperience.experience_id,
      selectedExperience.experience_version_id,
      `experience:${selectedExperience.experience_id}`,
      `experience:${selectedExperience.experience_id}@${selectedExperience.version}`,
    ])
    return skill.supporting_experience_pattern_refs.some((ref) => aliases.has(ref))
  }) : []
  return <div className="experience-body">
    <div className="experience-pipeline">{stages.map(([label, count], index) => <div key={label} className="experience-stage"><span className="experience-stage-icon"><BrainCircuit size={16} /></span><div><small>STAGE {String(index + 1).padStart(2,'0')}</small><strong>{label}</strong><b>{count}</b></div>{index < stages.length - 1 && <ChevronRight size={14} className="experience-arrow" />}</div>)}</div>
    {(learning?.experiences.length ?? 0) === 0 ? <div className="experience-empty"><Orbit size={30} /><div><strong>{text('尚无 durable Experience', 'NO DURABLE EXPERIENCE YET')}</strong><p>{text('Trajectory 已进入经验流水线；durable Experience 尚未形成时，界面保持空态，不制造学习结果。', 'Trajectories have entered the learning pipeline. Until a durable Experience is persisted, this surface remains empty rather than inventing a learned result.')}</p></div></div> : <div className="experience-workbench">
      <div className="experience-list">{learning!.experiences.map((item, index) => <button key={item.experience_version_id} className={item.experience_version_id === selectedExperience?.experience_version_id ? 'selected' : ''} onClick={() => setSelectedExperienceId(item.experience_version_id)}><span>{String(index + 1).padStart(2,'0')}</span><div><small>{item.status} · v{item.version}</small><strong>{item.name}</strong><em>{item.task_signature}</em></div><b>{item.success_count}/{item.failure_count}/{item.partial_count}</b></button>)}</div>
      {selectedExperience && <div className="experience-inspector">
        <div className="experience-inspector-head"><div><small>{text('持久 Experience', 'DURABLE EXPERIENCE')}</small><strong>{selectedExperience.name}</strong><span className="mono">{selectedExperience.experience_version_id}</span></div><div><small>{text('结果历史', 'OUTCOME HISTORY')}</small><strong>{selectedExperience.success_count} / {selectedExperience.failure_count} / {selectedExperience.partial_count}</strong><span>{text('成功 · 失败 · 部分完成', 'success · failure · partial')}</span></div></div>
        <div className="experience-evidence-wall">
          <section className="trajectory-wall support">
            <div className="trajectory-wall-head"><small>{text('支持轨迹', 'SUPPORT TRAJECTORIES')}</small><strong>{supportTrajectories.length}</strong></div>
            <div>
              {supportTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {supportTrajectories.length === 0 && <p>{text('当前 ExperienceVersion 没有持久化 support trajectory。', 'No persisted support trajectory for this ExperienceVersion.')}</p>}
            </div>
          </section>
          <section className="experience-pattern-core">
            <small>EXPERIENCE PATTERN</small>
            <strong>{selectedExperience.name}</strong>
            <span>{selectedExperience.status} · v{selectedExperience.version}</span>
            <div className="experience-pattern-score"><b>{selectedExperience.success_count}</b><i /><b>{selectedExperience.failure_count}</b></div>
            <em>{text(linkedSkills.length + ' 个声明关联 Skill Patch', linkedSkills.length + ' declared Skill Patch links')}</em>
          </section>
          <section className="trajectory-wall counterexample">
            <div className="trajectory-wall-head"><small>{text('反例轨迹', 'COUNTEREXAMPLES')}</small><strong>{counterexampleTrajectories.length}</strong></div>
            <div>
              {counterexampleTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {counterexampleTrajectories.length === 0 && <p>{text('当前 ExperienceVersion 没有持久化 counterexample。', 'No persisted counterexample for this ExperienceVersion.')}</p>}
            </div>
          </section>
        </div>
        <ExperienceVector label={text('触发信号', 'TRIGGER SIGNALS')} values={selectedExperience.trigger_signals} />
        <ExperienceVector label={text('适用条件', 'APPLICABLE CONDITIONS')} values={selectedExperience.applicable_conditions} />
        <ExperienceVector label={text('推荐动作', 'RECOMMENDED ACTIONS')} values={selectedExperience.recommended_actions} />
        <ExperienceVector label={text('证据预期', 'EVIDENCE EXPECTATION')} values={selectedExperience.evidence_expectation} />
        <ExperienceVector label={text('失败模式', 'FAILURE MODES')} values={selectedExperience.failure_modes} tone="failure" />
        <ExperienceVector label={text('停止条件', 'STOP CONDITIONS')} values={selectedExperience.stop_conditions} />
        <ExperienceVector label={text('回退动作', 'FALLBACK ACTIONS')} values={selectedExperience.fallback_actions} />
        <div className="experience-linked-skills"><small>{text('声明关联的 Skill Patch', 'DECLARED SKILL PATCH LINKS')}</small>{linkedSkills.length ? <div>{linkedSkills.map((skill) => <span key={skill.skill_ref}>{skill.skill_id}@{skill.version} · {skill.status}</span>)}</div> : <p>{text('当前 Skill registry 没有声明指向该 Experience pattern 的 supporting ref。', 'No Skill in the current registry declares a supporting reference to this Experience pattern.')}</p>}</div>
      </div>}
    </div>}
  </div>
}

function TrajectoryEvidence({ record, experienceRef }: { record: Awaited<ReturnType<typeof getAgentLearning>>['experiences'][number]['support_records'][number]; experienceRef: string }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const casePath = `/investigations?${new URLSearchParams({ case: record.case_id, from: 'experience', experience: experienceRef, trajectory: record.trajectory_id }).toString()}`
  return (
    <article className={'trajectory-evidence outcome-' + record.outcome}>
      <span><small>{record.outcome}</small><strong className="mono">{record.trajectory_id}</strong></span>
      <div>{formatEvaluation(record.evaluation).map((item) => <em key={item}>{item}</em>)}</div>
      <div className="trajectory-runtime-coordinate">
        <span>{record.trajectory_status}</span>
        <span>{record.tool_calls} tools</span>
        <span>{record.latency_ms != null ? `${record.latency_ms}ms` : 'latency —'}</span>
      </div>
      <button onClick={() => navigate(casePath)}><Waypoints size={10} /> {text('打开来源 Case', 'OPEN SOURCE CASE')}<span className="mono">{record.case_id}</span></button>
      <b>{record.evaluator}</b>
    </article>
  )
}

function formatEvaluation(evaluation: Record<string, unknown>) {
  const items = Object.entries(evaluation).slice(0, 3).map(([key, value]) => {
    if (typeof value === 'number') return key + '=' + (Number.isInteger(value) ? String(value) : value.toFixed(3))
    if (typeof value === 'boolean' || typeof value === 'string') return key + '=' + String(value)
    return key
  })
  return items.length ? items : ['evaluation persisted']
}

function ExperienceVector({ label, values, tone = 'default' }: { label: string; values: string[]; tone?: 'default' | 'failure' }) {
  return <div className={`experience-vector tone-${tone}`}><small>{label}</small>{values.length ? <div>{values.map((value, index) => <span key={`${value}:${index}`}>{value}</span>)}</div> : <p>—</p>}</div>
}
