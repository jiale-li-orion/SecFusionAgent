import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, RefreshCw, TriangleAlert } from 'lucide-react'
import { getAgentRuntime, getSystemOverview, getWorldOverview } from '../lib/api'
import { LiveObservatory } from '../components/observatory/ObservatoryLive'
import type { ObservatoryWindow } from '../lib/observatoryPresentation'
import { useI18n } from '../lib/i18n'

export function ObservatoryPage() {
  const { text } = useI18n()
  const [windowKey, setWindowKey] = useState<ObservatoryWindow>('24h')
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 15_000, refetchInterval: 30_000 })
  const agentsQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, staleTime: 10_000, refetchInterval: 15_000 })
  const systemQuery = useQuery({ queryKey: ['observatory-system'], queryFn: getSystemOverview, refetchInterval: 15_000 })
  const refresh = () => void Promise.all([worldQuery.refetch(), agentsQuery.refetch(), systemQuery.refetch()])
  const fetching = worldQuery.isFetching || agentsQuery.isFetching || systemQuery.isFetching
  return (
    <section className="observatory-space observatory-page observatory-live">
      <header className="observatory-switchboard-heading observatory-heading">
        <div>
          <p>{text('掌握采集、研判与服务的当前状态', 'FOLLOW COLLECTION, REASONING AND SERVICE HEALTH')}</p>
          <h1>{text('运行', 'LIVE')} <span>{text('观测', 'OBSERVATORY')}</span></h1>
          <small>{text('查看来源健康、数据变化、任务执行与服务状态。读数持续更新，时间窗口可切换。', 'Track source health, data changes, task execution and service status across live measurement windows.')}</small>
        </div>
        <button className="observatory-refresh" disabled={fetching} onClick={refresh}><RefreshCw size={15} /><span>{fetching ? text('更新中', 'UPDATING') : text('刷新状态', 'REFRESH')}</span><Activity size={14} /></button>
      </header>
      <div className="observatory-live observatory-live-stage">
        {(worldQuery.isError || agentsQuery.isError || systemQuery.isError) && (
          <div className="observatory-live-fault" role="alert">
            <TriangleAlert size={14} />
            <div><small>{text('状态读取异常', 'STATUS READ ERROR')}</small><strong>{worldQuery.isError ? text('采集快照读取失败', 'Collection snapshot read failed') : agentsQuery.isError ? text('任务运行状态读取失败', 'Task runtime read failed') : text('服务状态读取失败', 'Service status read failed')}</strong></div>
            <button onClick={refresh}>{text('重新读取', 'RETRY')}</button>
          </div>
        )}
        <LiveObservatory world={worldQuery.data ?? null} agents={agentsQuery.data ?? null} system={systemQuery.data ?? null} windowKey={windowKey} setWindowKey={setWindowKey} />
      </div>
    </section>
  )
}
