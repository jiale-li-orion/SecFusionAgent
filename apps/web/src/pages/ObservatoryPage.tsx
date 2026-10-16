import { DevelopingField } from '../components/ui/developing-field'
import { ObservatoryPulse } from '../components/observatory/ObservatoryPulse'
import { Button } from '../components/ui/button'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, TriangleAlert } from '../components/ui/icons'
import { getAgentRuntime, getSystemOverview, getWorldOverview } from '../lib/api'
import { LiveObservatory } from '../components/observatory/ObservatoryLive'
import { observatoryWindows, type ObservatoryWindow } from '../lib/observatoryPresentation'
import { useI18n } from '../lib/i18n'
import { useAuth } from '../lib/auth'

export function ObservatoryPage() {
  const auth = useAuth()
  const { text } = useI18n()
  const [windowKey, setWindowKey] = useState<ObservatoryWindow>('24h')
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, staleTime: 15_000, refetchInterval: 30_000 })
  const agentsQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, enabled: auth.authenticated, staleTime: 10_000, refetchInterval: 15_000 })
  const systemQuery = useQuery({ queryKey: ['observatory-system'], queryFn: getSystemOverview, refetchInterval: 15_000 })
  const refresh = () => void Promise.all([worldQuery.refetch(), ...(auth.authenticated ? [agentsQuery.refetch()] : []), systemQuery.refetch()])
  const fetching = worldQuery.isFetching || agentsQuery.isFetching || systemQuery.isFetching
  return (
    <section className="observatory-space studio-observatory observatory-page observatory-live" data-develop-scope>
      <header className="observatory-page-header development-heading"><DevelopingField variant="observatory" className="heading-imprint"/><div><h1>{text('数据与服务', 'Data & services')}</h1><p>{text('来源健康、数据变化与服务运行状态。', 'Source health, data activity, and service status.')}</p></div>
        <div className="observatory-page-actions"><div className="window-switch" aria-label={text('观测时间范围', 'Observation window')}>{observatoryWindows.map(item => <button key={item} className={windowKey === item ? 'active' : ''} aria-pressed={windowKey === item} onClick={() => setWindowKey(item)}>{item === '168h' ? '7d' : item}</button>)}</div><Button variant="outline" disabled={fetching} onClick={refresh}><RefreshCw size={15}/>{fetching ? text('更新中', 'Updating') : text('刷新', 'Refresh')}</Button></div>
      </header>
      <div className="observatory-live observatory-live-stage">
        {(worldQuery.isError || agentsQuery.isError || systemQuery.isError) && (
          <div className="observatory-live-fault" role="alert">
            <TriangleAlert size={14} />
            <div><small>{text('状态读取异常', 'STATUS READ ERROR')}</small><strong>{worldQuery.isError ? text('采集快照读取失败', 'Collection snapshot read failed') : agentsQuery.isError ? text('任务运行状态读取失败', 'Task runtime read failed') : text('服务状态读取失败', 'Service status read failed')}</strong></div>
            <button onClick={refresh}>{text('重新读取', 'RETRY')}</button>
          </div>
        )}
        <ObservatoryPulse world={worldQuery.data ?? null} windowKey={windowKey} failed={worldQuery.isError} />
        <LiveObservatory world={worldQuery.data ?? null} agents={agentsQuery.data ?? null} system={systemQuery.data ?? null} failures={{ world: worldQuery.isError, agents: agentsQuery.isError, system: systemQuery.isError }} windowKey={windowKey} />
      </div>
    </section>
  )
}
