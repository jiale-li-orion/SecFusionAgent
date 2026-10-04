import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import {
  Activity,
  Archive,
  BadgeCheck,
  Binary,
  Boxes,
  CircleGauge,
  Clock3,
  DatabaseZap,
  Eye,
  Fingerprint,
  Gauge,
  RadioTower,
  ScanLine,
  ServerCog,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Waypoints,
} from 'lucide-react'
import { getAgentRuntime, getCompetitionProof, getWorldOverview, type CompetitionProof, type WorldOverview } from '../lib/api'

const windows = ['1h', '6h', '24h', '168h'] as const

type ObservatoryMode = 'live' | 'proof'

export function ObservatoryPage() {
  const [mode, setMode] = useState<ObservatoryMode>('live')
  const [windowKey, setWindowKey] = useState<(typeof windows)[number]>('24h')
  const worldQuery = useQuery({ queryKey: ['observatory-world'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const agentsQuery = useQuery({ queryKey: ['observatory-agents'], queryFn: getAgentRuntime, refetchInterval: 15_000 })
  const proofQuery = useQuery({ queryKey: ['competition-proof'], queryFn: getCompetitionProof, staleTime: 60_000 })

  return (
    <section className={`observatory-space-v3 observatory-page observatory-${mode}`}>
      <header className="observatory-hero-v3 observatory-heading">
        <div>
          <p>OPERATIONAL TRUTH / FROZEN EVIDENCE / NO KPI THEATER</p>
          <h1>OBSERVATORY <span>CORE</span></h1>
          <small>LIVE 展示当前运行事实；PROOF 展示冻结测量证据。切换时语义边界保持严格分离。</small>
        </div>
        <div className="observatory-mode-switch" role="tablist" aria-label="Observatory mode">
          <button className={mode === 'live' ? 'active' : ''} onClick={() => setMode('live')}><Activity size={14} /> LIVE</button>
          <button className={mode === 'proof' ? 'active' : ''} onClick={() => setMode('proof')}><Archive size={14} /> PROOF</button>
          <motion.span className="mode-cursor" animate={{ x: mode === 'live' ? 0 : '100%' }} transition={{ type: 'spring', stiffness: 320, damping: 28 }} />
        </div>
      </header>

      <AnimatePresence mode="wait">
        {mode === 'live' ? (
          <motion.div key="live" className="observatory-live" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: .985 }} transition={{ duration: .22 }}>
            <LiveObservatory world={worldQuery.data ?? null} agents={agentsQuery.data ?? null} windowKey={windowKey} setWindowKey={setWindowKey} />
          </motion.div>
        ) : (
          <motion.div key="proof" className="observatory-proof" initial={{ opacity: 0, scale: 1.015, filter: 'blur(5px)' }} animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }} exit={{ opacity: 0, scale: .99 }} transition={{ duration: .28 }}>
            <ProofObservatory proof={proofQuery.data ?? null} loading={proofQuery.isLoading} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function LiveObservatory({ world, agents, windowKey, setWindowKey }: { world: WorldOverview | null; agents: Awaited<ReturnType<typeof getAgentRuntime>> | null; windowKey: string; setWindowKey: (value: (typeof windows)[number]) => void }) {
  const current = world?.windows[windowKey]
  const hours = windowKey === '1h' ? 1 : windowKey === '6h' ? 6 : windowKey === '24h' ? 24 : 168
  const series = useMemo(() => (world?.hourly_series ?? []).slice(-hours), [world?.hourly_series, hours])
  const activeTasks = agents?.roles.reduce((sum, role) => sum + role.active_tasks, 0) ?? 0
  const totalSources = world ? world.source_health.healthy + world.source_health.degraded + world.source_health.blocked : 0

  return (
    <>
      <div className="live-command-strip">
        <LiveMetric icon={RadioTower} label="SOURCE HEALTH" value={world ? `${world.source_health.healthy}/${totalSources}` : '—'} detail={world ? `${(world.healthy_rate * 100).toFixed(1)}% healthy` : 'loading'} tone="lime" />
        <LiveMetric icon={DatabaseZap} label="FRESH CHANGES" value={current ? compactNumber(current.fresh_external_changes) : '—'} detail={`${windowKey} operational window`} tone="cyan" />
        <LiveMetric icon={Clock3} label="QUEUE P95" value={seconds(current?.queue_delay_p95_seconds)} detail="scheduled acquisition" tone="violet" />
        <LiveMetric icon={Gauge} label="EXECUTION P95" value={seconds(current?.execution_p95_seconds)} detail={current?.scheduled_run_success_rate != null ? `${pct(current.scheduled_run_success_rate)} run success` : 'execution runtime'} tone="amber" />
        <LiveMetric icon={Waypoints} label="AGENT TASKS" value={String(activeTasks)} detail={`${agents?.roles.reduce((sum, role) => sum + role.total_tasks, 0) ?? 0} durable runs`} tone="blue" />
      </div>

      <div className="live-window-row">
        <div className="live-now"><span className="scan-dot" /><strong>OPERATIONAL SNAPSHOT</strong><span>{world ? snapshotAge(world.generated_at) : 'loading'}</span></div>
        <div className="window-switch">{windows.map((item) => <button key={item} className={windowKey === item ? 'active' : ''} onClick={() => setWindowKey(item)}>{item === '168h' ? '7d' : item}</button>)}</div>
      </div>

      <div className="observatory-live-grid">
        <section className="telemetry-panel telemetry-wide">
          <PanelHead eyebrow="DATA PLANE" title="WORLD ACTIVITY" meta={`${series.length} hourly samples`} icon={ScanLine} />
          <div className="telemetry-charts">
            <TelemetryChart title="FRESH / BACKFILL" series={series} lines={[{ key: 'fresh_external_changes', label: 'fresh', tone: 'cyan' }, { key: 'backfill_observations', label: 'backfill', tone: 'violet' }]} />
            <TelemetryChart title="CANONICAL WRITES" series={series} lines={[{ key: 'canonical_writes', label: 'writes', tone: 'lime' }, { key: 'observations', label: 'observations', tone: 'blue' }]} />
            <TelemetryChart title="QUEUE / EXECUTION" series={series} lines={[{ key: 'queue_delay_p95_seconds', label: 'queue p95', tone: 'violet' }, { key: 'execution_p95_seconds', label: 'execution p95', tone: 'amber' }]} />
          </div>
        </section>

        <section className="telemetry-panel source-spectrum">
          <PanelHead eyebrow="SOURCE CONSTELLATION" title="HEALTH SPECTRUM" meta="8 product categories" icon={RadioTower} />
          <div className="spectrum-list">
            {(world?.categories ?? []).map((category, index) => {
              const total = category.healthy + category.degraded + category.blocked
              return <motion.div key={category.category} className="spectrum-row" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * .035 }}>
                <div className="spectrum-label"><strong>{category.category}</strong><span>{total}</span></div>
                <div className="spectrum-track">
                  <span className="healthy" style={{ width: total ? `${category.healthy / total * 100}%` : '0%' }} />
                  <span className="degraded" style={{ width: total ? `${category.degraded / total * 100}%` : '0%' }} />
                  <span className="blocked" style={{ width: total ? `${category.blocked / total * 100}%` : '0%' }} />
                </div>
                <small>{category.healthy} H · {category.degraded} D · {category.blocked} B</small>
              </motion.div>
            })}
          </div>
        </section>

        <section className="telemetry-panel agent-spectrum">
          <PanelHead eyebrow="AGENT RUNTIME" title="ROLE ACTIVITY" meta="live + durable history" icon={Sparkles} />
          <div className="agent-spectrum-list">
            {(agents?.roles ?? []).map((role) => {
              const alias = role.role_id === 'DecisionRole' ? 'ORACLE' : role.role_id === 'InvestigationRole' ? 'ARGUS' : 'ALCHEMIST'
              return <div key={role.role_id} className={`agent-spectrum-row ${role.active_tasks ? 'live' : ''}`}>
                <div className="agent-spectrum-icon"><CircleGauge size={18} /></div>
                <div><small>{role.role_id}@{role.version}</small><strong>{alias}</strong><span>{role.active_tasks ? `${role.active_tasks} active` : 'idle'} · {role.total_tasks} durable</span></div>
                <RoleBars counts={role.status_counts} />
              </div>
            })}
          </div>
          <div className="capability-activity-summary"><Binary size={13} /><span>Persisted CapabilityInvocation</span><strong>{agents?.recent_capabilities.length ?? 0}</strong></div>
        </section>

        <section className="telemetry-panel system-status-panel">
          <PanelHead eyebrow="SYSTEM" title="PIPELINE INTEGRITY" meta="measured facts only" icon={ServerCog} />
          <div className="system-status-grid">
            <SystemFact icon={Boxes} label="OUTBOX DELIVERED" value={world ? compactNumber(world.outbox_delivered) : '—'} />
            <SystemFact icon={Eye} label="LEXICAL READY" value={world ? compactNumber(world.lexical_ready_documents) : '—'} />
            <SystemFact icon={ShieldCheck} label="ARTIFACT STORE" value={world?.artifact_store_status ?? '—'} />
            <SystemFact icon={Fingerprint} label="ARTIFACT INTEGRITY" value={world?.public_epoch_artifact_integrity_rate != null ? pct(world.public_epoch_artifact_integrity_rate) : '—'} />
          </div>
        </section>
      </div>
    </>
  )
}

function ProofObservatory({ proof, loading }: { proof: CompetitionProof | null; loading: boolean }) {
  const metric = (name: string) => proof?.headline_metrics.find((item) => item.metric_name === name)
  return (
    <>
      <section className="proof-seal">
        <div className="proof-seal-mark"><Archive size={30} /><div className="seal-ring" /></div>
        <div className="proof-seal-copy"><small>FROZEN COMPETITION EVIDENCE</small><strong>{proof?.report_id ?? (loading ? 'RESOLVING REPORT…' : 'UNAVAILABLE')}</strong><span className="mono">{proof?.deployment_revision_id ?? 'deployment revision'}</span></div>
        <div className="proof-seal-stats">
          <ProofSealStat value={proof ? String(proof.benchmark_runs_completed) : '—'} label="BENCHMARK RUNS" />
          <ProofSealStat value={proof ? `${proof.case_runs_passed}/37` : '—'} label="CASE RUNS PASSED" />
          <ProofSealStat value={proof ? `${proof.observed_core_metrics}/${proof.registered_core_metrics}` : '—'} label="CORE METRICS" />
        </div>
      </section>

      <div className="proof-grid">
        <ProofBlock title="M1 · MONITORING" eyebrow="MULTI-SOURCE OPERATIONS" tone="cyan" icon={RadioTower}>
          <ProofNumber label="≤ 6H RATE" value={proofMetric(metric('m1.monitoring.within_6h_rate'))} />
          <ProofNumber label="SOURCE DELIVERY COVERAGE" value={proofMetric(metric('m1.source_delivery_coverage'))} warning />
          <p className="proof-note warning-note"><TriangleAlert size={13} /> Coverage weakness stays visible. Passing latency does not erase missing delivery keys.</p>
        </ProofBlock>

        <ProofBlock title="M3 · ENRICHMENT" eyebrow="CLOSED-SET PRECISION / RECALL" tone="lime" icon={DatabaseZap}>
          <div className="proof-triplet"><ProofNumber label="TP" value={rawMetric(metric('m3.true_positive'))} /><ProofNumber label="FP" value={rawMetric(metric('m3.false_positive'))} /><ProofNumber label="FN" value={rawMetric(metric('m3.false_negative'))} /></div>
          <ProofNumber label="MICRO P / R" value={`${proofMetric(metric('m3.micro_precision'))} / ${proofMetric(metric('m3.micro_recall'))}`} />
        </ProofBlock>

        <ProofBlock title="M6 · PRODUCT QA" eyebrow="DECISION QUALITY" tone="violet" icon={BadgeCheck}>
          <div className="proof-triplet"><ProofNumber label="ACCURACY" value={proofMetric(metric('m6.answer_accuracy'))} /><ProofNumber label="GROUNDED" value={proofMetric(metric('m6.groundedness'))} /><ProofNumber label="CITATIONS" value={proofMetric(metric('m6.citation_correctness'))} /></div>
          <ProofNumber label="INTERACTIVE MAX" value={proofMetric(metric('m6.interactive_latency_seconds'))} />
        </ProofBlock>

        <ProofBlock title="SESSION · CONTINUITY" eyebrow="MULTI-TURN PRODUCT" tone="blue" icon={Waypoints}>
          <ProofNumber label="CONTEXT CHAIN" value={proofMetric(metric('m6.session_context_chain_correctness'))} />
          <ProofNumber label="TARGET CARRY" value={proofMetric(metric('m6.session_target_carry_correctness'))} />
          <ProofNumber label="RETRIEVAL REUSE" value={proofMetric(metric('m6.session_retrieval_reuse_rate'))} />
        </ProofBlock>
      </div>

      <div className="proof-lower-grid">
        <section className="proof-targets">
          <PanelHead eyebrow="COMPETITION TARGETS" title="TARGET CHECKS" meta={`${proof?.target_checks.length ?? 0} checks`} icon={ShieldCheck} />
          <div className="target-check-list">{(proof?.target_checks ?? []).map((item) => <div key={item.target_name} className={`target-check ${item.status}`}><span className="target-icon"><BadgeCheck size={15} /></span><div><small>{item.target_name}</small><strong>{item.requirement}</strong><span>{item.metric_name} · observed {formatNumber(item.observed_value)} {item.comparator} {formatNumber(item.threshold)}</span></div><b>{item.status}</b></div>)}</div>
        </section>
        <section className="proof-boundary">
          <PanelHead eyebrow="MEASUREMENT BOUNDARY" title="WHAT WE REFUSE TO FAKE" meta={`${proof?.partial_metric_groups ?? 0} partial groups`} icon={TriangleAlert} />
          <div className="core-metric-ring"><span>{proof ? Math.round(proof.observed_core_metrics / proof.registered_core_metrics * 100) : 0}%</span><small>CORE METRICS OBSERVED</small></div>
          <div className="unevaluated-list">{(proof?.unevaluated_core_metrics ?? []).map((name) => <div key={name}><span className="unevaluated-dot" /><strong>{name}</strong><small>exact monetary cost · not inferred</small></div>)}</div>
          <p>Exact provider / capability monetary cost stays unavailable until the provider or executor reports it. Token counts are never multiplied by public price tables and presented as fact.</p>
        </section>
      </div>
    </>
  )
}

function TelemetryChart({ title, series, lines }: { title: string; series: Array<Record<string, number | string | null>>; lines: Array<{ key: string; label: string; tone: string }> }) {
  const width = 520
  const height = 150
  const allValues = lines.flatMap((line) => series.map((item) => numeric(item[line.key]))).filter((value) => Number.isFinite(value))
  const max = Math.max(...allValues, 1)
  const paths = lines.map((line) => ({ ...line, d: linePath(series.map((item) => numeric(item[line.key])), width, height, max) }))
  return <div className="telemetry-chart"><div className="chart-head"><strong>{title}</strong><div>{lines.map((line) => <span key={line.key} className={`tone-${line.tone}`}><i />{line.label}</span>)}</div></div><div className="chart-canvas"><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><defs><linearGradient id={`fade-${title.replaceAll(' ', '-')}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".16"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((part) => <line key={part} x1="0" x2={width} y1={height * part} y2={height * part} className="chart-gridline" />)}{paths.map((path) => <motion.path key={path.key} className={`chart-line tone-${path.tone}`} d={path.d} fill="none" initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: .8, ease: 'easeOut' }} />)}</svg><div className="chart-scanline" /></div></div>
}

function LiveMetric({ icon: Icon, label, value, detail, tone }: { icon: typeof Activity; label: string; value: string; detail: string; tone: string }) { return <article className={`live-metric tone-${tone}`}><span className="live-metric-icon"><Icon size={17} /></span><div><small>{label}</small><motion.strong key={value} initial={{ opacity: .25, y: 4 }} animate={{ opacity: 1, y: 0 }}>{value}</motion.strong><span>{detail}</span></div></article> }
function PanelHead({ eyebrow, title, meta, icon: Icon }: { eyebrow: string; title: string; meta: string; icon: typeof Activity }) { return <div className="panel-head"><span className="panel-head-icon"><Icon size={15} /></span><div><small>{eyebrow}</small><strong>{title}</strong></div><span>{meta}</span></div> }
function SystemFact({ icon: Icon, label, value }: { icon: typeof Boxes; label: string; value: string }) { return <div className="system-fact"><Icon size={16} /><small>{label}</small><strong>{value}</strong></div> }
function RoleBars({ counts }: { counts: Record<string, number> }) { const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1; return <div className="role-bars"><span className="done" style={{ width: `${((counts.completed ?? 0) / total) * 100}%` }} /><span className="live" style={{ width: `${(((counts.running ?? 0) + (counts.queued ?? 0)) / total) * 100}%` }} /><span className="fail" style={{ width: `${(((counts.failed ?? 0) + (counts.blocked ?? 0)) / total) * 100}%` }} /></div> }
function ProofBlock({ title, eyebrow, tone, icon: Icon, children }: { title: string; eyebrow: string; tone: string; icon: typeof Activity; children: React.ReactNode }) { return <motion.section className={`proof-block tone-${tone}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><div className="proof-block-head"><span><Icon size={16} /></span><div><small>{eyebrow}</small><strong>{title}</strong></div></div><div className="proof-block-body">{children}</div></motion.section> }
function ProofNumber({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) { return <div className={`proof-number ${warning ? 'warning' : ''}`}><small>{label}</small><strong>{value}</strong></div> }
function ProofSealStat({ value, label }: { value: string; label: string }) { return <div><strong>{value}</strong><small>{label}</small></div> }

function linePath(values: number[], width: number, height: number, max: number) { if (!values.length) return ''; if (values.length === 1) return `M 0 ${height - values[0] / max * height}`; return values.map((value, index) => `${index ? 'L' : 'M'} ${(index / (values.length - 1)) * width} ${height - Math.min(value / max, 1) * (height - 10) - 5}`).join(' ') }
function numeric(value: number | string | null | undefined) { return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) || 0 : 0 }
function seconds(value: number | null | undefined) { return value == null ? '—' : value < 1 ? `${(value * 1000).toFixed(0)}ms` : `${value.toFixed(value < 10 ? 2 : 1)}s` }
function pct(value: number) { return `${(value * 100).toFixed(value >= .995 ? 0 : 1)}%` }
function compactNumber(value: number) { return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) }
function formatNumber(value: number) { return Math.abs(value) < 10 ? value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') : value.toFixed(0) }
function proofMetric(metric: CompetitionProof['headline_metrics'][number] | undefined) { if (!metric) return '—'; if (metric.unit === 'ratio') return pct(metric.value); if (metric.unit === 'seconds') return `${metric.value.toFixed(3)}s`; return `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ''}` }
function rawMetric(metric: CompetitionProof['headline_metrics'][number] | undefined) { return metric ? formatNumber(metric.value) : '—' }
function snapshotAge(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); if (seconds < 60) return `${seconds}s ago`; const minutes = Math.floor(seconds / 60); if (minutes < 60) return `${minutes}m ago`; const hours = Math.floor(minutes / 60); return hours < 48 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago` }
