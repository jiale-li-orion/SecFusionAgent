export type ProofRunSummary = {
  benchmark_run_id: string
  suite_ref: string
  deployment_revision_id: string
  world_snapshot_ref: string | null
  status: string
  execution_mode: string
  environment: string
  started_at: string
  finished_at: string | null
  case_count: number
  passed_case_count: number
}

export type ProofCaseRun = {
  case_run_id: string
  case_ref: string
  target_refs: string[]
  execution_profile: string | null
  status: string
  failure_class: string | null
  task_run_id: string | null
  execution_id: string | null
  decision_ref: string | null
  replay_checkpoint_ref: string | null
  artifact_refs: string[]
  started_at: string
  finished_at: string | null
}

export type ProofMetricObservation = {
  metric_observation_id: string
  metric_name: string
  value: number
  unit: string | null
  direction: string
  measurement_source: string
  case_run_id: string
  subject_ref: string | null
  evidence_refs: string[]
  created_at: string
}

export type ProofRunDetail = {
  run: ProofRunSummary
  deployment: {
    deployment_revision_id: string
    git_commit: string
    container_image_digest: string | null
    schema_revision: string
    source_inventory_hash: string
    vocabulary_revision: string
    policy_revision: string
    capability_registry_revision: string
    skill_registry_revision: string | null
    model_provider_revision: string
    configuration_digest: string
    created_at: string
  }
  cases: ProofCaseRun[]
  metrics: ProofMetricObservation[]
}

export async function getCompetitionProofRun(runId: string): Promise<ProofRunDetail> {
  const response = await fetch(`/api/v1/observatory/proof/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) throw new Error(response.status === 404 ? 'Benchmark run not found' : `Benchmark run unavailable (${response.status})`)
  return response.json() as Promise<ProofRunDetail>
}

export type CompetitionProof = {
  report_id: string
  report_digest: string
  deployment_revision_id: string
  generated_at: string
  benchmark_runs_completed: number
  case_runs_passed: number
  registered_core_metrics: number
  observed_core_metrics: number
  metric_groups: number
  observed_metric_groups: number
  partial_metric_groups: number
  unevaluated_core_metrics: string[]
  headline_metrics: Array<{
    metric_name: string
    value: number
    unit: string | null
    direction: string
  }>
  target_checks: Array<{
    target_name: string
    requirement: string
    metric_name: string
    observed_value: number
    threshold: number
    comparator: string
    status: string
  }>
  runs: ProofRunSummary[]
}

export async function getCompetitionProof(): Promise<CompetitionProof> {
  const response = await fetch('/api/v1/observatory/proof')
  if (!response.ok) throw new Error(`Competition proof unavailable (${response.status})`)
  return response.json() as Promise<CompetitionProof>
}
