# Evaluation Infrastructure Status

This directory is the generated readiness/audit view for M7/TD3 itself. It is not a competition score and it never fills missing benchmark metrics with zeros.

`current.json` answers three questions from durable state: which Requirements/TD3 metric contracts are registered versus actually observed, which trace owners currently contain records, and how far BenchmarkCaseRun / MetricObservation provenance can be followed toward runtime and Evidence. `current.md` is a deterministic renderer over that JSON.

The metric catalog is owned by `packages.evaluation.metric_contract`; every listed name must resolve to an immutable `MetricDefinition`. The generated table shows two independent axes. `implementation` is `contract_only`, `scorer_ready`, or `runner_ready`; observation status is `contract_ready`, `partial`, or `observed` based on durable MetricObservation presence. A scorer-ready group with no frozen denominator therefore remains `contract_ready`, and an observed metric never implies that a competition threshold passed. Observation status is an infrastructure-wide substrate check, not a domain-specific competition score.

Observation status is computed against the **current MetricDefinition revision**, not merely by metric name. Historical observations from an older metric revision remain visible in `historical_observed_metric_counts`, but they do not satisfy current readiness after the denominator/scorer contract changes.

The provenance section distinguishes general artifact refs from evidence-bound metrics. Runtime latency/token/count metrics legitimately have no EvidenceRef; groundedness/citation metrics are expected to carry the EvidenceRefs used by the prediction. Exact frozen model-input replay is also kept separate: request/response hashes and model metadata do not substitute for durable normalized request/response artifacts.

Historical closure and current-runner closure are reported separately. Earlier BenchmarkRuns remain immutable evidence of earlier infrastructure gaps. A newly completed live QA run is inspected separately for citation metric → EvidenceRef binding, ModelRequest/ModelAttempt request/response artifacts, and runtime MetricObservation projection. Improving the runner never rewrites historical observations to make the cumulative percentage look better.

`scripts/query_benchmark_evidence.py` is the executable drill-down path. It accepts either a CompetitionReport or explicit `--run-id` / optional `--case-run-id` and expands:

```text
BenchmarkRun → CaseRun → TaskRun / ContextManifest / TaskEvent
             → ExecutionRun → ModelRequest / ModelAttempt / PromptAssembly
             → RuntimeArtifact / CapabilityInvocation / RetrievalInvocation
             → Decision / Investigation trajectory
             → EvidenceLink → Observation → EvidenceArtifact
```

`--require-closed` fails when a selected live case cannot resolve required model request/response artifacts, Context or retrieval coordinates, or when citation/groundedness metrics are not directly bound to EvidenceRefs. It is an audit gate, not a score.
