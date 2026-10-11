import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowRight, ArrowUpRight, CheckCircle2, CircleAlert, Database, Network, RefreshCw, Workflow } from '../ui/icons'
import { Link } from 'react-router-dom'
import { getAgentRuntime } from '../../lib/api/agents'
import { getSystemOverview } from '../../lib/api/system'
import { useI18n } from '../../lib/i18n'
import { investigationStopMessage } from '../../lib/investigationPresentation'

export function OperationsOverview() {
  const { text } = useI18n()
  const runtime = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 30_000 })
  const system = useQuery({ queryKey: ['observatory-system'], queryFn: getSystemOverview, refetchInterval: 30_000 })
  const active = runtime.data?.roles.reduce((sum, role) => sum + role.active_tasks, 0)
  const failedTasks = runtime.data?.recent_tasks.filter((task) => ['failed', 'blocked', 'timed_out'].includes(task.status)) ?? []
  const issues =
    system.data?.dependencies.filter((item) => item.status !== 'healthy' && item.status !== 'ready' && item.status !== 'ok') ?? []
  const healthy = system.data?.overall === 'healthy' || system.data?.overall === 'ready' || system.data?.overall === 'ok'
  const components: Record<string, [string, string]> = {
    postgresql: ['知识与证据存储', 'Knowledge and evidence storage'],
    redis_broker: ['任务调度队列', 'Task dispatch queue'],
    redis_hot_cache: ['热区缓存', 'Hot cache'],
    redis_task_bus: ['任务事件通道', 'Task event channel'],
  }
  const roles: Record<string, [string, string]> = {
    DecisionRole: ['研判', 'Reasoning'],
    InvestigationRole: ['调查', 'Investigation'],
    EnrichmentRole: ['富化', 'Enrichment'],
  }
  return (
    <div className="operations-overview">
      <header className="workspace-heading">
        <div>
          <h1>{text('运行工作台', 'Operations')}</h1>
          <p>{text('任务进展、智能体协作与服务状态。', 'Tasks, agent collaboration, and service health.')}</p>
        </div>
        <Button
          variant="outline"
          disabled={runtime.isFetching || system.isFetching}
          onClick={() => void Promise.all([runtime.refetch(), system.refetch()])}
        >
          <RefreshCw size={16} />
          {text('刷新', 'Refresh')}
        </Button>
      </header>
      {(runtime.isError || system.isError) && (
        <p className="error-block" role="alert">
          {text('部分运行状态暂时不可用，可以刷新重试。', 'Some operational data is unavailable. Refresh to retry.')}
        </p>
      )}
      <div className="operations-metrics">
        <Link to="/observatory">
          <Card>
            <CardContent>
              <span>
                <Activity size={17} />
                {text('系统状态', 'System state')}
              </span>
              <strong className={healthy && !system.isError ? 'metric-healthy' : 'metric-warning'}>
                {system.isError
                  ? text('读取失败', 'Read failed')
                  : system.data
                    ? healthy
                      ? text('运行正常', 'Healthy')
                      : text('需要关注', 'Needs attention')
                    : '—'}
              </strong>
              <small>
                {text('数据、服务与队列', 'Data, services and queues')}
                <ArrowUpRight size={14} />
              </small>
            </CardContent>
          </Card>
        </Link>
        <Link to="/agents">
          <Card>
            <CardContent>
              <span>
                <Workflow size={17} />
                {text('正在执行', 'Active tasks')}
              </span>
              <strong>{runtime.isError ? '—' : (active ?? '—')}</strong>
              <small>
                {text('当前账户可见任务', 'Tasks visible to your account')}
                <ArrowUpRight size={14} />
              </small>
            </CardContent>
          </Card>
        </Link>
        <Link to="/agents">
          <Card>
            <CardContent>
              <span>
                <Network size={17} />
                {text('协作角色', 'Agent roles')}
              </span>
              <strong>{runtime.isError ? '—' : (runtime.data?.roles.length ?? '—')}</strong>
              <small>
                {text('研判、调查与富化', 'Reasoning, investigation, enrichment')}
                <ArrowUpRight size={14} />
              </small>
            </CardContent>
          </Card>
        </Link>
        <Link to="/observatory">
          <Card>
            <CardContent>
              <span>
                <Database size={17} />
                {text('待分发事件', 'Pending events')}
              </span>
              <strong>
                {system.data && !system.isError ? system.data.outbox.pending_count + system.data.task_event_delivery.pending_count : '—'}
              </strong>
              <small>
                {text('持久事件队列', 'Durable event delivery')}
                <ArrowUpRight size={14} />
              </small>
            </CardContent>
          </Card>
        </Link>
      </div>
      <div className="operations-columns">
        <Card>
          <CardContent>
            <header className="workspace-card-heading">
              <div>
                <h2>{text('智能体协作', 'Agent collaboration')}</h2>
              </div>
              <Link to="/agents">
                {text('查看任务', 'View tasks')}
                <ArrowUpRight size={14} />
              </Link>
            </header>
            <div className="operations-role-list">
              {runtime.data?.roles.map((role) => (
                <Link to={`/agents?role=${encodeURIComponent(role.role_id)}`} key={role.role_id}>
                  <span className={`operations-role-icon role-${role.role_id}`}>
                    <Network size={22} />
                  </span>
                  <div>
                    <strong>{roles[role.role_id] ? text(...roles[role.role_id]) : role.role_id}</strong>
                    <small>
                      {role.active_tasks} {text('个执行中', 'active')} · {role.total_tasks} {text('次累计运行', 'runs')}
                    </small>
                  </div>
                  <ArrowRight size={16} />
                </Link>
              ))}
            </div>
            {runtime.isPending && (
              <p className="empty-block" role="status">
                {text('正在读取协作状态…', 'Loading agent state…')}
              </p>
            )}
            <Link className="operations-memory" to="/agents?section=memory">
              {text('探索技能与经验库', 'Explore skills and experience')}
              <ArrowRight size={16} />
            </Link>
          </CardContent>
        </Card>
        <Card className="operations-attention">
          <CardContent>
            <header className="workspace-card-heading">
              <div>
                <h2>{text('需要关注', 'Needs attention')}</h2>
              </div>
              <CircleAlert size={18} />
            </header>
            {(system.isPending || runtime.isPending) && !system.data && !runtime.data ? (
              <p className="empty-block">{text('正在读取…', 'Loading…')}</p>
            ) : system.isError || runtime.isError ? (
              <p className="empty-block" role="status">
                {text('部分状态读取失败，暂时无法判断是否有新的异常。', 'Some readings failed. New issues cannot be assessed yet.')}
              </p>
            ) : !issues.length && !failedTasks.length && healthy ? (
              <div className="workspace-empty">
                <CheckCircle2 size={26} />
                <div>
                  <strong>{text('当前读数没有发现异常', 'No issues in the current readings')}</strong>
                  <p>{text('任务和服务状态会持续更新。', 'Task and service states update regularly.')}</p>
                </div>
              </div>
            ) : (
              <div className="operations-attention-list">
                {!issues.length && !failedTasks.length && !healthy && (
                  <Link to="/observatory">
                    <span className="workspace-status status-waiting" />
                    <div>
                      <strong>{text('系统状态需要进一步检查', 'Review the system status')}</strong>
                      <small>{system.data?.overall ?? text('部分状态不可用', 'Some readings are unavailable')}</small>
                    </div>
                    <ArrowUpRight size={14} />
                  </Link>
                )}
                {issues.slice(0, 3).map((item) => (
                  <Link key={item.component} to="/observatory">
                    <span className="workspace-status status-waiting" />
                    <div>
                      <strong>{components[item.component] ? text(...components[item.component]) : item.component}</strong>
                      <small>
                        {item.status === 'degraded' ? text('运行降级，查看服务详情', 'Degraded; review service details') : text('连接异常，查看服务详情', 'Connection issue; review service details')}
                      </small>
                    </div>
                    <ArrowUpRight size={14} />
                  </Link>
                ))}
                {failedTasks.slice(0, 3).map((item) => (
                  <Link key={item.run_id} to={`/agents?run=${encodeURIComponent(item.run_id)}`}>
                    <span className="workspace-status status-failed" />
                    <div>
                      <strong>
                        {text('任务未完成', 'Task stopped')} · {roles[item.role_id] ? text(...roles[item.role_id]) : item.role_id}
                      </strong>
                      <small>{investigationStopMessage(item.stop_reason ?? '', text)}</small>
                    </div>
                    <ArrowUpRight size={14} />
                  </Link>
                ))}
              </div>
            )}
            <p className="operations-scope">
              {text('显示当前可见的近期任务与最新服务读数。', 'Recent visible tasks and latest service readings.')}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
