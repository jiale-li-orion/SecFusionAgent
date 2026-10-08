import type { SystemWorkerProbe } from '../../lib/api/system'
import { useI18n } from '../../lib/i18n'

const queueLabels: Record<string, [string, string]> = {
  collection: ['采集', 'Collection'], enrichment: ['情报补全', 'Enrichment'],
  investigation: ['调查', 'Investigation'], indexing: ['索引', 'Indexing'],
}

export function WorkerHealth({ probe }: { probe: SystemWorkerProbe | null }) {
  const { text } = useI18n()
  const available = probe?.queues.filter(queue => queue.availability === 'available').length ?? 0
  return <div className={`system-worker-health status-${probe?.status ?? 'loading'}`}>
    <header><strong>{text('执行进程', 'Execution workers')}</strong><span>{probe ? text(`${available}/${probe.queues.length} 条执行管线已观察到消费者`, `${available}/${probe.queues.length} execution queues have observed consumers`) : text('正在检测进程响应…', 'Checking worker responses…')}</span></header>
    {probe && <>
      <div className="worker-queue-status">{probe.queues.map(queue => {
        const label = queueLabels[queue.queue_name] ?? [queue.queue_name, queue.queue_name]
        return <div key={queue.queue_name} className={`availability-${queue.availability}`}><i /><span>{text(...label)}</span><small>{queue.availability === 'available' ? text('可接收任务', 'Accepting tasks') : queue.availability === 'unobserved' ? text('未观察到消费者', 'No consumer observed') : text('状态未读取', 'Status unavailable')}</small></div>
      })}</div>
      {probe.status === 'unavailable' && <p>{text('暂未获取工作进程响应，可以刷新状态重新检测。', 'Worker responses are unavailable. Refresh the status to check again.')}</p>}
      <details><summary>{text('检测详情', 'Probe details')} · {new Date(probe.checked_at).toLocaleTimeString()}</summary>
        <p>{text('根据本次控制请求的实际响应记录进程和队列状态。', 'Worker and queue states come from the actual responses to this control request.')}</p>
        {probe.workers.map(worker => <div key={worker.name}><code>{worker.name}</code><span>{worker.queue_names.join(' · ')}</span><small>{worker.ping_responded ? text('响应正常', 'Ping responded') : text('未收到 Ping 响应', 'Ping response not received')}</small></div>)}
        {probe.failure_code && <code>{probe.failure_code}</code>}
      </details>
    </>}
  </div>
}
