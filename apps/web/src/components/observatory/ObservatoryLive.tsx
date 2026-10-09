import { useMemo, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { useNavigate } from 'react-router-dom'
import { Binary, Boxes, BrainCircuit, CircleGauge, Clock3, DatabaseZap, Eye, Fingerprint, RadioTower, ScanLine, ServerCog, ShieldCheck, Sparkles, Waypoints } from 'lucide-react'

import { getAgentRuntime, type SystemOverview, type WorldOverview } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import { useAuth } from '../../lib/auth'
import { AccountLoginPrompt } from '../auth/RequireAccount'
import { bytes, compactNumber, linePath, observatoryWindows, pct, seconds, snapshotAge, type ObservatoryWindow } from '../../lib/observatoryPresentation'
import { dominantRuntimeName, rankRuntimeCounts, runtimeToken } from '../../lib/runtimePresentation'
import { PanelHead } from './ObservatoryPrimitives'
import { WorkerHealth } from './WorkerHealth'

function AgentLiveInstrument({ runtime }: { runtime: Awaited<ReturnType<typeof getAgentRuntime>> }) {
  const { text } = useI18n()
  const model = runtime.model_runtime
  const control = runtime.control_runtime
  const topProvider = dominantRuntimeName(model.provider_counts)
  const topModel = dominantRuntimeName(model.model_counts)
  const stopReasons = rankRuntimeCounts(control.stop_reason_counts, 4)
  return (
    <div className="agent-live-instrument">
      <div className="agent-live-instrument-head">
        <div><small>MODEL / CONTROL RUNTIME</small><strong>{text('最近持久执行样本', 'RECENT PERSISTED SAMPLE')}</strong></div>
        <span>{model.scope.replaceAll('_', ' ')}</span>
      </div>
      <div className="agent-live-signal">
        <div><small>REQUEST</small><strong>{model.request_count}</strong><span>{model.attempt_count} attempts</span></div>
        <div><small>RETRY</small><strong>{model.retry_attempt_count}</strong><span>{model.retry_scheduled_count} scheduled</span></div>
        <div><small>FAIL</small><strong>{model.failed_attempt_count}</strong><span>{model.unknown_after_dispatch_count} unknown</span></div>
        <div><small>MODEL P95</small><strong>{model.p95_latency_ms == null ? '—' : `${model.p95_latency_ms}ms`}</strong><span>{topProvider ?? 'provider not recorded'}</span></div>
      </div>
      <div className="agent-live-coordinate">
        <div><BrainCircuit size={12} /><span>{topModel ?? text('没有持久 ModelAttempt', 'no persisted ModelAttempt')}</span></div>
        <div><Waypoints size={12} /><span>{control.dependency_wake_count} wakes · {control.waiting_event_count} waits</span></div>
        <div><Clock3 size={12} /><span>{text('WAKE LATENCY 未测量', 'WAKE LATENCY UNMEASURED')}</span></div>
      </div>
      <div className="agent-stop-reasons">
        <small>RECENT STOP REASONS</small>
        <div>
          {stopReasons.length
            ? stopReasons.map(([reason, count]) => <span key={reason}><b>{count}</b>{runtimeToken(reason)}</span>)
            : <span>{text('当前读取窗口没有 stop reason', 'no stop reason in current read window')}</span>}
        </div>
      </div>
    </div>
  )
}

export function LiveObservatory({ world, agents, system, failures, windowKey, setWindowKey }: { world: WorldOverview | null; agents: Awaited<ReturnType<typeof getAgentRuntime>> | null; system: SystemOverview | null; failures: { world: boolean; agents: boolean; system: boolean }; windowKey: ObservatoryWindow; setWindowKey: (value: ObservatoryWindow) => void }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const { authenticated } = useAuth()
  const [focus, setFocus] = useState<'world' | 'sources' | 'agents' | 'system' | null>('sources')
  const current = world?.windows[windowKey]
  const hours = windowKey === '1h' ? 1 : windowKey === '6h' ? 6 : windowKey === '24h' ? 24 : 168
  const series = useMemo(() => (world?.hourly_series ?? []).slice(-hours), [world?.hourly_series, hours])
  const agentSummary = agents ? text(`当前账户与公共任务中有 ${agents.roles.reduce((sum, role) => sum + role.active_tasks, 0)} 个活动任务、${agents.roles.reduce((sum, role) => sum + role.total_tasks, 0)} 次持久执行。`, `Your account and public tasks include ${agents.roles.reduce((sum, role) => sum + role.active_tasks, 0)} active tasks and ${agents.roles.reduce((sum, role) => sum + role.total_tasks, 0)} retained runs.`) : authenticated ? failures.agents ? text('账户任务读数不可用，可重试。', 'Account task read unavailable; retry.') : text('账户任务状态尚未载入。', 'Account task status is not loaded yet.') : text('登录后可查看与你有关的任务运行状态。', 'Sign in to inspect task activity for your account.')
  const totalSources = world ? world.source_health.healthy + world.source_health.degraded + world.source_health.blocked : 0
  const chooseFocus = (next: 'world' | 'sources' | 'agents' | 'system') => setFocus(next)

  return (
    <>
      <div className="live-command-strip">
        <p>{world && current ? text(
          `这份 ${windowKey === '168h' ? '7 天' : windowKey} 运行窗口覆盖 ${totalSources} 个来源，其中 ${world.source_health.healthy} 个健康。窗口内出现 ${compactNumber(current.fresh_external_changes)} 次外部新变化；采集队列 p95 为 ${seconds(current.queue_delay_p95_seconds)}，执行 p95 为 ${seconds(current.execution_p95_seconds)}，计划采集成功率为 ${current.scheduled_run_success_rate == null ? '未测量' : pct(current.scheduled_run_success_rate)}。${agentSummary}`,
          `This ${windowKey === '168h' ? '7-day' : windowKey} operational window covers ${totalSources} sources, with ${world.source_health.healthy} healthy. It contains ${compactNumber(current.fresh_external_changes)} fresh external changes; acquisition queue p95 is ${seconds(current.queue_delay_p95_seconds)}, execution p95 is ${seconds(current.execution_p95_seconds)}, and scheduled-run success is ${current.scheduled_run_success_rate == null ? 'not measured' : pct(current.scheduled_run_success_rate)}. ${agentSummary}`,
        ) : failures.world ? text('来源与数据流读数不可用。请重新读取状态。', 'Source and data-plane readings are unavailable. Retry the status read.') : text('正在读取来源、数据流、Agent 与服务状态。', 'Reading source, data-plane, Agent, and service state.')}</p>
        <div className="observatory-focus-tabs" aria-label={text('聚焦运行面', 'Focus operational surface')}>
          <button className={focus === 'sources' ? 'active' : ''} onClick={() => chooseFocus('sources')}>{text('来源', 'SOURCES')}</button>
          <button className={focus === 'world' ? 'active' : ''} onClick={() => chooseFocus('world')}>{text('数据流', 'DATA PLANE')}</button>
          <button className={focus === 'agents' ? 'active' : ''} onClick={() => chooseFocus('agents')}>{text('智能体', 'AGENTS')}</button>
          <button className={focus === 'system' ? 'active' : ''} onClick={() => chooseFocus('system')}>{text('服务', 'SYSTEM')}</button>
        </div>
      </div>

      <div className="live-window-row">
        <div className="live-now"><span className="scan-dot" /><strong>{text('运行快照', 'OPERATIONAL SNAPSHOT')}</strong><span>{world ? snapshotAge(world.generated_at) : failures.world ? text('读数不可用', 'read unavailable') : text('加载中', 'loading')}</span></div>
        <div className="window-switch">{observatoryWindows.map((item) => <button key={item} className={windowKey === item ? 'active' : ''} onClick={() => setWindowKey(item)}>{item === '168h' ? '7d' : item}</button>)}</div>
      </div>

      <div className={`observatory-live-grid ${focus ? `has-observatory-focus focus-${focus}` : ''}`}>
        {focus === 'world' && <section className={`telemetry-panel telemetry-wide ${focus === 'world' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
          <PanelHead eyebrow="DATA PLANE" title={text('世界活动', 'WORLD ACTIVITY')} meta={text(`${series.length} 个小时样本`, `${series.length} hourly samples`)} icon={ScanLine} />
          <div className="telemetry-charts">
            <TelemetryChart title="FRESH / BACKFILL" series={series} failed={failures.world} lines={[{ key: 'fresh_external_changes', label: 'fresh', tone: 'cyan' }, { key: 'backfill_observations', label: 'backfill', tone: 'violet' }]} />
            <TelemetryChart title="CANONICAL WRITES" series={series} failed={failures.world} lines={[{ key: 'canonical_writes', label: 'writes', tone: 'lime' }, { key: 'observations', label: 'observations', tone: 'blue' }]} />
            <TelemetryChart title="QUEUE / EXECUTION" series={series} failed={failures.world} lines={[{ key: 'queue_delay_p95_seconds', label: 'queue p95', tone: 'violet' }, { key: 'execution_p95_seconds', label: 'execution p95', tone: 'amber' }]} />
            <TelemetryChart title="DOCUMENT GROWTH" series={series} failed={failures.world} lines={[{ key: 'document_chunks', label: 'chunks', tone: 'cyan' }]} />
            <TelemetryChart title="FRESH SOURCE BREADTH" series={series} failed={failures.world} lines={[{ key: 'fresh_contributing_sources', label: 'sources', tone: 'lime' }, { key: 'fresh_contributing_categories', label: 'categories', tone: 'violet' }]} />
          </div>
          <div className="world-measurement-ledger">
            <MeasurementFact label="DOCUMENT REVISIONS" value={current ? compactNumber(current.document_revisions) : '—'} />
            <MeasurementFact label="DOCUMENT TEXT" value={current ? bytes(current.document_text_bytes) : '—'} />
            <MeasurementFact label="TOP-1 FRESH SHARE" value={current?.fresh_top1_source_share == null ? '—' : pct(current.fresh_top1_source_share)} />
            <MeasurementFact label="EVIDENCE INTEGRITY" value={current?.evidence_integrity_rate == null ? '—' : pct(current.evidence_integrity_rate)} />
            <MeasurementFact label="EVIDENCE OBJECTS" value={current ? `${current.evidence_artifacts_present}/${current.evidence_artifacts}` : '—'} />
            <MeasurementFact label="EVIDENCE BYTES" value={current ? bytes(current.evidence_physical_bytes) : '—'} />
          </div>
        </section>}

        {focus === 'sources' && <section className={`telemetry-panel source-spectrum ${focus === 'sources' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
          <PanelHead eyebrow="SOURCE CONSTELLATION" title={text('健康频谱', 'HEALTH SPECTRUM')} meta={text('8 类产品来源', '8 product categories')} icon={RadioTower} />
          <div className="spectrum-list">
            {(world?.categories ?? []).map((category) => {
              const total = category.healthy + category.degraded + category.blocked
              return <motion.button type="button" key={category.category} className="spectrum-row spectrum-link" initial={false} animate={{ opacity: 1, x: 0 }} onClick={() => navigate(`/?source=${encodeURIComponent(category.category)}`)}>
                <div className="spectrum-label"><strong>{category.category}</strong><span>{total}</span></div>
                <div className="spectrum-track">
                  <span className="healthy" style={{ width: total ? `${category.healthy / total * 100}%` : '0%' }} />
                  <span className="degraded" style={{ width: total ? `${category.degraded / total * 100}%` : '0%' }} />
                  <span className="blocked" style={{ width: total ? `${category.blocked / total * 100}%` : '0%' }} />
                </div>
                <small>{category.healthy} H · {category.degraded} D · {category.blocked} B</small>
              </motion.button>
            })}
            {!world && (failures.world ? <p className="observatory-read-fault">{text('来源健康读数暂时不可用。', 'Source health readings are unavailable.')}</p> : <SourceSpectrumBlueprint />)}
          </div>
        </section>}

        {focus === 'agents' && !authenticated && <AccountLoginPrompt title={text('查看你的任务运行', 'Inspect your task activity')} description={text('登录后查看任务、模型调用与执行结果。', 'Sign in to inspect your tasks, model calls and execution outcomes.')} />}
        {focus === 'agents' && authenticated && <section className={`telemetry-panel agent-spectrum ${focus === 'agents' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
          <PanelHead eyebrow="AGENT RUNTIME" title={text('ROLE 活动', 'ROLE ACTIVITY')} meta={text('实时 + durable 历史', 'live + durable history')} icon={Sparkles} />
          <div className="agent-spectrum-list">
            {(agents?.roles ?? []).map((role) => {
              const alias = role.role_id === 'DecisionRole' ? 'ORACLE' : role.role_id === 'InvestigationRole' ? 'ARGUS' : 'ALCHEMIST'
              return <button type="button" key={role.role_id} className={`agent-spectrum-row agent-spectrum-link ${role.active_tasks ? 'live' : ''}`} onClick={() => navigate(`/agents?role=${encodeURIComponent(role.role_id)}`)}>
                <div className="agent-spectrum-icon"><CircleGauge size={18} /></div>
                <div><small>{role.role_id}@{role.version}</small><strong>{alias}</strong><span>{role.active_tasks ? text(`${role.active_tasks} 个活动 Task`, `${role.active_tasks} active`) : text('空闲', 'idle')} · {text(`${role.total_tasks} 个 durable runs`, `${role.total_tasks} durable runs`)}</span></div>
                <RoleBars counts={role.status_counts} />
              </button>
            })}
            {!agents && (failures.agents ? <p className="observatory-read-fault">{text('Agent 运行读数暂时不可用。', 'Agent runtime readings are unavailable.')}</p> : <AgentSpectrumBlueprint />)}
          </div>
          <div className="capability-activity-summary"><Binary size={13} /><span>{text('持久化 CapabilityInvocation', 'Persisted CapabilityInvocation')}</span><strong>{agents ? agents.recent_capabilities.length : '—'}</strong></div>
          {agents && <AgentLiveInstrument runtime={agents} />}
        </section>}

        {focus === 'system' && <section
          className={`telemetry-panel system-status-panel ${focus === 'system' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}
        >
          <PanelHead eyebrow="SYSTEM" title={text('管线完整性', 'PIPELINE INTEGRITY')} meta={text('仅显示实测事实', 'measured facts only')} icon={ServerCog} />
          <div className="system-status-grid">
            <SystemFact icon={Boxes} label="OUTBOX DELIVERED" value={world ? compactNumber(world.outbox_delivered) : '—'} />
            <SystemFact icon={Eye} label="LEXICAL READY" value={world ? compactNumber(world.lexical_ready_documents) : '—'} />
            <SystemFact icon={ShieldCheck} label="ARTIFACT STORE" value={world?.artifact_store_status ?? '—'} />
            <SystemFact icon={Fingerprint} label="ARTIFACT INTEGRITY" value={world?.public_epoch_artifact_integrity_rate != null ? pct(world.public_epoch_artifact_integrity_rate) : '—'} />
          </div>
          <div className="system-dependency-mesh">
            {(system?.dependencies ?? []).map((dependency) => (
              <div key={dependency.component} className={`system-dependency status-${dependency.status}`}>
                {dependency.component === 'postgresql' ? <DatabaseZap size={13} /> : <RadioTower size={13} />}
                <div><small>{runtimeToken(dependency.component)}</small><strong>{runtimeToken(dependency.status)}</strong></div>
                <span>{dependency.latency_ms == null ? '—' : `${dependency.latency_ms.toFixed(1)}ms`}</span>
              </div>
            ))}
            {!system && <div className="system-dependency-empty">{failures.system ? text('服务依赖状态不可用。', 'Service dependency status is unavailable.') : text('解析依赖健康…', 'RESOLVING DEPENDENCY HEALTH…')}</div>}
          </div>
          <div className="system-backlog-strip">
            <SystemBacklog label="OUTBOX PENDING" value={system?.outbox.pending_count} oldest={system?.outbox.oldest_pending_at ?? null} />
            <SystemBacklog label="TASK DELIVERY" value={system?.task_event_delivery.pending_count} oldest={system?.task_event_delivery.oldest_pending_at ?? null} />
            <SystemBacklog label="STREAM UNACKED" value={system?.task_event_stream_pending} />
            <SystemBacklog label="RUNTIME POLICY" value={system ? runtimeToken(system.runtime_policy_status) : null} />
          </div>
          <WorkerHealth probe={system?.worker_probe ?? null} />
        </section>}
      </div>
    </>
  )
}

function TelemetryChart({ title, series, lines, failed }: { title: string; series: Array<Record<string, number | string | null>>; lines: Array<{ key: string; label: string; tone: string }>; failed: boolean }) {
  const { text } = useI18n()
  const reduceMotion = Boolean(useReducedMotion())
  const width = 520
  const height = 150
  const sampleValue = (value: number | string | null | undefined) => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value)
  const allValues = lines.flatMap((line) => series.map((item) => sampleValue(item[line.key]))).filter((value): value is number => value != null)
  const max = Math.max(...allValues, 1)
  const paths = lines.map((line) => ({ ...line, d: linePath(series.map((item) => sampleValue(item[line.key])), width, height, max) }))
  const lastSample = series.at(-1)
  const revision = String(lastSample?.hour ?? lastSample?.timestamp ?? lastSample?.generated_at ?? series.length)
  return <div className={`telemetry-chart ${series.length ? '' : 'chart-unresolved'}`}><div className="chart-head"><strong>{title}</strong><div>{lines.map((line) => <span key={line.key} className={`tone-${line.tone}`}><i />{line.label} · {sampleValue(lastSample?.[line.key]) == null ? '—' : line.key.endsWith('_seconds') ? seconds(sampleValue(lastSample?.[line.key])) : compactNumber(sampleValue(lastSample?.[line.key])!)}</span>)}</div></div><div className="chart-canvas"><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><defs><linearGradient id={`fade-${title.replaceAll(' ', '-')}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".16"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((part) => <line key={part} x1="0" x2={width} y1={height * part} y2={height * part} className="chart-gridline" />)}{paths.map((path) => <motion.path key={`${path.key}:${revision}`} className={`chart-line tone-${path.tone}`} d={path.d} fill="none" initial={reduceMotion ? false : { pathLength: 0, opacity: .28 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: reduceMotion ? 0 : .58, ease: [0.22, 1, 0.36, 1] }} />)}{series.length === 1 && lines.map(line => {
      const value = sampleValue(series[0][line.key])
      return value == null ? null : <circle key={line.key} className={`chart-sample tone-${line.tone}`} cx={width / 2} cy={height - Math.min(value / max, 1) * (height - 10) - 5} r="4" />
    })}</svg>{series.length === 0 && <div className="chart-await"><ScanLine size={16}/><strong>{failed ? text('运行样本不可用', 'OPERATIONAL SAMPLES UNAVAILABLE') : text('等待运行样本', 'AWAITING OPERATIONAL SAMPLES')}</strong><small>{failed ? text('可通过顶部按钮重新读取', 'Retry from the status control above') : text('数据到达后显示趋势', 'Trends appear when samples arrive')}</small></div>}<div className="chart-scanline" /></div></div>
}

function SourceSpectrumBlueprint() {
  const { text } = useI18n()
  return (
    <>
      {['vulnerability','development','academic','vendor','independent','normative','assets','incidents'].map((label) => (
        <div key={label} className="spectrum-row spectrum-blueprint">
          <div className="spectrum-label"><strong>{label}</strong><span>—</span></div>
          <div className="spectrum-track"><i /></div>
          <small>{text('未解析', 'UNRESOLVED')}</small>
        </div>
      ))}
    </>
  )
}

function AgentSpectrumBlueprint() {
  const { text } = useI18n()
  return (
    <>
      {[
        ['DecisionRole@1','ORACLE','DIRECT / RETRIEVE'],
        ['InvestigationRole@1','ARGUS','VERIFY / INVESTIGATE / WATCH'],
        ['EnrichmentRole@1','ALCHEMIST','ENRICHMENT'],
      ].map(([role, alias, profile]) => (
        <div key={role} className="agent-spectrum-row agent-spectrum-blueprint">
          <div className="agent-spectrum-icon"><CircleGauge size={18} /></div>
          <div><small>{role}</small><strong>{alias}</strong><span>{profile}</span></div>
          <div className="agent-spectrum-offline">{text('运行数据尚未载入', 'Runtime data not loaded')}</div>
        </div>
      ))}
    </>
  )
}


function SystemFact({ icon: Icon, label, value }: { icon: typeof Boxes; label: string; value: string }) { return <div className="system-fact"><Icon size={16} /><small>{label}</small><strong>{value}</strong></div> }

function MeasurementFact({ label, value }: { label: string; value: string }) { return <div><small>{label}</small><strong>{value}</strong></div> }

function SystemBacklog({ label, value, oldest = null }: { label: string; value: number | string | null | undefined; oldest?: string | null }) { return <div><small>{label}</small><strong>{value == null ? '—' : typeof value === 'number' ? compactNumber(value) : value}</strong>{oldest && <span>{snapshotAge(oldest)}</span>}</div> }

function RoleBars({ counts }: { counts: Record<string, number> }) { const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1; return <div className="role-bars"><span className="done" style={{ width: `${((counts.completed ?? 0) / total) * 100}%` }} /><span className="live" style={{ width: `${(((counts.running ?? 0) + (counts.queued ?? 0)) / total) * 100}%` }} /><span className="fail" style={{ width: `${(((counts.failed ?? 0) + (counts.blocked ?? 0)) / total) * 100}%` }} /></div> }
