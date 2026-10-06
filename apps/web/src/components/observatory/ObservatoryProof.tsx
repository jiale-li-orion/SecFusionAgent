import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { useNavigate } from 'react-router-dom'
import { Activity, Archive, BadgeCheck, BrainCircuit, DatabaseZap, Link2, RadioTower, ScanLine, ShieldCheck, TriangleAlert, Waypoints, X } from 'lucide-react'

import { evidenceBoundObjectIds, getCompetitionProofRun, getEvidence, type CompetitionProof, type ProofRunDetail } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import { compactCoordinate, compactEvidenceObjectRef, formatMetricDelta, formatNumber, formatObservedMetric, pairRunMetrics, proofMetric, proofRefKind, proofTargetLabel, proofTargetPath, rawMetric } from '../../lib/observatoryPresentation'
import { PanelHead } from './ObservatoryPrimitives'

export function ProofObservatory({ proof, loading, preferredRunId, preferredCaseRunId }: { proof: CompetitionProof | null; loading: boolean; preferredRunId: string | null; preferredCaseRunId: string | null }) {
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

function ProofBlock({ title, eyebrow, tone, icon: Icon, children }: { title: string; eyebrow: string; tone: string; icon: typeof Activity; children: React.ReactNode }) { return <motion.section className={`proof-block tone-${tone}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><div className="proof-block-head"><span><Icon size={16} /></span><div><small>{eyebrow}</small><strong>{title}</strong></div></div><div className="proof-block-body">{children}</div></motion.section> }

function ProofNumber({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) { return <div className={`proof-number ${warning ? 'warning' : ''}`}><small>{label}</small><strong>{value}</strong></div> }

function ProofSealStat({ value, label }: { value: string; label: string }) { return <div><strong>{value}</strong><small>{label}</small></div> }
