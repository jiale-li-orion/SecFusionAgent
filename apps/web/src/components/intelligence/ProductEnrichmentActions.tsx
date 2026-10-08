import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { getAgentTask } from '../../lib/api/agents'
import { listProductEnrichmentRuns, startProductEnrichment } from '../../lib/api/enrichment'
import type { IntelligenceEnrichmentState } from '../../lib/api/intelligence'
import { useI18n } from '../../lib/i18n'

const dimensionLabels: Record<string, [string, string]> = {
  identity: ['漏洞身份', 'Identity'], severity: ['严重性', 'Severity'],
  weakness: ['漏洞类型', 'Weakness'], product_package: ['产品与软件包', 'Product / package'],
  version_applicability: ['版本适用性', 'Version applicability'],
  fix_remediation: ['修复与缓解', 'Fix / remediation'], exploit_state: ['公开利用证据', 'Exploit state'],
  exploit_likelihood: ['利用可能性', 'Exploit likelihood'],
  advisory_reference: ['公告与参考资料', 'Advisory / reference'],
  asset_exposure: ['资产暴露', 'Asset exposure'], research_paper: ['相关研究', 'Research / paper'],
  incident_context: ['事件背景', 'Incident context'],
}
const terminalStatuses = new Set(['completed', 'blocked', 'failed', 'cancelled', 'timed_out', 'superseded'])

type Props = {
  objectId: string
  cveId: string
  state: IntelligenceEnrichmentState | null
  onChanged: () => void | Promise<void>
}

export function ProductEnrichmentActions(props: Props) {
  // The key isolates transient selection and request retry state when the dossier changes.
  return <EnrichmentActions key={props.objectId} {...props} />
}

function EnrichmentActions({ objectId, cveId, state, onChanged }: Props) {
  const { text } = useI18n()
  const queryClient = useQueryClient()
  const [selection, setSelection] = useState<string[] | null>(null)
  const refreshedRun = useRef<string | null>(null)
  const retryRequest = useRef<{ signature: string; key: string } | null>(null)
  const candidates = state?.dimensions.filter((item) => item.status !== 'resolved') ?? []
  const selected = selection
    ? selection.filter((key) => candidates.some((item) => item.dimension === key))
    : candidates.filter((item) => item.status !== 'unknown').map((item) => item.dimension)
  const runs = useQuery({
    queryKey: ['product-enrichment-runs', objectId],
    queryFn: () => listProductEnrichmentRuns(objectId),
    retry: false,
  })
  const submit = useMutation({
    mutationFn: ({ dimensions, key }: { dimensions: string[]; key: string }) => startProductEnrichment(
      objectId, { dimensions, expected_world_revision: state?.world_revision }, key,
    ),
    onSuccess: (run) => {
      retryRequest.current = null
      queryClient.setQueryData(['product-enrichment-runs', objectId], { items: [run] })
    },
  })
  const latest = runs.data?.items[0] ?? null
  const taskQuery = useQuery({
    queryKey: ['product-enrichment-task', latest?.task_run_id],
    queryFn: () => getAgentTask(latest!.task_run_id),
    enabled: Boolean(latest),
    retry: false,
    refetchInterval: (query) => terminalStatuses.has(query.state.data?.task.status ?? '') ? false : 2_000,
  })
  const task = taskQuery.data?.task
  const status = task?.status ?? latest?.status
  const active = Boolean(status && !terminalStatuses.has(status))
  const reason = task?.stop_reason ?? latest?.stop_reason

  useEffect(() => {
    if (!task || !terminalStatuses.has(task.status) || refreshedRun.current === task.run_id) return
    refreshedRun.current = task.run_id
    void onChanged()
  }, [task, onChanged])

  function requestEnrichment() {
    const dimensions = [...selected].sort()
    const signature = JSON.stringify({ objectId, dimensions, revision: state?.world_revision })
    if (retryRequest.current?.signature !== signature) {
      retryRequest.current = { signature, key: crypto.randomUUID() }
    }
    submit.mutate({ dimensions, key: retryRequest.current.key })
  }

  const statusLabels: Record<string, [string, string]> = {
    submitted: ['已提交', 'Submitted'], queued: ['等待执行', 'Queued'], running: ['正在补全', 'Enriching'],
    waiting_input: ['等待输入', 'Waiting for input'], waiting_dependency: ['等待依赖', 'Waiting for dependency'],
    completed: ['本次补全已结束', 'Enrichment finished'], blocked: ['补全受阻', 'Enrichment blocked'],
    failed: ['补全失败', 'Enrichment failed'], timed_out: ['补全超时', 'Enrichment timed out'],
    cancelled: ['已取消', 'Cancelled'], superseded: ['已被后续任务替代', 'Superseded'],
  }
  const label = status ? statusLabels[status] : null

  return (
    <section className="product-enrichment-actions" aria-label={text('补全漏洞情报', 'Enrich vulnerability intelligence')}>
      <header>
        <div><small>EnrichmentRole</small><h3>{text('补全漏洞情报', 'Enrich vulnerability intelligence')}</h3></div>
        <p>{text(`为 ${cveId} 选择待补全维度。新增事实保留来源证据，未知与冲突会继续显示。`, `Choose dimensions for ${cveId}. New facts retain their sources; unknowns and conflicts remain visible.`)}</p>
      </header>
      {!state ? <p>{text('等待维度状态加载后可提交。', 'Load the dimension state before submitting.')}</p> : candidates.length === 0
        ? <p>{text('当前十二个维度均已有证据支持。', 'All twelve dimensions currently have supporting evidence.')}</p>
        : <fieldset className="enrichment-action-dimensions" disabled={submit.isPending || active}>
          <legend>{text('需要补充的维度', 'Dimensions to enrich')}</legend>
          {candidates.map((item) => {
            const labels = dimensionLabels[item.dimension] ?? [item.dimension, item.dimension]
            return <label key={item.dimension}>
              <input type="checkbox" checked={selected.includes(item.dimension)} onChange={() => setSelection((current) => {
                const values = current ?? selected
                return values.includes(item.dimension) ? values.filter((key) => key !== item.dimension) : [...values, item.dimension]
              })} />
              <span>{text(...labels)}</span>
              <small>{item.status === 'conflict' ? text('来源冲突', 'Source conflict') : item.status === 'unknown' ? text('已查询，仍未知', 'Queried; still unknown') : text('缺少证据', 'Evidence missing')}</small>
            </label>
          })}
        </fieldset>}
      <p>{text('现有来源与算子只能补充可获得的材料；缺少前置证据或可用来源时，任务会明确报告受阻。', 'Available sources and operators determine what can be retrieved. Missing prerequisites or sources are reported as blocked.')}</p>
      <button type="button" className="instrument-button" disabled={!state || selected.length === 0 || submit.isPending || active || runs.isPending || runs.isError}
        onClick={requestEnrichment}>
        {submit.isPending ? text('正在提交…', 'Submitting…') : active ? text('补全任务正在执行', 'Enrichment task in progress') : text(`补全所选 ${selected.length} 个维度`, `Enrich ${selected.length} selected dimensions`)}
      </button>
      {submit.isError && <p role="alert">{submit.error.message === 'REVISION_CHANGED'
        ? text('情报已更新，请刷新状态后重新选择。', 'Intelligence changed. Refresh the state and select again.')
        : submit.error.message}<button type="button" onClick={() => void onChanged()}>{text('刷新档案', 'Refresh dossier')}</button></p>}
      {runs.isError && <p role="alert">{text('补全任务记录暂时不可读。', 'Enrichment task history is temporarily unavailable.')} <button type="button" onClick={() => void runs.refetch()}>{text('重试读取', 'Retry')}</button></p>}
      {latest && <div className={`enrichment-action-task status-${status}`} aria-live="polite">
        <strong>{label ? text(...label) : status}</strong>
        <span>{latest.required_dimensions.map((key) => text(...(dimensionLabels[key] ?? [key, key]))).join(' · ')}</span>
        {status === 'completed' && <p>{text('已刷新档案；任务结束仍可能保留未知或来源冲突，请查看维度结果。', 'The dossier has refreshed. Finished tasks can retain unknowns or source conflicts; check the dimension results.')}</p>}
        {status === 'blocked' && <p>{text('现有算子或证据无法完成所选维度。已获得的材料保留在档案中。', 'Available operators or evidence could not complete the selected dimensions. Retrieved material remains in the dossier.')}</p>}
        {(status === 'failed' || status === 'timed_out') && <p>{text('任务未完成，请查看任务记录后决定是否重新提交。', 'The task did not finish. Review the task record before submitting again.')}</p>}
        {taskQuery.isError && <p role="alert">{text('任务状态暂时不可读，正在重试。', 'Task status is temporarily unavailable; retrying.')}</p>}
        <Link to={`/agents?${new URLSearchParams({ run: latest.task_run_id }).toString()}`}>{text('查看任务记录', 'View task record')}</Link>
        <details><summary>{text('任务与前置条件', 'Task and prerequisites')}</summary>
          <p>{latest.task_run_id}</p>{reason && <p>{reason}</p>}
          {candidates.filter((item) => latest.required_dimensions.includes(item.dimension)).map((item) => <p key={item.dimension}>
            {text(...(dimensionLabels[item.dimension] ?? [item.dimension, item.dimension]))}: {item.missing_prerequisites.join(' · ') || text('无缺失前置条件', 'No missing prerequisites')}
            {item.blocked_attempt_refs.length > 0 && ` · ${item.blocked_attempt_refs.length} ${text('次受阻尝试', 'blocked attempts')}`}
          </p>)}
        </details>
      </div>}
    </section>
  )
}
