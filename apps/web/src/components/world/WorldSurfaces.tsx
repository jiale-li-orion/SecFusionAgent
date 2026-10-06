import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowUpRight, Flame } from 'lucide-react'

import type { HotBug, WorldOverview } from '../../lib/api'
import { sourceNarrative, sourceState, sources, worldLanePoints } from './worldModel'
import { useI18n } from '../../lib/i18n'

function shortDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function SourceMiniTrend({ series }: { series: Array<Record<string, number | string | null>> }) {
  const { text } = useI18n()
  const values = series.map((item) => Number(item.fresh_external_changes ?? 0))
  const max = Math.max(...values, 1)
  const points = values.map((value, index) => {
    const x = values.length <= 1 ? 0 : index / (values.length - 1) * 100
    const y = 36 - Math.min(value / max, 1) * 30
    return `${x},${y}`
  }).join(' ')
  return (
    <div className="source-mini-trend">
      <div><small>{text('新增贡献', 'FRESH CONTRIBUTION')}</small><span>{series.length ? text(`${series.length} 个小时样本`, `${series.length} hourly samples`) : text('当前类别没有样本', 'no category samples')}</span></div>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" x2="100" y1="36" y2="36" />
        {series.length > 0 && <polyline points={points} />}
      </svg>
    </div>
  )
}

function categorySeriesSummary(series: Array<Record<string, number | string | null>>) {
  const fresh = series.reduce((sum, item) => sum + Number(item.fresh_external_changes ?? 0), 0)
  const runs = series.reduce((sum, item) => sum + Number(item.scheduled_runs ?? 0), 0)
  const average = (key: string) => {
    const values = series.map((item) => item[key]).filter((value): value is number => typeof value === 'number')
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  }
  return {
    fresh,
    runs,
    success: average('scheduled_run_success_rate'),
    providerFailure: average('provider_boundary_failure_rate'),
    runtimeFailure: average('runtime_owned_failure_rate'),
  }
}

const hotSlots = [
  { left: '78%', top: '27%' },
  { left: '78%', top: '39%' },
  { left: '78%', top: '51%' },
  { left: '78%', top: '63%' },
  { left: '78%', top: '75%' },
]

export function WorldIngressFlow({ snapshot, focusedSource, focusedLane, focusedHot, reduceMotion }: { snapshot: WorldOverview | null | undefined; focusedSource: string | null; focusedLane: string | null; focusedHot: boolean; reduceMotion: boolean }) {
  const categoryHealth = new Map((snapshot?.categories ?? []).map((item) => [item.category, item]))
  const laneNames = Object.keys(worldLanePoints)
  return (
    <svg className={`world-ingress-flow ${focusedHot ? 'dimmed' : ''}`} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <g className="world-lane-trunks">
        {laneNames.map((lane) => {
          const point = worldLanePoints[lane]
          const laneActive = sources.some((source) => sourceNarrative[source.key].lane === lane && categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? []).active)
          const selected = focusedLane === lane
          const dimmed = Boolean(focusedLane && !selected)
          return <motion.path key={lane} className={`${laneActive ? 'active' : ''} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`} d={`M ${point.x} ${point.y} C ${point.x + 6} ${point.y}, 45 50, 50 50`} animate={reduceMotion || !laneActive ? undefined : { strokeDashoffset: [0, -18] }} transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }} />
        })}
      </g>
      <g className="world-source-ingress">
        {sources.map((source) => {
          const lane = sourceNarrative[source.key].lane
          const point = worldLanePoints[lane]
          const health = categoryHealth.get(source.key)
          const state = sourceState(health ? { healthy: health.healthy, degraded: health.degraded, blocked: health.blocked } : undefined)
          const activity = categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? [])
          const selected = focusedSource === source.key
          const laneSelected = focusedLane === lane
          const dimmed = Boolean((focusedSource && !selected) || (focusedLane && !laneSelected))
          return (
            <g key={source.key} className={`state-${state} ${activity.active ? 'active' : ''} ${selected || laneSelected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}>
              <motion.path d={`M 20 ${source.y} C 26 ${source.y}, 29 ${point.y}, ${point.x} ${point.y}`} animate={reduceMotion || !activity.active ? undefined : { strokeDashoffset: [0, -14] }} transition={{ duration: activity.fresh > 0 ? 1.15 : 2.1, repeat: Infinity, ease: 'linear' }} />
              <circle cx={point.x} cy={point.y} r={selected || laneSelected ? 1.1 : .65} />
            </g>
          )
        })}
      </g>
    </svg>
  )
}

function categoryActivity(series: Array<Record<string, number | string | null>>) {
  const latest = series.at(-1)
  const fresh = Number(latest?.fresh_external_changes ?? 0)
  const runs = Number(latest?.scheduled_runs ?? 0)
  const observations = Number(latest?.observations ?? 0)
  return { fresh, runs, observations, active: fresh > 0 || runs > 0 || observations > 0 }
}

export function WorldField2D({ freshChanges, backfillObservations, canonicalWrites }: { freshChanges: number; backfillObservations: number; canonicalWrites: number }) {
  const freshRadius = Math.min(31, 20 + Math.log10(freshChanges + 1) * 3.2)
  const backfillRadius = Math.min(38, 27 + Math.log10(backfillObservations + 1) * 2.8)
  const writeEnergy = Math.min(1, Math.log10(canonicalWrites + 1) / 2.5)
  return (
    <div className="world-2d-fallback" aria-hidden="true">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <ellipse className="grid-ring outer" cx="50" cy="50" rx="35" ry="31" />
        <ellipse className="grid-ring middle" cx="50" cy="50" rx="27" ry="24" />
        <ellipse className="grid-ring inner" cx="50" cy="50" rx="18" ry="16" />
        <circle className="backfill-ring" cx="50" cy="50" r={backfillRadius / 2} />
        <circle className="fresh-ring" cx="50" cy="50" r={freshRadius / 2} />
        <polygon className="core-plane outer" points="50,39 58,44 60,53 54,61 45,60 40,53 42,44" />
        <polygon className="core-plane inner" points="50,43 55,46 56,52 52,57 46,56 44,52 45,46" style={{ opacity: .36 + writeEnergy * .44 }} />
        {canonicalWrites > 0 && <circle className="write-ring" cx="50" cy="50" r="13" />}
      </svg>
      <div className="world-2d-readout"><span>{freshChanges} fresh</span><span>{backfillObservations} backfill</span><span>{canonicalWrites} writes</span></div>
    </div>
  )
}

export function WorldLiveFlow({ series, requestedWindow, totalAvailable }: { series: Array<Record<string, number | string | null>>; requestedWindow: '1h' | '6h' | '24h' | '168h'; totalAvailable: number }) {
  const { text } = useI18n()
  return (
    <section className="world-live-flow">
      <div className="world-live-flow-head">
        <div><small>LIVE EVIDENCE FLOW</small><strong>{text('近期运行样本', 'RECENT OPERATIONAL SAMPLES')}</strong></div>
        <span>{text(`${series.length} 个可见样本 · 共 ${totalAvailable} 个 · ${requestedWindow === '168h' ? '7d' : requestedWindow}`, `${series.length} visible · ${totalAvailable} available · ${requestedWindow === '168h' ? '7d' : requestedWindow}`)}</span>
      </div>
      <div className="world-live-flow-track">
        {series.map((item, index) => {
          const fresh = Number(item.fresh_external_changes ?? 0)
          const writes = Number(item.canonical_writes ?? 0)
          const observations = Number(item.observations ?? 0)
          const stamp = String(item.hour ?? item.timestamp ?? item.generated_at ?? '')
          return (
            <div key={stamp + '-' + index} className="world-flow-sample">
              <i style={{ height: Math.max(12, Math.min(58, Math.log10(fresh + 1) * 18)) + 'px' }} />
              <div><small>{stamp ? new Date(stamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'T-' + (series.length - index)}</small><strong>{text(`${fresh} 条新增`, `${fresh} fresh`)}</strong><span>{text(`${writes} 次写入 · ${observations} 条观测`, `${writes} writes · ${observations} obs`)}</span></div>
            </div>
          )
        })}
        {series.length === 0 && <div className="world-flow-empty">{text('等待运行样本', 'AWAITING OPERATIONAL SAMPLES')}</div>}
      </div>
    </section>
  )
}

export function HotCrystal({
  item,
  index,
  selected,
  dimmed,
  reduceMotion,
  onOpen,
}: {
  item: HotBug
  index: number
  selected: boolean
  dimmed: boolean
  reduceMotion: boolean
  onOpen: () => void
}) {
  const { text } = useI18n()
  const slot = hotSlots[index % hotSlots.length]
  const identity = item.cve_id ?? item.external_object_id
  const critical = item.priority_signals.includes('critical_severity')
  const primarySignal = critical ? text('严重等级', 'CRITICAL SEVERITY') : item.priority_signals[0]?.replaceAll('_', ' ').toUpperCase() ?? text('热点', 'HOT')
  const changeBand = item.changed_fields.length >= 8 ? 'major' : item.changed_fields.length >= 3 ? 'material' : item.changed_fields.length > 0 ? 'minor' : 'stable'
  const signalClasses = item.priority_signals.map((value) => `signal-${hotSignalSlug(value)}`).join(' ')

  return (
    <motion.button
      className={`hot-crystal change-${changeBand} ${signalClasses} ${critical ? 'priority-critical' : ''} ${item.active ? 'is-active' : ''} ${item.pinned ? 'is-pinned' : ''} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
      style={slot}
      onClick={onOpen}
      animate={{
        opacity: dimmed ? .18 : 1,
        scale: selected ? 1.11 : dimmed ? .94 : 1,
        y: 0,
      }}
      transition={{ opacity: { duration: .2 }, scale: { duration: .2 }, y: { duration: reduceMotion ? 0 : .2 } }}
    >
      <span className="hot-crystal-cut" />
      <small>{primarySignal}</small>
      <strong>{identity}</strong>
      <em>{item.cvss_score != null ? `CVSS ${item.cvss_score.toFixed(1)} · ${item.cvss_severity ?? ''}` : item.source_id}</em>
      {item.changed_fields.length > 0 && <span className="hot-change-count">Δ {item.changed_fields.length}</span>}
      {item.access_count > 0 && <span className="hot-access-count">{text('读取', 'READ')} {formatHotCount(item.access_count)}</span>}
      {item.pinned && <span className="hot-pin-state">{text('已固定', 'PINNED')}</span>}
      {(item.active || item.pinned) && <span className="hot-orbit" />}
    </motion.button>
  )
}

function hotSignalSlug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function formatHotCount(value: number) { return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : String(Math.round(value)) }

export function SourceLens({
  source,
  health,
  series,
  sourceDetails,
}: {
  source: (typeof sources)[number]
  health: { healthy: number; degraded: number; blocked: number } | undefined
  series: Array<Record<string, number | string | null>>
  sourceDetails: WorldOverview['sources']
}) {
  const { text } = useI18n()
  const [focusedProviderId, setFocusedProviderId] = useState<string | null>(null)
  const narrative = sourceNarrative[source.key]
  const total = health ? health.healthy + health.degraded + health.blocked : 0
  const Icon = source.icon
  const summary = categorySeriesSummary(series.slice(-6))
  const focusedProvider = sourceDetails.find((item) => item.source_id === focusedProviderId) ?? null

  return (
    <div className="lens-stack">
      <div className="lens-index">{text('来源星图', 'SOURCE CONSTELLATION')} / {source.key.toUpperCase()}</div>
      <div className="lens-title"><span><Icon size={18} /></span><div><small>{source.sub}</small><strong>{text(source.labelZh, source.label)}</strong></div></div>
      <p>{text(narrative.summaryZh, narrative.summary)}</p>
      <div className="lens-facts">
        <LensFact label={text('类别路径', 'CATEGORY ROUTE')} value={narrative.lane} />
        <LensFact label={text('世界角色', 'WORLD ROLE')} value={text(narrative.roleZh, narrative.role)} />
        <LensFact label={text('健康度', 'HEALTH')} value={health ? text(`${health.healthy}/${total} 健康`, `${health.healthy}/${total} healthy`) : text('快照不可用', 'snapshot unavailable')} />
        <LensFact label={text('新增 · 6H', 'FRESH · 6H')} value={String(summary.fresh)} />
        <LensFact label={text('运行 · 6H', 'RUNS · 6H')} value={String(summary.runs)} />
        <LensFact label={text('运行成功率', 'RUN SUCCESS')} value={summary.success == null ? '—' : `${(summary.success * 100).toFixed(1)}%`} />
      </div>
      <SourceMiniTrend series={series.slice(-12)} />
      <div className="lens-failure-balance">
        <div><small>{text('Provider 失败', 'PROVIDER FAIL')}</small><strong>{summary.providerFailure == null ? '—' : `${(summary.providerFailure * 100).toFixed(1)}%`}</strong></div>
        <div><small>{text('Runtime 失败', 'RUNTIME FAIL')}</small><strong>{summary.runtimeFailure == null ? '—' : `${(summary.runtimeFailure * 100).toFixed(1)}%`}</strong></div>
      </div>
      <div className="source-provider-list">
        <div className="source-provider-head"><small>{text('PROVIDER / 调度状态', 'PROVIDERS / SCHEDULE STATE')}</small><span>{sourceDetails.length}</span></div>
        {sourceDetails.slice(0, 8).map((item) => (
          <button
            type="button"
            key={item.source_id}
            className={`source-provider-row state-${item.health} ${focusedProviderId === item.source_id ? 'selected' : ''}`}
            onClick={() => setFocusedProviderId((current) => current === item.source_id ? null : item.source_id)}
          >
            <i />
            <div>
              <strong>{item.source_id}</strong>
              <small>{item.latest_scheduled_status ?? text('无调度状态', 'no scheduled status')}</small>
            </div>
            <div className="source-provider-time">
              <span>{item.last_success_at ? text(`最近 ${shortDateTime(item.last_success_at)}`, `last ${shortDateTime(item.last_success_at)}`) : text('暂无成功记录', 'no success recorded')}</span>
              <em>{item.next_due_at ? text(`下次 ${shortDateTime(item.next_due_at)}`, `due ${shortDateTime(item.next_due_at)}`) : text('无下次调度时间', 'no due time')}</em>
            </div>
            {(item.consecutive_failures > 0 || item.latest_error_code || item.overdue || item.backfill_pending) && (
              <div className="source-provider-alert">
                {item.consecutive_failures > 0 && <span>{text(`${item.consecutive_failures} 次失败`, `${item.consecutive_failures} failures`)}</span>}
                {item.latest_error_code && <span>{item.latest_error_code}</span>}
                {item.overdue && <span>{text('已逾期', 'OVERDUE')}</span>}
                {item.backfill_pending && <span>{text('待回填', 'BACKFILL')}</span>}
              </div>
            )}
          </button>
        ))}
        {sourceDetails.length === 0 && <div className="source-provider-empty">{text('当前快照没有 source-level 调度记录。', 'No source-level schedule rows in current snapshot.')}</div>}
      </div>
      <AnimatePresence mode="wait">
        {focusedProvider && (
          <motion.section
            key={focusedProvider.source_id}
            className={`source-provider-focus state-${focusedProvider.health}`}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
          >
            <div className="source-provider-focus-head">
              <div><small>{text('运行来源', 'RUNTIME SOURCE')}</small><strong>{focusedProvider.source_id}</strong></div>
              <span>{focusedProvider.health}</span>
            </div>
            <div className="source-provider-focus-grid">
              <LensFact label={text('最近成功', 'LAST SUCCESS')} value={focusedProvider.last_success_at ? shortDateTime(focusedProvider.last_success_at) : '—'} />
              <LensFact label={text('下次调度', 'NEXT DUE')} value={focusedProvider.next_due_at ? shortDateTime(focusedProvider.next_due_at) : '—'} />
              <LensFact label={text('调度状态', 'SCHEDULE')} value={focusedProvider.latest_scheduled_status ?? text('未解析', 'unresolved')} />
              <LensFact label={text('连续失败', 'FAILURES')} value={String(focusedProvider.consecutive_failures)} />
              <LensFact label={text('退避至', 'BACKOFF')} value={focusedProvider.backoff_until ? shortDateTime(focusedProvider.backoff_until) : '—'} />
              <LensFact label={text('错误码', 'ERROR')} value={focusedProvider.latest_error_code ?? text('无', 'none')} />
            </div>
            <div className="source-provider-flags">
              {focusedProvider.overdue && <span>{text('已逾期', 'OVERDUE')}</span>}
              {focusedProvider.backfill_pending && <span>{text('待回填', 'BACKFILL PENDING')}</span>}
              {!focusedProvider.overdue && !focusedProvider.backfill_pending && <span>{text('无活动调度告警', 'NO ACTIVE SCHEDULER FLAG')}</span>}
            </div>
          </motion.section>
        )}
      </AnimatePresence>
      {health && total > 0 && (
        <div className="lens-health">
          <span className="healthy" style={{ width: `${health.healthy / total * 100}%` }} />
          <span className="degraded" style={{ width: `${health.degraded / total * 100}%` }} />
          <span className="blocked" style={{ width: `${health.blocked / total * 100}%` }} />
        </div>
      )}
      <div className="lens-coordinate mono">{source.key} / operational category</div>
    </div>
  )
}

export function PathLens({ lane, snapshot }: { lane: string; snapshot: WorldOverview | null }) {
  const { text } = useI18n()
  const categories = sources.filter((source) => sourceNarrative[source.key].lane === lane)
  const categoryKeys = new Set(categories.map((source) => source.key))
  const providers = (snapshot?.sources ?? []).filter((source) => categoryKeys.has(source.measurement_category))
  const health = providers.reduce((acc, source) => {
    if (source.health === 'healthy') acc.healthy += 1
    else if (source.health === 'degraded') acc.degraded += 1
    else if (source.health === 'blocked') acc.blocked += 1
    return acc
  }, { healthy: 0, degraded: 0, blocked: 0 })
  const summaries = categories.map((source) => categorySeriesSummary((snapshot?.category_hourly_series?.[source.key] ?? []).slice(-6)))
  const fresh = summaries.reduce((sum, item) => sum + item.fresh, 0)
  const runs = summaries.reduce((sum, item) => sum + item.runs, 0)
  const failures = providers.filter((provider) => provider.health !== 'healthy')

  return (
    <div className="lens-stack path-lens">
      <div className="lens-index">{text('类别路径 / 运行叠加', 'CATEGORY ROUTE / RUNTIME OVERLAY')}</div>
      <div className="path-lens-title">
        <div><small>{text('类别路径', 'CATEGORY ROUTE')}</small><strong>{lane}</strong></div>
        <span>{text(`${categories.length} 类来源 · ${providers.length} 个 provider`, `${categories.length} categories · ${providers.length} sources`)}</span>
      </div>
      <p>{text(
        '这一视角使用产品 taxonomy 的类别→路径映射，再叠加近六小时运行量和 source health；它不声称某一次 execution 选择了未记录的处理路径。',
        'This view applies the product taxonomy category-to-route mapping, then overlays six-hour activity and source health; it does not claim an unrecorded per-execution path selection.',
      )}</p>
      <div className="lens-facts">
        <LensFact label={text('来源类别', 'CATEGORIES')} value={categories.map((item) => text(item.labelZh, item.label)).join(' · ')} />
        <LensFact label={text('新增 · 6H', 'FRESH · 6H')} value={String(fresh)} />
        <LensFact label={text('运行 · 6H', 'RUNS · 6H')} value={String(runs)} />
        <LensFact label={text('健康度', 'HEALTH')} value={`${health.healthy}H · ${health.degraded}D · ${health.blocked}B`} />
      </div>
      <div className="path-category-map">
        {categories.map((source) => {
          const state = snapshot?.categories.find((item) => item.category === source.key)
          const activity = categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? [])
          return (
            <div key={source.key}>
              <span className={`state-${sourceState(state)}`} />
              <div><small>{source.sub}</small><strong>{text(source.labelZh, source.label)}</strong></div>
              <em>{text(`${activity.fresh} 新增 · ${activity.runs} 运行`, `${activity.fresh} fresh · ${activity.runs} runs`)}</em>
            </div>
          )
        })}
      </div>
      <div className="path-failure-field">
        <div><small>{text('当前边界', 'CURRENT BOUNDARY')}</small><strong>{failures.length ? text(`${failures.length} 个来源需要注意`, `${failures.length} sources require attention`) : text('无 degraded / blocked 来源', 'NO DEGRADED / BLOCKED SOURCES')}</strong></div>
        {failures.slice(0, 6).map((provider) => (
          <div key={provider.source_id} className={`state-${provider.health}`}>
            <span>{provider.source_id}</span>
            <b>{provider.latest_error_code ?? provider.latest_scheduled_status ?? provider.health}</b>
          </div>
        ))}
      </div>
      <div className="lens-coordinate mono">{lane.toLowerCase().replaceAll(' ', '-')} / taxonomy-map + runtime-overlay</div>
    </div>
  )
}

export function HotLens({ item, onInspect }: { item: HotBug; onInspect: () => void }) {
  const { text } = useI18n()
  const signal = item.priority_signals.includes('critical_severity') ? text('严重等级', 'CRITICAL SEVERITY') : item.priority_signals[0]?.replaceAll('_', ' ').toUpperCase() ?? text('热点', 'HOT')
  return (
    <div className="lens-stack">
      <div className="lens-index">{text('HOT 工作集 / REDIS 读取边界', 'HOT WORKING SET / REDIS READ SEAM')}</div>
      <div className="lens-title"><span><Flame size={18} /></span><div><small>{signal}</small><strong>{item.cve_id ?? item.external_object_id}</strong></div></div>
      <p>{item.description ?? item.title ?? text('当前 Hot Bug 投影来自真实读取，不填充演示内容。', 'Current Hot Bug projection. No demo content substituted.')}</p>
      <div className="lens-facts two">
        <LensFact label={text('来源', 'SOURCE')} value={item.source_id} />
        <LensFact label={text('版本', 'REVISION')} value={item.external_revision ?? text('内容版本', 'content revision')} />
        <LensFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
        <LensFact label="TTL" value={item.ttl_seconds != null ? `${Math.max(0, Math.round(item.ttl_seconds / 60))} min` : item.pinned ? text('已固定', 'pinned') : '—'} />
        <LensFact label={text('读取次数', 'ACCESS')} value={item.access_count > 0 ? formatHotCount(item.access_count) : '0'} />
        <LensFact label={text('工作状态', 'WORKING STATE')} value={[item.active ? text('活动', 'active') : null, item.pinned ? text('已固定', 'pinned') : null].filter(Boolean).join(' · ') || text('被动', 'passive')} />
      </div>
      <div className="lens-signal"><small>{text('变化字段', 'CHANGED FIELDS')}</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : text('无已报告字段', 'none reported')}</span></div>
      <div className="lens-signal"><small>{text('优先级信号', 'PRIORITY SIGNALS')}</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : text('无已报告信号', 'none reported')}</span></div>
      <button className="lens-primary" onClick={onInspect}>{text('打开情报档案', 'OPEN INTELLIGENCE DOSSIER')} <ArrowUpRight size={13} /></button>
      <div className="lens-coordinate mono">{item.source_id}:{item.external_object_id}</div>
    </div>
  )
}

function LensFact({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>
}

export function Telemetry({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return <div className={`telemetry-readout tone-${tone}`}><small>{label}</small><strong>{value}</strong><span>{detail}</span></div>
}
