import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Activity,
  Archive,
  BadgeCheck,
  Binary,
  BrainCircuit,
  Boxes,
  CircleGauge,
  Clock3,
  DatabaseZap,
  Eye,
  Fingerprint,
  Gauge,
  Link2,
  RadioTower,
  ScanLine,
  ServerCog,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Waypoints,
  X,
} from 'lucide-react'
import { evidenceBoundObjectIds, getAgentRuntime, getCompetitionProof, getCompetitionProofRun, getEvidence, getWorldOverview, type CompetitionProof, type ProofMetricObservation, type ProofRunDetail, type WorldOverview } from '../lib/api'
import { useI18n } from '../lib/i18n'

const windows = ['1h', '6h', '24h', '168h'] as const

type ObservatoryMode = 'live' | 'proof'

export function ObservatoryPage() {
  const { text } = useI18n()
  const [params, setParams] = useSearchParams()
  const preferredRunId = params.get('run')
  const preferredCaseRunId = params.get('caseRun')
  const reduceMotion = Boolean(useReducedMotion())
  const mode: ObservatoryMode = params.get('mode') === 'proof' ? 'proof' : 'live'
  const [windowKey, setWindowKey] = useState<(typeof windows)[number]>('24h')
  const worldQuery = useQuery({ queryKey: ['observatory-world'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const agentsQuery = useQuery({ queryKey: ['observatory-agents'], queryFn: getAgentRuntime, refetchInterval: 15_000 })
  const proofQuery = useQuery({ queryKey: ['competition-proof'], queryFn: getCompetitionProof, staleTime: 60_000 })

  function selectMode(nextMode: ObservatoryMode) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (nextMode === 'proof') {
        next.set('mode', 'proof')
      } else {
        next.delete('mode')
        next.delete('run')
        next.delete('caseRun')
      }
      return next
    }, { replace: true })
  }

  useEffect(() => {
    const openProof = () => {
      setParams((current) => {
        const next = new URLSearchParams(current)
        next.set('mode', 'proof')
        return next
      }, { replace: true })
    }
    window.addEventListener('secfusion:proof', openProof)
    return () => window.removeEventListener('secfusion:proof', openProof)
  }, [setParams])

  return (
    <section className={`observatory-space observatory-page observatory-${mode}`}>
      <header className="observatory-switchboard-heading observatory-heading">
        <div>
          <p>{mode === 'live'
            ? text('测量此刻正在发生的运行', 'MEASURE THE SYSTEM WHILE IT LIVES')
            : text('让完成的实验留下可复验记录', 'LET THE FINISHED EXPERIMENT STAND')}</p>
          <h1>{mode === 'live'
            ? <>{text('运行', 'LIVE')} <span>{text('观测', 'OBSERVATORY')}</span></>
            : <>{text('冻结', 'FROZEN')} <span>{text('证明', 'PROOF')}</span></>}</h1>
          <small>{mode === 'live'
            ? text(
              'Data Plane、source health、queue / execution 与 Agent runtime 按当前测量窗口展开；所有读数来自当前运行快照。',
              'Data Plane, source health, queue / execution, and Agent runtime unfold over the current measurement window; every reading comes from the live operational snapshot.',
            )
            : text(
              'CompetitionReport、BenchmarkRun、CaseRun 与 MetricObservation 形成冻结证据链；运行坐标、测量值和 EvidenceRef 保持可追溯。',
              'CompetitionReport, BenchmarkRun, CaseRun, and MetricObservation form the frozen proof chain; runtime coordinates, measurements, and EvidenceRefs remain traceable.',
            )}</small>
        </div>
        <div className="observatory-mode-switch" role="tablist" aria-label={text('观测模式', 'Observatory mode')}>
          <button role="tab" aria-selected={mode === 'live'} className={mode === 'live' ? 'active' : ''} onClick={() => selectMode('live')}><Activity size={14} /> {text('实时', 'LIVE')}</button>
          <button role="tab" aria-selected={mode === 'proof'} className={mode === 'proof' ? 'active' : ''} onClick={() => selectMode('proof')}><Archive size={14} /> {text('冻结证明', 'PROOF')}</button>
          <motion.span className="mode-cursor" animate={{ x: mode === 'live' ? 0 : '100%' }} transition={{ type: 'spring', stiffness: 320, damping: 28 }} />
        </div>
      </header>

      <AnimatePresence mode="wait">
        {mode === 'live' ? (
          <motion.div
            key="live"
            className="observatory-live observatory-live-stage"
            initial={reduceMotion ? false : { opacity: 0, scaleY: .06, filter: 'brightness(1.8) saturate(.7)', transformOrigin: 'center top' }}
            animate={{ opacity: 1, scaleY: 1, filter: 'brightness(1) saturate(1)' }}
            exit={reduceMotion ? undefined : { opacity: .18, scaleY: .025, filter: 'brightness(2.2) saturate(.5)', transformOrigin: 'center top' }}
            transition={{ duration: reduceMotion ? 0 : .3, ease: [0.22, 1, 0.36, 1] }}
          >
            {(worldQuery.isError || agentsQuery.isError) && (
              <div className="observatory-live-fault">
                <TriangleAlert size={14} />
                <div><small>{text('LIVE 读取降级', 'LIVE READ DEGRADED')}</small><strong>{worldQuery.isError ? text('Data Plane 快照不可用', 'Data Plane snapshot unavailable') : text('Agent Runtime 快照不可用', 'Agent Runtime snapshot unavailable')}</strong></div>
                <button onClick={() => selectMode('proof')}><Archive size={12} /> {text('打开冻结 PROOF', 'OPEN FROZEN PROOF')}</button>
              </div>
            )}
            <LiveObservatory world={worldQuery.data ?? null} agents={agentsQuery.data ?? null} windowKey={windowKey} setWindowKey={setWindowKey} />
          </motion.div>
        ) : (
          <motion.div
            key="proof"
            className="observatory-proof observatory-proof-stage"
            initial={reduceMotion ? false : { opacity: 0, y: -12, rotateX: 1.2, clipPath: 'inset(0 0 100% 0)', filter: 'brightness(1.12)' }}
            animate={{ opacity: 1, y: 0, rotateX: 0, clipPath: 'inset(0 0 0% 0)', filter: 'brightness(1)' }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 8, clipPath: 'inset(100% 0 0 0)', filter: 'brightness(.94)' }}
            transition={{ duration: reduceMotion ? 0 : .38, ease: [0.22, 1, 0.36, 1] }}
          >
            {proofQuery.isError && <div className="observatory-proof-fault"><TriangleAlert size={14} /><span>{text('冻结 CompetitionReport 当前不可读。', 'Frozen CompetitionReport read unavailable.')}</span></div>}
            <ProofObservatory key={`${preferredRunId ?? 'proof-default'}:${preferredCaseRunId ?? 'case-default'}`} proof={proofQuery.data ?? null} loading={proofQuery.isLoading} preferredRunId={preferredRunId} preferredCaseRunId={preferredCaseRunId} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

function proofTargetPath(ref: string, runId: string, caseRunId: string) {
  const base = { from: 'proof', proofRun: runId, caseRun: caseRunId }
  if (ref.startsWith('cve:')) return `/intelligence?${new URLSearchParams({ ...base, cve: ref.slice(4) }).toString()}`
  if (ref.startsWith('knowledge-key:cve:')) return `/intelligence?${new URLSearchParams({ ...base, cve: ref.slice('knowledge-key:cve:'.length) }).toString()}`
  if (ref.startsWith('object:')) return `/intelligence?${new URLSearchParams({ ...base, object: ref.slice(7) }).toString()}`
  if (ref.startsWith('incident:')) return `/intelligence?${new URLSearchParams({ ...base, incident: ref.slice(9) }).toString()}`
  return null
}

function proofTargetLabel(ref: string) {
  if (ref.startsWith('cve:') || ref.startsWith('knowledge-key:cve:')) return 'CVE DOSSIER'
  if (ref.startsWith('object:')) return 'OBJECT DOSSIER'
  if (ref.startsWith('incident:')) return 'INCIDENT DOSSIER'
  return 'TARGET'
}

function proofRefKind(ref: string) {
  const [kind] = ref.split(':', 1)
  return kind?.replaceAll('-', ' ').toUpperCase() || 'FROZEN REF'
}

function LiveObservatory({ world, agents, windowKey, setWindowKey }: { world: WorldOverview | null; agents: Awaited<ReturnType<typeof getAgentRuntime>> | null; windowKey: string; setWindowKey: (value: (typeof windows)[number]) => void }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [focus, setFocus] = useState<'world' | 'sources' | 'agents' | 'system' | null>(null)
  const current = world?.windows[windowKey]
  const hours = windowKey === '1h' ? 1 : windowKey === '6h' ? 6 : windowKey === '24h' ? 24 : 168
  const series = useMemo(() => (world?.hourly_series ?? []).slice(-hours), [world?.hourly_series, hours])
  const activeTasks = agents?.roles.reduce((sum, role) => sum + role.active_tasks, 0) ?? 0
  const totalSources = world ? world.source_health.healthy + world.source_health.degraded + world.source_health.blocked : 0
  const chooseFocus = (next: 'world' | 'sources' | 'agents' | 'system') => setFocus((current) => current === next ? null : next)

  return (
    <>
      <div className="live-command-strip">
        <LiveMetric icon={RadioTower} label="SOURCE HEALTH" value={world ? `${world.source_health.healthy}/${totalSources}` : '—'} detail={world ? `${(world.healthy_rate * 100).toFixed(1)}% healthy` : 'loading'} tone="lime" active={focus === 'sources'} onClick={() => chooseFocus('sources')} />
        <LiveMetric icon={DatabaseZap} label="FRESH CHANGES" value={current ? compactNumber(current.fresh_external_changes) : '—'} detail={`${windowKey} operational window`} tone="cyan" active={focus === 'world'} onClick={() => chooseFocus('world')} />
        <LiveMetric icon={Clock3} label="QUEUE P95" value={seconds(current?.queue_delay_p95_seconds)} detail="scheduled acquisition" tone="violet" active={focus === 'world'} onClick={() => chooseFocus('world')} />
        <LiveMetric icon={Gauge} label="EXECUTION P95" value={seconds(current?.execution_p95_seconds)} detail={current?.scheduled_run_success_rate != null ? `${pct(current.scheduled_run_success_rate)} run success` : 'execution runtime'} tone="amber" active={focus === 'world'} onClick={() => chooseFocus('world')} />
        <LiveMetric icon={Waypoints} label="AGENT TASKS" value={String(activeTasks)} detail={`${agents?.roles.reduce((sum, role) => sum + role.total_tasks, 0) ?? 0} durable runs`} tone="blue" active={focus === 'agents'} onClick={() => chooseFocus('agents')} />
      </div>

      <div className="live-window-row">
        <div className="live-now"><span className="scan-dot" /><strong>{text('运行快照', 'OPERATIONAL SNAPSHOT')}</strong><span>{world ? snapshotAge(world.generated_at) : text('加载中', 'loading')}</span></div>
        <div className="window-switch">{windows.map((item) => <button key={item} className={windowKey === item ? 'active' : ''} onClick={() => setWindowKey(item)}>{item === '168h' ? '7d' : item}</button>)}</div>
      </div>

      <div className={`observatory-live-grid ${focus ? `has-observatory-focus focus-${focus}` : ''}`}>
        <section className={`telemetry-panel telemetry-wide ${focus === 'world' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
          <PanelHead eyebrow="DATA PLANE" title={text('世界活动', 'WORLD ACTIVITY')} meta={text(`${series.length} 个小时样本`, `${series.length} hourly samples`)} icon={ScanLine} />
          <div className="telemetry-charts">
            <TelemetryChart title="FRESH / BACKFILL" series={series} lines={[{ key: 'fresh_external_changes', label: 'fresh', tone: 'cyan' }, { key: 'backfill_observations', label: 'backfill', tone: 'violet' }]} />
            <TelemetryChart title="CANONICAL WRITES" series={series} lines={[{ key: 'canonical_writes', label: 'writes', tone: 'lime' }, { key: 'observations', label: 'observations', tone: 'blue' }]} />
            <TelemetryChart title="QUEUE / EXECUTION" series={series} lines={[{ key: 'queue_delay_p95_seconds', label: 'queue p95', tone: 'violet' }, { key: 'execution_p95_seconds', label: 'execution p95', tone: 'amber' }]} />
          </div>
        </section>

        <section className={`telemetry-panel source-spectrum ${focus === 'sources' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
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
            {!world && <SourceSpectrumBlueprint />}
          </div>
        </section>

        <section className={`telemetry-panel agent-spectrum ${focus === 'agents' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}>
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
            {!agents && <AgentSpectrumBlueprint />}
          </div>
          <div className="capability-activity-summary"><Binary size={13} /><span>{text('持久化 CapabilityInvocation', 'Persisted CapabilityInvocation')}</span><strong>{agents?.recent_capabilities.length ?? 0}</strong></div>
        </section>

        <section
          className={`telemetry-panel system-status-panel ${focus === 'system' ? 'focus-selected' : focus ? 'focus-dimmed' : ''}`}
          role="button"
          tabIndex={0}
          aria-pressed={focus === 'system'}
          onClick={() => chooseFocus('system')}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              chooseFocus('system')
            }
          }}
        >
          <PanelHead eyebrow="SYSTEM" title={text('管线完整性', 'PIPELINE INTEGRITY')} meta={text('仅显示实测事实', 'measured facts only')} icon={ServerCog} />
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

function ProofObservatory({ proof, loading, preferredRunId, preferredCaseRunId }: { proof: CompetitionProof | null; loading: boolean; preferredRunId: string | null; preferredCaseRunId: string | null }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const metric = (name: string) => proof?.headline_metrics.find((item) => item.metric_name === name)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [compareRunId, setCompareRunId] = useState<string | null>(null)
  const [selectedCaseRunId, setSelectedCaseRunId] = useState<string | null>(preferredCaseRunId)
  const [selectedEvidenceRef, setSelectedEvidenceRef] = useState<string | null>(null)
  const activeRunId = selectedRunId ?? preferredRunId ?? proof?.runs[0]?.benchmark_run_id ?? null
  const runQuery = useQuery({
    queryKey: ['competition-proof-run', activeRunId],
    queryFn: () => getCompetitionProofRun(activeRunId!),
    enabled: Boolean(activeRunId),
    staleTime: 60_000,
  })
  const compareQuery = useQuery({
    queryKey: ['competition-proof-run', compareRunId],
    queryFn: () => getCompetitionProofRun(compareRunId!),
    enabled: Boolean(compareRunId && compareRunId !== activeRunId),
    staleTime: 60_000,
  })
  const selectedCaseRun = runQuery.data?.cases.find((item) => item.case_run_id === selectedCaseRunId)
    ?? runQuery.data?.cases[0]
    ?? null

  const evidenceQuery = useQuery({
    queryKey: ['proof-evidence', selectedEvidenceRef],
    queryFn: () => getEvidence(selectedEvidenceRef!),
    enabled: Boolean(selectedEvidenceRef?.startsWith('evidence:')),
  })
  return (
    <>
      <section className="proof-seal">
        <div className="proof-seal-mark"><Archive size={30} /><div className="seal-ring" /></div>
        <div className="proof-seal-copy"><small>{text('冻结竞赛证据', 'FROZEN COMPETITION EVIDENCE')}</small><strong>{proof?.report_id ?? (loading ? text('解析报告…', 'RESOLVING REPORT…') : text('不可用', 'UNAVAILABLE'))}</strong><span className="mono">{proof?.deployment_revision_id ?? text('deployment revision 未绑定', 'deployment revision')}</span></div>
        <div className="proof-seal-stats">
          <ProofSealStat value={proof ? String(proof.benchmark_runs_completed) : '—'} label={text('BENCHMARK RUNS', 'BENCHMARK RUNS')} />
          <ProofSealStat value={proof ? `${proof.case_runs_passed}/37` : '—'} label={text('通过的 CASE RUNS', 'CASE RUNS PASSED')} />
          <ProofSealStat value={proof ? `${proof.observed_core_metrics}/${proof.registered_core_metrics}` : '—'} label={text('核心 METRICS', 'CORE METRICS')} />
        </div>
      </section>

      <section className="proof-run-ledger">
        <div className="proof-run-ledger-head">
          <div><small>{text('冻结 BENCHMARK RUNS', 'FROZEN BENCHMARK RUNS')}</small><strong>{text('RUN → CASE → METRIC 追踪', 'RUN → CASE → METRIC TRACE')}</strong></div>
          <span>{text(`${proof?.runs.length ?? 0} 次正式 Run`, `${proof?.runs.length ?? 0} formal runs`)}</span>
        </div>
        <div className="proof-run-rail">
          {(proof?.runs ?? []).map((run, index) => {
            const active = run.benchmark_run_id === activeRunId
            return (
              <button key={run.benchmark_run_id} className={active ? 'active' : ''} onClick={() => { setSelectedRunId(run.benchmark_run_id); if (compareRunId === run.benchmark_run_id) setCompareRunId(null) }}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div><small>{run.suite_ref}</small><strong>{text(`${run.passed_case_count}/${run.case_count} 个 CASES`, `${run.passed_case_count}/${run.case_count} CASES`)}</strong><em>{run.execution_mode} · {run.status}</em></div>
              </button>
            )
          })}
        </div>
        <AnimatePresence mode="wait">
          {activeRunId && (
            <motion.div
              key={activeRunId}
              className="proof-run-detail"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
            >
              {runQuery.isLoading ? (
                <div className="proof-run-loading"><ScanLine size={16} /> {text('解析冻结 Run', 'RESOLVING FROZEN RUN')}</div>
              ) : runQuery.isError ? (
                <div className="proof-run-loading error-block"><span>{String(runQuery.error.message)}</span><button className="recovery-action" onClick={() => void runQuery.refetch()}>{text('重试冻结 Run', 'RETRY FROZEN RUN')}</button></div>
              ) : runQuery.data ? (
                <>
                  <div className="proof-run-coordinate">
                    <div><small>RUN ID</small><strong className="mono">{runQuery.data.run.benchmark_run_id}</strong></div>
                    <div><small>WORLD COORDINATE</small><strong className="mono">{runQuery.data.run.world_snapshot_ref ?? text('未绑定', 'unbound')}</strong></div>
                    <div><small>ENVIRONMENT</small><strong>{runQuery.data.run.environment}</strong></div>
                  </div>
                  <div className="proof-compare-selector">
                    <div><small>{text('冻结 RUN 对照', 'FROZEN RUN CONTRAST')}</small><strong>{text('选择第二个正式 Run', 'SELECT A SECOND FORMAL RUN')}</strong></div>
                    <div>{(proof?.runs ?? []).filter((run) => run.benchmark_run_id !== activeRunId).map((run, index) => <button key={run.benchmark_run_id} className={compareRunId === run.benchmark_run_id ? 'active' : ''} onClick={() => setCompareRunId((current) => current === run.benchmark_run_id ? null : run.benchmark_run_id)}><span>{String(index + 1).padStart(2,'0')}</span><strong>{run.suite_ref}</strong><em>{run.passed_case_count}/{run.case_count}</em></button>)}</div>
                  </div>
                  <AnimatePresence>
                    {compareRunId && compareQuery.isLoading && <motion.div className="proof-run-compare-loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><ScanLine size={14} /> {text('解析对照 Run…', 'RESOLVING COMPARISON RUN…')}</motion.div>}
                    {compareRunId && compareQuery.data && <RunComparison left={runQuery.data} right={compareQuery.data} />}
                  </AnimatePresence>
                  <div className="proof-freeze-fingerprint">
                    <div><small>DEPLOYMENT</small><strong className="mono">{runQuery.data.deployment.deployment_revision_id}</strong><span>{runQuery.data.deployment.git_commit}</span></div>
                    <div><small>SCHEMA / VOCAB</small><strong>{runQuery.data.deployment.schema_revision}</strong><span>{runQuery.data.deployment.vocabulary_revision}</span></div>
                    <div><small>POLICY / CAPABILITY</small><strong>{runQuery.data.deployment.policy_revision}</strong><span>{runQuery.data.deployment.capability_registry_revision}</span></div>
                    <div><small>MODEL / CONFIG</small><strong>{runQuery.data.deployment.model_provider_revision}</strong><span className="mono">{runQuery.data.deployment.configuration_digest.slice(0, 18)}…</span></div>
                  </div>
                  <div className="proof-run-body">
                    <div className="proof-case-list">
                      <div className="proof-run-subhead"><small>{text('CASE RUNS', 'CASE RUNS')}</small><strong>{runQuery.data.cases.length}</strong></div>
                      {runQuery.data.cases.map((item) => (
                        <article
                          key={item.case_run_id}
                          className={item.case_run_id === selectedCaseRun?.case_run_id ? 'selected' : ''}
                          role="button"
                          tabIndex={0}
                          aria-pressed={item.case_run_id === selectedCaseRun?.case_run_id}
                          onClick={() => setSelectedCaseRunId(item.case_run_id)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault()
                              setSelectedCaseRunId(item.case_run_id)
                            }
                          }}
                        >
                          <span className={`proof-case-state state-${item.status}`} />
                          <div><small>{item.case_ref}</small><strong>{item.status}</strong><em className="mono">{item.case_run_id}</em></div>
                          <div className="proof-case-coordinates">
                            {item.task_run_id && <button onClick={(event) => {
                              event.stopPropagation()
                              const query = new URLSearchParams({
                                run: item.task_run_id!,
                                from: 'proof',
                                proofRun: runQuery.data.run.benchmark_run_id,
                                caseRun: item.case_run_id,
                              })
                              navigate(`/agents?${query.toString()}`)
                            }}>task {item.task_run_id.slice(0, 8)}</button>}
                            {item.execution_id && <span>execution {item.execution_id.replace('execution:', '').slice(0, 8)}</span>}
                            {item.decision_ref && <span>decision {item.decision_ref.slice(0, 12)}</span>}
                          </div>
                        </article>
                      ))}
                    </div>
                    <div className="proof-case-inspector">
                      <div className="proof-run-subhead"><small>CASE FREEZE COORDINATE</small><strong>{selectedCaseRun ? text('已绑定', 'BOUND') : text('空', 'EMPTY')}</strong></div>
                      {selectedCaseRun && (
                        <>
                          <div className="proof-case-freeze-grid">
                            <div><small>CASE RUN</small><strong className="mono">{selectedCaseRun.case_run_id}</strong></div>
                            <div><small>REPLAY CHECKPOINT</small><strong className="mono">{selectedCaseRun.replay_checkpoint_ref ?? text('无', 'none')}</strong></div>
                            <div><small>EXECUTION</small><strong className="mono">{selectedCaseRun.execution_id ?? text('无', 'none')}</strong></div>
                            <div><small>DECISION</small><strong className="mono">{selectedCaseRun.decision_ref ?? text('无', 'none')}</strong></div>
                          </div>
                          {selectedCaseRun.target_refs.length > 0 && <div className="proof-target-ref-strip"><small>{text('冻结目标', 'FROZEN TARGETS')}</small><div>{selectedCaseRun.target_refs.map((ref) => {
                            const path = proofTargetPath(ref, runQuery.data.run.benchmark_run_id, selectedCaseRun.case_run_id)
                            return path ? <button key={ref} onClick={() => navigate(path)}><BrainCircuit size={11} /><span>{proofTargetLabel(ref)}</span><b className="mono">{ref}</b></button> : <span key={ref} className="mono">{ref}</span>
                          })}</div></div>}
                          <div className="proof-artifact-stack">
                            <small>{text('冻结 ARTIFACT REFS', 'ARTIFACT REFS')}</small>
                            <div>{selectedCaseRun.artifact_refs.length ? selectedCaseRun.artifact_refs.map((ref) => <span key={ref} className="mono">{ref}</span>) : <span>{text('没有冻结 artifact refs', 'no frozen artifact refs')}</span>}</div>
                          </div>
                        </>
                      )}
                      <div className="proof-run-subhead metric-subhead"><small>{text('METRIC OBSERVATIONS', 'METRIC OBSERVATIONS')}</small><strong>{runQuery.data.metrics.length}</strong></div>
                      <div className="proof-metric-list">
                        {runQuery.data.metrics.map((item) => (
                          <article key={item.metric_observation_id} className={selectedCaseRun && item.case_run_id !== selectedCaseRun.case_run_id ? 'metric-dimmed' : ''}>
                            <div><small>{item.measurement_source}</small><strong>{item.metric_name}</strong><em>{formatNumber(item.value)}{item.unit ? ` ${item.unit}` : ''}</em></div>
                            <div className="proof-metric-refs">
                              {item.evidence_refs.length === 0 ? <span>0 refs</span> : item.evidence_refs.slice(0, 3).map((ref) => (
                                ref.startsWith('evidence:') ? (
                                  <button key={ref} onClick={() => setSelectedEvidenceRef(ref)} title={ref}><Link2 size={10} /> {text('证据', 'EVIDENCE')}</button>
                                ) : (
                                  <span key={ref} className="proof-artifact-ref" title={ref}>{proofRefKind(ref)}</span>
                                )
                              ))}
                              {item.evidence_refs.length > 3 && <span>+{item.evidence_refs.length - 3}</span>}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </motion.div>
          )}
        </AnimatePresence>
        <AnimatePresence>
          {selectedEvidenceRef && (
            <motion.aside
              className="proof-evidence-lens"
              initial={{ opacity: 0, x: 26 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 18 }}
            >
              <button className="proof-evidence-close" onClick={() => setSelectedEvidenceRef(null)} aria-label={text('关闭证据', 'Close evidence')}><X size={14} /></button>
              <small>METRIC → EVIDENCE</small>
              <strong className="mono">{selectedEvidenceRef}</strong>
              {evidenceQuery.isLoading ? (
                <div className="proof-evidence-state">{text('解析 Evidence', 'RESOLVING EVIDENCE')}</div>
              ) : evidenceQuery.isError ? (
                <div className="proof-evidence-state error-block"><span>{String(evidenceQuery.error.message)}</span><button className="recovery-action" onClick={() => void evidenceQuery.refetch()}>{text('重试 Evidence', 'RETRY EVIDENCE')}</button></div>
              ) : evidenceQuery.data ? (
                <div className="proof-evidence-body">
                  <div><small>SOURCE</small><strong>{evidenceQuery.data.source.source_id}</strong><span>{evidenceQuery.data.source.source_role} · {evidenceQuery.data.source.source_class}</span></div>
                  <div><small>{text('绑定目标', 'BOUND TARGET')}</small><strong>{evidenceQuery.data.target.label}</strong><span>{evidenceQuery.data.target.target_kind}</span></div>
                  <div><small>OBSERVED</small><strong>{new Date(evidenceQuery.data.observation.observed_at).toLocaleString()}</strong><span className="mono">{evidenceQuery.data.observation.external_revision ?? 'content-addressed'}</span></div>
                  <div><small>LOCATOR</small><strong className="mono">{Object.entries(evidenceQuery.data.locator).map(([key, value]) => `${key}=${String(value)}`).join(' · ') || 'root'}</strong></div>
                  {evidenceBoundObjectIds(evidenceQuery.data).length > 0 && <div className="evidence-object-links"><small>{text('绑定对象', 'BOUND OBJECTS')}</small><div>{evidenceBoundObjectIds(evidenceQuery.data).map((objectId, index) => <button key={objectId} onClick={() => navigate(`/intelligence?object=${encodeURIComponent(objectId)}&from=proof`)}><BrainCircuit size={11} /> {index === 0 ? text('打开主体档案', 'OPEN SUBJECT DOSSIER') : text('打开关系对象', 'OPEN RELATED OBJECT')}<span className="mono">{compactEvidenceObjectRef(objectId)}</span></button>)}</div></div>}
                  {evidenceQuery.data.observation.canonical_url && <a href={evidenceQuery.data.observation.canonical_url} target="_blank" rel="noreferrer">{text('打开规范来源', 'OPEN CANONICAL SOURCE')}</a>}
                </div>
              ) : null}
            </motion.aside>
          )}
        </AnimatePresence>
      </section>

      <div className="proof-grid">
        <ProofBlock title="M1 · MONITORING" eyebrow="MULTI-SOURCE OPERATIONS" tone="cyan" icon={RadioTower}>
          <ProofNumber label="≤ 6H RATE" value={proofMetric(metric('m1.monitoring.within_6h_rate'))} />
          <ProofNumber label="SOURCE DELIVERY COVERAGE" value={proofMetric(metric('m1.source_delivery_coverage'))} warning />
          <p className="proof-note warning-note"><TriangleAlert size={13} /> {text('Coverage 缺口持续保留。延迟达标不会抹掉缺失的 delivery keys。', 'Coverage weakness stays visible. Passing latency does not erase missing delivery keys.')}</p>
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
          <PanelHead eyebrow="COMPETITION TARGETS" title={text('目标检查', 'TARGET CHECKS')} meta={text(`${proof?.target_checks.length ?? 0} 项`, `${proof?.target_checks.length ?? 0} checks`)} icon={ShieldCheck} />
          <div className="target-check-list">{(proof?.target_checks ?? []).map((item) => <div key={item.target_name} className={`target-check ${item.status}`}><span className="target-icon"><BadgeCheck size={15} /></span><div><small>{item.target_name}</small><strong>{item.requirement}</strong><span>{item.metric_name} · observed {formatNumber(item.observed_value)} {item.comparator} {formatNumber(item.threshold)}</span></div><b>{item.status}</b></div>)}</div>
        </section>
        <section className="proof-boundary">
          <PanelHead eyebrow="MEASUREMENT BOUNDARY" title={text('不可伪造的测量边界', 'WHAT WE REFUSE TO FAKE')} meta={text(`${proof?.partial_metric_groups ?? 0} 个 partial groups`, `${proof?.partial_metric_groups ?? 0} partial groups`)} icon={TriangleAlert} />
          <div className="core-metric-ring"><span>{proof ? Math.round(proof.observed_core_metrics / proof.registered_core_metrics * 100) : 0}%</span><small>{text('已观测核心 METRICS', 'CORE METRICS OBSERVED')}</small></div>
          <div className="unevaluated-list">{(proof?.unevaluated_core_metrics ?? []).map((name) => <div key={name}><span className="unevaluated-dot" /><strong>{name}</strong><small>{text('精确货币成本 · 未推断', 'exact monetary cost · not inferred')}</small></div>)}</div>
          <p>{text('Provider / Capability 的精确货币成本等待真实 provider 或 executor 报告。Token 数不会乘公开价格表后冒充测量事实。', 'Exact provider / capability monetary cost stays unavailable until the provider or executor reports it. Token counts are never multiplied by public price tables and presented as fact.')}</p>
        </section>
      </div>
    </>
  )
}

function RunComparison({ left, right }: { left: ProofRunDetail; right: ProofRunDetail }) {
  const { text } = useI18n()
  const pairedMetrics = pairRunMetrics(left, right)
  const sharedCases = new Set(left.cases.map((item) => item.case_ref))
  const sharedCaseCount = right.cases.filter((item) => sharedCases.has(item.case_ref)).length
  const deploymentFields = [
    ['GIT', left.deployment.git_commit, right.deployment.git_commit],
    ['SCHEMA', left.deployment.schema_revision, right.deployment.schema_revision],
    ['VOCAB', left.deployment.vocabulary_revision, right.deployment.vocabulary_revision],
    ['POLICY', left.deployment.policy_revision, right.deployment.policy_revision],
    ['CAPABILITY', left.deployment.capability_registry_revision, right.deployment.capability_registry_revision],
    ['MODEL', left.deployment.model_provider_revision, right.deployment.model_provider_revision],
    ['CONFIG', left.deployment.configuration_digest, right.deployment.configuration_digest],
  ] as const
  const changedDeploymentFields = deploymentFields.filter(([, leftValue, rightValue]) => leftValue !== rightValue)
  const sameWorld = left.run.world_snapshot_ref === right.run.world_snapshot_ref

  return (
    <motion.section
      className="proof-run-contrast"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: .22 }}
    >
      <div className="proof-run-contrast-head">
        <div>
          <small>{text('冻结 RUN 对照', 'FROZEN RUN CONTRAST')}</small>
          <strong>{text('同一证据表面上的可复验差异', 'REPRODUCIBLE DIFFERENCE ON THE SAME PROOF SURFACE')}</strong>
        </div>
        <span className={sameWorld ? 'coordinate-same' : 'coordinate-shift'}>
          {sameWorld ? text('同一 WORLD COORDINATE', 'SAME WORLD COORDINATE') : text('WORLD COORDINATE 已变化', 'WORLD COORDINATE SHIFTED')}
        </span>
      </div>

      <div className="proof-run-contrast-axis" aria-label={text('Run 对照坐标', 'Run comparison coordinates')}>
        <RunContrastCoordinate label="A" run={left} />
        <div className="proof-run-contrast-spine">
          <span />
          <b>Δ</b>
          <span />
        </div>
        <RunContrastCoordinate label="B" run={right} />
      </div>

      <div className="proof-run-contrast-facts">
        <div><small>{text('共享 CASE', 'SHARED CASES')}</small><strong>{sharedCaseCount}</strong><span>{text('按 case_ref 对齐', 'aligned by case_ref')}</span></div>
        <div><small>{text('成对 METRIC', 'PAIRED METRICS')}</small><strong>{pairedMetrics.length}</strong><span>{text('同 Case / 同 metric / 同 measurement source', 'same case / metric / measurement source')}</span></div>
        <div><small>{text('部署差异', 'DEPLOYMENT DIFF')}</small><strong>{changedDeploymentFields.length}</strong><span>{changedDeploymentFields.length ? changedDeploymentFields.map(([label]) => label).join(' · ') : text('冻结部署一致', 'frozen deployment identical')}</span></div>
      </div>

      {changedDeploymentFields.length > 0 && (
        <div className="proof-run-deployment-diff">
          {changedDeploymentFields.map(([label, leftValue, rightValue]) => (
            <div key={label}>
              <small>{label}</small>
              <span className="mono" title={leftValue}>{compactCoordinate(leftValue)}</span>
              <i aria-hidden="true">→</i>
              <span className="mono" title={rightValue}>{compactCoordinate(rightValue)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="proof-run-metric-contrast">
        <div className="proof-run-metric-contrast-head">
          <small>{text('共享 METRIC OBSERVATIONS', 'SHARED METRIC OBSERVATIONS')}</small>
          <span>{text('仅显示可按冻结 Case 与 measurement source 精确配对的观测', 'only observations exactly pairable by frozen Case and measurement source')}</span>
        </div>
        {pairedMetrics.length ? pairedMetrics.slice(0, 12).map((pair) => (
          <div className="proof-run-metric-row" key={pair.key}>
            <div><small>{pair.caseRef}</small><strong>{pair.left.metric_name}</strong><span>{pair.left.measurement_source}</span></div>
            <b>{formatObservedMetric(pair.left)}</b>
            <em className={Math.abs(pair.delta) < 1e-12 ? 'delta-zero' : pair.delta > 0 ? 'delta-positive' : 'delta-negative'}>{formatMetricDelta(pair.delta, pair.left.unit)}</em>
            <b>{formatObservedMetric(pair.right)}</b>
          </div>
        )) : (
          <div className="proof-run-metric-empty">{text('两个 Run 没有可精确配对的 MetricObservation；保持空白，不做聚合推断。', 'No MetricObservation can be paired exactly across these runs; the contrast stays empty rather than inventing an aggregate.')}</div>
        )}
      </div>
    </motion.section>
  )
}

function RunContrastCoordinate({ label, run }: { label: string; run: ProofRunDetail }) {
  const { text } = useI18n()
  return (
    <div className="run-contrast-coordinate">
      <span>{label}</span>
      <div>
        <small>{run.run.suite_ref}</small>
        <strong className="mono">{run.run.benchmark_run_id}</strong>
        <em>{run.run.passed_case_count}/{run.run.case_count} {text('通过', 'passed')} · {run.run.environment}</em>
      </div>
      <b className="mono" title={run.run.world_snapshot_ref ?? text('未绑定', 'unbound')}>{compactCoordinate(run.run.world_snapshot_ref ?? text('未绑定', 'unbound'))}</b>
    </div>
  )
}

function pairRunMetrics(left: ProofRunDetail, right: ProofRunDetail) {
  const leftCaseRefs = new Map(left.cases.map((item) => [item.case_run_id, item.case_ref]))
  const rightCaseRefs = new Map(right.cases.map((item) => [item.case_run_id, item.case_ref]))
  const rightIndex = new Map<string, ProofMetricObservation>()
  for (const metric of right.metrics) {
    const caseRef = rightCaseRefs.get(metric.case_run_id)
    if (!caseRef) continue
    rightIndex.set(`${caseRef}\u0000${metric.metric_name}\u0000${metric.measurement_source}`, metric)
  }

  return left.metrics.flatMap((metric) => {
    const caseRef = leftCaseRefs.get(metric.case_run_id)
    if (!caseRef) return []
    const key = `${caseRef}\u0000${metric.metric_name}\u0000${metric.measurement_source}`
    const matched = rightIndex.get(key)
    if (!matched || matched.unit !== metric.unit) return []
    return [{ key, caseRef, left: metric, right: matched, delta: matched.value - metric.value }]
  }).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.left.metric_name.localeCompare(b.left.metric_name))
}

function compactCoordinate(value: string) {
  return value.length > 34 ? `${value.slice(0, 15)}…${value.slice(-11)}` : value
}

function formatObservedMetric(metric: ProofMetricObservation) {
  if (metric.unit === 'ratio') return pct(metric.value)
  if (metric.unit === 'seconds') return `${metric.value.toFixed(metric.value < 10 ? 3 : 2)}s`
  return `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ''}`
}

function formatMetricDelta(value: number, unit: string | null) {
  if (Math.abs(value) < 1e-12) return 'Δ 0'
  const sign = value > 0 ? '+' : '−'
  const magnitude = Math.abs(value)
  if (unit === 'ratio') return `Δ ${sign}${(magnitude * 100).toFixed(2)}pp`
  if (unit === 'seconds') return `Δ ${sign}${magnitude.toFixed(magnitude < 10 ? 3 : 2)}s`
  return `Δ ${sign}${formatNumber(magnitude)}${unit ? ` ${unit}` : ''}`
}

function TelemetryChart({ title, series, lines }: { title: string; series: Array<Record<string, number | string | null>>; lines: Array<{ key: string; label: string; tone: string }> }) {
  const { text } = useI18n()
  const reduceMotion = Boolean(useReducedMotion())
  const width = 520
  const height = 150
  const allValues = lines.flatMap((line) => series.map((item) => numeric(item[line.key]))).filter((value) => Number.isFinite(value))
  const max = Math.max(...allValues, 1)
  const paths = lines.map((line) => ({ ...line, d: linePath(series.map((item) => numeric(item[line.key])), width, height, max) }))
  const lastSample = series.at(-1)
  const revision = String(lastSample?.hour ?? lastSample?.timestamp ?? lastSample?.generated_at ?? series.length)
  return <div className={`telemetry-chart ${series.length ? '' : 'chart-unresolved'}`}><div className="chart-head"><strong>{title}</strong><div>{lines.map((line) => <span key={line.key} className={`tone-${line.tone}`}><i />{line.label}</span>)}</div></div><div className="chart-canvas"><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><defs><linearGradient id={`fade-${title.replaceAll(' ', '-')}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".16"/><stop offset="1" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>{[.25,.5,.75].map((part) => <line key={part} x1="0" x2={width} y1={height * part} y2={height * part} className="chart-gridline" />)}{paths.map((path) => <motion.path key={`${path.key}:${revision}`} className={`chart-line tone-${path.tone}`} d={path.d} fill="none" initial={reduceMotion ? false : { pathLength: 0, opacity: .28 }} animate={{ pathLength: 1, opacity: 1 }} transition={{ duration: reduceMotion ? 0 : .58, ease: [0.22, 1, 0.36, 1] }} />)}</svg>{series.length === 0 && <div className="chart-await"><ScanLine size={16}/><strong>{text('等待运行样本', 'AWAITING OPERATIONAL SAMPLES')}</strong><small>{text('保留测量网格 · 不生成合成曲线', 'grid retained · no synthetic curve')}</small></div>}<div className="chart-scanline" /></div></div>
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
          <div className="agent-spectrum-offline">{text('RUNTIME 离线', 'RUNTIME OFFLINE')}</div>
        </div>
      ))}
    </>
  )
}

function LiveMetric({ icon: Icon, label, value, detail, tone, active, onClick }: { icon: typeof Activity; label: string; value: string; detail: string; tone: string; active?: boolean; onClick?: () => void }) { return <button type="button" className={`live-metric tone-${tone} ${active ? 'focus-selected' : ''}`} onClick={onClick}><span className="live-metric-icon"><Icon size={17} /></span><div><small>{label}</small><strong>{value}</strong><span>{detail}</span></div></button> }
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
