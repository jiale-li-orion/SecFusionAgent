import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAgentTask, getInvestigationActivity } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

export function AlchemistBoundary({ caseId, active = true }: { caseId: string | null; active?: boolean }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const activityQuery = useQuery({
    queryKey: ['start-case-activity', caseId],
    queryFn: () => getInvestigationActivity(caseId!),
    enabled: Boolean(caseId),
    refetchInterval: caseId && active ? 4_000 : false,
  })
  const enrichmentEvent = useMemo(() => (
    [...(activityQuery.data?.events ?? [])]
      .reverse()
      .find((event) => event.role_id === 'EnrichmentRole' && event.task_run_id)
  ), [activityQuery.data?.events])
  const enrichmentRunId = enrichmentEvent?.task_run_id ?? null
  const taskQuery = useQuery({
    queryKey: ['start-enrichment-task', enrichmentRunId],
    queryFn: () => getAgentTask(enrichmentRunId!),
    enabled: Boolean(enrichmentRunId),
    refetchInterval: (query) => enrichmentRunId && active && !['completed', 'blocked', 'failed', 'cancelled', 'timed_out', 'superseded'].includes(query.state.data?.task.status ?? '') ? 5_000 : false,
  })
  const task = taskQuery.data?.task ?? null
  const parent = taskQuery.data?.parent ?? null
  const delegatedChild = Boolean(task?.parent_run_id && parent)
  const status = task?.status ?? enrichmentEvent?.status ?? null

  if (!caseId) return null

  return (
    <div className={`alchemist-boundary ${enrichmentRunId ? 'runtime-active' : 'runtime-dormant'} ${delegatedChild ? 'delegated-child' : ''}`}>
      <span>ALCHEMIST</span>
      {!caseId ? (
        <small>{text('真实 Enrichment 子任务创建后，ALCHEMIST 进入运行链。', 'ALCHEMIST enters the runtime when a real Enrichment child task is created.')}</small>
      ) : activityQuery.isError ? (
        <small>{text('暂时无法读取调查中的情报补全状态。', 'Intelligence enrichment status is temporarily unavailable.')}</small>
      ) : activityQuery.isLoading ? (
        <small>{text('正在读取调查中的情报补全任务…', 'Loading enrichment tasks for this investigation…')}</small>
      ) : !enrichmentRunId ? (
        <small>{text('本次调查暂未调用情报补全。', 'This investigation has not requested intelligence enrichment.')}</small>
      ) : (
        <button
          type="button"
          className="alchemist-runtime-link"
          onClick={() => navigate(`/agents?${new URLSearchParams({ run: enrichmentRunId, from: 'start', caseRef: caseId }).toString()}`)}
        >
          <small>{delegatedChild ? text('已确认委派子任务', 'DELEGATED CHILD CONFIRMED') : text('已观察到 Enrichment Task', 'ENRICHMENT TASK OBSERVED')}</small>
          <strong>{status ?? text('状态未解析', 'status unresolved')}</strong>
          <em className="mono">{enrichmentRunId}</em>
          {task?.parent_run_id && <b className="mono">PARENT {parent?.run_id ?? task.parent_run_id}</b>}
        </button>
      )}
    </div>
  )
}
