import { ArrowUpRight } from "@phosphor-icons/react/dist/csr/ArrowUpRight"
import { GitBranch } from "@phosphor-icons/react/dist/csr/GitBranch"
import { Clock } from "@phosphor-icons/react/dist/csr/Clock"
import { Terminal } from "@phosphor-icons/react/dist/csr/Terminal"
import { TreeStructure } from "@phosphor-icons/react/dist/csr/TreeStructure"
import { Link } from 'react-router-dom'
import type { AgentTaskDetail, AgentTaskSummary } from '../../lib/api/agents'
import { useI18n } from '../../lib/i18n'
import { runtimeTaskLabel } from '../../lib/investigationPresentation'
import { taskOutcome, taskResult, taskTitle } from '../../lib/taskPresentation'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { TaskContextLedger, TaskModelLedger } from './TaskAuditSurfaces'

export function TaskCard({ task, selected, onSelect }: { task: AgentTaskSummary; selected: boolean; onSelect: (runId: string) => void }) {
  const { text, language } = useI18n()
  return <button className={`ops-task-row ${selected ? 'selected' : ''}`} onClick={() => onSelect(task.run_id)}>
    <span className="ops-task-subject"><strong>{taskTitle(task, text)}</strong><small>{runtimeTaskLabel(task.task_kind, text)} · {task.target_label || text('未记录具体对象', 'No specific target recorded')}</small></span>
    <span className={`ops-task-outcome outcome-${task.status}`}>{taskOutcome(task, text)}</span>
    <time dateTime={task.updated_at}>{new Date(task.updated_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</time>
    <ArrowUpRight size={16} />
  </button>
}

export function TaskTopology({ detail, onSelect }: { detail: AgentTaskDetail; onSelect: (runId: string) => void }) {
  const { text } = useI18n()
  const links = [
    ...(detail.parent ? [{ task: detail.parent, label: text('上级任务', 'Parent task') }] : []),
    ...(detail.predecessor && detail.predecessor.run_id !== detail.parent?.run_id ? [{ task: detail.predecessor, label: text('前序任务', 'Preceding task') }] : []),
    { task: detail.task, label: text('当前任务', 'Selected task') },
    ...detail.children.map(task => ({ task, label: text('委派任务', 'Delegated task') })),
  ]
  return <section className="ops-task-family">
    <h3><TreeStructure size={18} />{text('本次任务的执行关系', 'Execution relationships')}</h3>
    <p>{text('仅展示已记录的上级、前序与直接委派关系。', 'Recorded parent, predecessor and directly delegated tasks.')}</p>
    <ol>{links.map(({ task, label }) => <li key={task.run_id} className={task.run_id === detail.task.run_id ? 'current' : ''}>
      <span>{label}</span><button onClick={() => onSelect(task.run_id)}><strong>{taskTitle(task, text)}</strong><small>{taskOutcome(task, text)}</small></button>
    </li>)}</ol>
  </section>
}

function eventLabel(type: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = {
    TaskCreated: ['接收任务', 'Task accepted'], TaskStarted: ['开始执行', 'Execution started'], TaskPatched: ['更新执行状态', 'Task updated'],
    ContextUpdated: ['更新上下文', 'Context updated'], EvidenceFound: ['取得证据', 'Evidence found'], KnowledgeChanged: ['更新知识', 'Knowledge updated'],
    EnrichmentStateChanged: ['更新补全状态', 'Enrichment updated'], InvestigationStateChanged: ['更新调查状态', 'Investigation updated'],
    TaskBlocked: ['执行受阻', 'Execution blocked'], NeedInput: ['等待补充信息', 'Input needed'], NeedContext: ['等待证据或依赖', 'Evidence or dependency needed'],
    BudgetWarning: ['执行额度接近上限', 'Budget nearing its limit'], ArtifactProduced: ['保存运行材料', 'Artifact saved'], Progress: ['记录进展', 'Progress recorded'],
    TaskCompleted: ['执行完成', 'Execution completed'], TaskFailed: ['执行失败', 'Execution failed'], TaskCanceled: ['执行取消', 'Execution cancelled'],
  }
  return labels[type] ? text(...labels[type]) : text('记录运行事件', 'Runtime event recorded')
}

export function TaskDossier({ detail, onSkillSelect, onTaskSelect }: { detail: AgentTaskDetail; onSkillSelect: (skillRef: string) => void; onTaskSelect: (runId: string) => void }) {
  const { text } = useI18n()
  const task = detail.task
  return <article className="ops-task-detail">
    <header><span className={`ops-task-outcome outcome-${task.status}`}>{taskOutcome(task, text)}</span><h2>{taskTitle(task, text)}</h2>
      {task.target_label && <p>{task.target_label}</p>}
      <p className="ops-task-result">{taskResult(task, text)}</p>
      <div className="ops-task-links">
        {task.session_id && <Link to={`/start?session=${encodeURIComponent(task.session_id)}`}>{text('打开原始会话', 'Open conversation')}<ArrowUpRight size={14} /></Link>}
        {task.case_id && <Link to={`/investigations?case=${encodeURIComponent(task.case_id)}&from=task&run=${encodeURIComponent(task.run_id)}`}>{text('查看调查结果', 'Open investigation')}<ArrowUpRight size={14} /></Link>}
        {task.target_refs?.find(ref => ref.startsWith('object:')) && <Link to={`/intelligence?object=${encodeURIComponent(task.target_refs.find(ref => ref.startsWith('object:'))!.slice(7))}`}>{text('查看对象', 'Open target')}<ArrowUpRight size={14} /></Link>}
      </div>
      <small className="ops-task-time"><Clock size={14} />{text('更新于', 'Updated')} {new Date(task.updated_at).toLocaleString()}</small>
    </header>
    <Tabs defaultValue="process">
      <TabsList variant="line" aria-label={text('任务详情', 'Task detail')}>
        <TabsTrigger value="process">{text('执行过程', 'Process')}</TabsTrigger>
        <TabsTrigger value="calls">{text('工具与模型', 'Tools & models')}</TabsTrigger>
        <TabsTrigger value="context">{text('上下文与证据', 'Context & evidence')}</TabsTrigger>
      </TabsList>
      <TabsContent value="process">
        <TaskTopology detail={detail} onSelect={onTaskSelect} />
        <section className="ops-task-events"><h3><GitBranch size={17} />{text('执行时间线', 'Execution timeline')}</h3>
          {detail.events.length ? <ol>{detail.events.map(event => <li key={event.event_id}><span>{eventLabel(event.event_type, text)}</span><time dateTime={event.emitted_at}>{new Date(event.emitted_at).toLocaleString()}</time><details><summary>{text('事件详情', 'Event details')}</summary><code>{event.event_type} · {event.producer} · #{event.seq}</code></details></li>)}</ol> : <p>{text('没有已记录的执行事件。', 'No execution events recorded.')}</p>}
        </section>
      </TabsContent>
      <TabsContent value="calls">
        <h3><Terminal size={17} />{text('工具调用', 'Tool calls')}</h3>
        {detail.capabilities.length ? <div className="ops-tool-list">{detail.capabilities.map(item => <details key={item.invocation_id} open={Boolean(item.failure_code || item.failure_detail)}>
          <summary><strong>{item.capability_id}</strong><span>{['failed', 'blocked'].includes(item.status) ? text('调用失败或受阻', 'Failed or blocked') : item.status === 'succeeded' || item.status === 'completed' ? text('已完成', 'Completed') : text('查看调用状态', 'Review call state')}</span></summary>
          {(item.failure_code || item.failure_detail) && <p role="status" className="ops-call-failure">{item.failure_detail || item.failure_code}</p>}
          <dl><dt>{text('实现', 'Implementation')}</dt><dd>{item.tool_impl_id}</dd><dt>{text('状态', 'Status')}</dt><dd>{item.status}</dd><dt>{text('调用标识', 'Invocation')}</dt><dd>{item.invocation_id}</dd><dt>{text('输出', 'Output')}</dt><dd>{item.canonical_output_ref || '—'}</dd><dt>{text('错误代码', 'Failure code')}</dt><dd>{item.failure_code || '—'}</dd><dt>{text('策略', 'Policy')}</dt><dd>{item.policy_decision_ref || '—'}</dd><dt>{text('原始材料', 'Raw artifact')}</dt><dd>{item.raw_artifact_ref || '—'}</dd><dt>{text('操作回执', 'Effect receipt')}</dt><dd>{item.effect_receipt_ref || '—'}</dd><dt>{text('观测类型', 'Observation class')}</dt><dd>{item.observation_class || '—'}</dd></dl>
        </details>)}</div> : <p className="ops-empty">{text('本次任务没有已记录的工具调用。', 'No tool calls recorded for this task.')}</p>}
        <TaskModelLedger attempts={detail.model_attempts} />
        <details className="ops-technical"><summary>{text('预算与用量', 'Budget and usage')}</summary>{detail.budget ? <dl>{Object.entries(detail.budget.limits).map(([resource, limit]) => <div key={resource}><dt>{resource}</dt><dd>{text('已用', 'Used')} {detail.budget!.committed[resource] ?? 0} / {limit} · {text('预留', 'Reserved')} {detail.budget!.reserved[resource] ?? 0} · {text('剩余', 'Remaining')} {detail.budget!.remaining[resource] ?? '—'}</dd></div>)}</dl> : <p>{text('未记录预算账户。', 'No budget account recorded.')}</p>}</details>
      </TabsContent>
      <TabsContent value="context">
        <TaskContextLedger context={detail.context} />
        <details className="ops-technical"><summary>{text('提示装配与技能', 'Prompt assemblies & skills')} · {detail.prompt_assemblies.length}</summary>
          {detail.prompt_assemblies.map(assembly => <section key={assembly.assembly_id}><small>{new Date(assembly.created_at).toLocaleString()}</small><div className="ops-task-links">{assembly.materialized_skill_refs.map(ref => <button key={ref} onClick={() => onSkillSelect(ref)}>{ref}</button>)}</div><dl><dt>{text('装配标识', 'Assembly')}</dt><dd>{assembly.assembly_id}</dd><dt>{text('角色版本', 'Role revision')}</dt><dd>{assembly.role_revision}</dd></dl>{assembly.fragments.map((fragment, i) => <p key={i}>{fragment.source_ref} · {fragment.selection_reason}</p>)}</section>)}
        </details>
      </TabsContent>
    </Tabs>
    <details className="ops-technical"><summary>{text('技术详情', 'Technical details')}</summary><dl><dt>{text('运行标识', 'Run ID')}</dt><dd>{task.run_id}</dd><dt>{text('任务类型', 'Task kind')}</dt><dd>{task.task_kind}</dd><dt>{text('执行角色', 'Role')}</dt><dd>{task.role_id}@{task.role_version}</dd><dt>{text('状态', 'Status')}</dt><dd>{task.status}</dd><dt>{text('停止原因', 'Stop reason')}</dt><dd>{task.stop_reason || '—'}</dd><dt>{text('请求标识', 'Request')}</dt><dd>{task.request_id || '—'}</dd><dt>{text('目标引用', 'Target references')}</dt><dd>{task.target_refs?.join(', ') || '—'}</dd></dl></details>
  </article>
}
