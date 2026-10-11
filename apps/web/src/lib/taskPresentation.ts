import type { AgentTaskSummary } from './api/agents'
import { investigationStopMessage, runtimeTaskLabel } from './investigationPresentation'

type Translate = (zh: string, en: string) => string

export function taskTitle(task: AgentTaskSummary, text: Translate) {
  if (task.goal) return task.goal
  const label = runtimeTaskLabel(task.task_kind, text)
  return label === task.task_kind.replaceAll('_', ' ') ? text('任务执行', 'Task execution') : label
}

export function taskOutcome(task: AgentTaskSummary, text: Translate) {
  if (task.status === 'failed' || task.status === 'timed_out') return text('执行失败', 'Failed')
  if (task.stop_reason === 'no_eligible_enrichment_operator') return text('暂无适用的补全操作', 'No applicable enrichment')
  if (['completed', 'succeeded'].includes(task.status) && task.stop_reason === 'partial_evidence') return text('已形成部分结论', 'Partial findings')
  if (['completed', 'succeeded'].includes(task.status) && task.stop_reason === 'evidence_insufficient') return text('证据仍不足', 'Evidence insufficient')
  const labels: Record<string, [string, string]> = {
    submitted: ['已接收', 'Accepted'], queued: ['排队中', 'Queued'], running: ['执行中', 'In progress'],
    waiting_input: ['等待补充信息', 'Awaiting input'], waiting_dependency: ['等待证据或依赖', 'Awaiting evidence or dependencies'],
    completed: ['已完成', 'Completed'], succeeded: ['已完成', 'Completed'], canceled: ['已取消', 'Cancelled'],
    cancelled: ['已取消', 'Cancelled'], blocked: ['执行受阻', 'Blocked'],
  }
  return labels[task.status] ? text(...labels[task.status]) : text('查看执行状态', 'Review execution state')
}

export function taskResult(task: AgentTaskSummary, text: Translate) {
  if (task.stop_reason === 'partial_evidence') return text('本轮仅形成部分结论，仍有证据缺口。打开原始会话或调查查看已确认内容与待核实事项。', 'Only partial conclusions were reached; evidence gaps remain. Open the original conversation or investigation to review confirmed findings and unresolved questions.')
  if (task.stop_reason === 'evidence_insufficient') return text('现有证据不足以支持完整结论。打开原始会话或调查查看需要补充的证据。', 'The available evidence is insufficient for a complete conclusion. Open the original conversation or investigation to review the missing evidence.')
  if (task.result_available && ['completed', 'succeeded'].includes(task.status)) return text('本轮结果已保存，可打开原始会话或调查查看。', 'The result is saved. Open the original conversation or investigation to read it.')
  if (task.status === 'waiting_input') return text('需要补充信息。打开原始会话或调查查看缺口。', 'More input is needed. Open the original conversation or investigation to review the gap.')
  if (task.status === 'waiting_dependency') return text('正在等待证据或关联任务的结果。', 'Waiting for evidence or a related task result.')
  if (task.stop_reason) return investigationStopMessage(task.stop_reason, text)
  return taskOutcome(task, text)
}

export type TaskAttentionGroup = { key: string; task: AgentTaskSummary; count: number; kind: 'failure' | 'waiting' | 'blocked' }

/** Only real lineage joins a family; a shared role or similar title is not a link. */
export function taskAttentionGroups(tasks: AgentTaskSummary[], asOf: string): TaskAttentionGroup[] {
  const parents = new Map(tasks.map(task => [task.run_id, task.run_id]))
  const root = (id: string): string => {
    const parent = parents.get(id)
    if (!parent || parent === id) return id
    const result = root(parent)
    parents.set(id, result)
    return result
  }
  for (const task of tasks) {
    for (const ref of [task.parent_run_id, task.predecessor_run_id]) {
      if (ref && parents.has(ref)) parents.set(root(task.run_id), root(ref))
    }
  }
  const cutoff = Date.parse(asOf) - 24 * 60 * 60 * 1000
  const groups = new Map<string, TaskAttentionGroup>()
  for (const task of tasks) {
    const failed = ['failed', 'timed_out'].includes(task.status)
    const waiting = ['waiting_input', 'waiting_dependency'].includes(task.status)
    if (!failed && !waiting && task.status !== 'blocked') continue
    if (!failed && task.stop_reason === 'no_eligible_enrichment_operator') continue
    if (!waiting && Date.parse(task.updated_at) < cutoff) continue
    const kind = failed ? 'failure' : waiting ? 'waiting' : 'blocked'
    const key = `${task.case_id || root(task.run_id)}:${kind}:${task.stop_reason || task.status}`
    const current = groups.get(key)
    if (current) {
      current.count += 1
      if (task.updated_at > current.task.updated_at) current.task = task
    } else groups.set(key, { key, task, count: 1, kind })
  }
  return [...groups.values()].sort((a, b) => b.task.updated_at.localeCompare(a.task.updated_at))
}
