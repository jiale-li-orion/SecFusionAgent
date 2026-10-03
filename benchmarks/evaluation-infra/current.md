# Evaluation infrastructure status

Snapshot `2026-10-03T11:20:37.946350+00:00`. This is an infrastructure/readiness projection, not a competition score.
Observation readiness is evaluated against the current MetricDefinition revision. Older observations remain historical evidence but do not satisfy a revised contract.

## Metric contract coverage

| Group | Owner | Implementation | Observation status | Observed / Contract | Open metrics |
| --- | --- | --- | --- | ---: | --- |
| `m1.competition` | M1 + M7 | `runner_ready` | **observed** | 7/7 | — |
| `m6.session` | M6 + M7 | `runner_ready` | **observed** | 5/5 | — |
| `m2.diagnostics` | M2 + M7 | `runner_ready` | **observed** | 6/6 | — |
| `m3.competition` | M3 + M7 | `runner_ready` | **observed** | 7/7 | — |
| `m6.qa` | M6 + M7 | `runner_ready` | **observed** | 9/9 | — |
| `m6.long_investigation` | M5/M6 + M7 | `runner_ready` | **observed** | 6/6 | — |
| `m5.requirements_runtime` | M5 + M7 | `runner_ready` | **partial** | 8/9 | `runtime.model_provider_cost` |
| `m5.gap_acquisition` | M5 + M7 | `runner_ready` | **observed** | 6/6 | — |
| `m5.state_integration` | M4/M5 + M7 | `runner_ready` | **observed** | 4/4 | — |
| `m5.planning_tool` | M5 + M7 | `runner_ready` | **observed** | 5/5 | — |
| `m5.delegation` | M5 + M7 | `runner_ready` | **observed** | 4/4 | — |
| `m5.stop` | M5/M6 + M7 | `runner_ready` | **observed** | 4/4 | — |
| `runtime.economics` | TD3 measurement | `runner_ready` | **partial** | 7/9 | `runtime.model_provider_cost`, `runtime.capability_external_cost` |
| `retrieval.execution` | Retrieval + M7 | `runner_ready` | **observed** | 2/2 | — |
| `security.hard_gates` | M7 security | `runner_ready` | **observed** | 3/3 | — |
| `security.adversarial_suite` | M7 security | `runner_ready` | **observed** | 2/2 | — |
| `engineering.recovery` | M8 + M7 | `runner_ready` | **observed** | 4/4 | — |

## Next legal denominators

- `m6.session`: Multi-turn RETRIEVE sessions whose initial and follow-up turns both resolve non-empty document-chunk refs; empty-result cache reuse does not define retrieval overlap.
- `m5.requirements_runtime`: Frozen Agent cases that naturally exercise CapabilityBroker selection/arguments and recoverable failures; monetary cost remains absent until the provider reports it exactly.
- `m5.gap_acquisition`: Frozen cases where the Agent itself must identify/open a critical EvidenceNeed and perform an acquisition under pre-frozen source-role and freshness constraints.
- `m5.state_integration`: Frozen conflict-bearing Investigation cases whose competing durable assertions are known before Agent state integration.
- `m5.planning_tool`: External-capability Agent cases with pre-frozen acceptable capability ids, canonical argument digests, policy-denial expectations and primary/fallback binding outcomes.
- `m5.delegation`: Cases where missing evidence legitimately requires child-task delegation; freeze child usefulness, parent budget ceiling and context-staleness expectations before execution.
- `m5.stop`: Short-budget/deadline or repeated-no-progress Investigation cases with expected bounded stop/continue behavior frozen before execution.
- `runtime.economics`: Provider responses that expose exact monetary cost plus real CapabilityBroker calls whose executor reports exact external cost; never infer missing money from price tables.

## Durable trace substrate

| Owner record | Rows |
| --- | ---: |
| `benchmark_runs` | 124 |
| `benchmark_case_runs` | 509 |
| `metric_observations` | 7935 |
| `task_runs` | 195 |
| `task_events` | 1035 |
| `execution_runs` | 122 |
| `trajectory_events` | 0 |
| `capability_invocations` | 0 |
| `retrieval_invocations` | 10 |
| `model_requests` | 121 |
| `model_attempts` | 121 |
| `prompt_assembly_records` | 16 |
| `decision_results` | 92 |
| `evidence_links` | 5131 |
| `observations` | 1349 |
| `evidence_artifacts` | 1349 |

## Provenance closure

| Check | Coverage |
| --- | ---: |
| CaseRun has artifact refs | 30.5% |
| CaseRun can reach TaskRun | 18.9% |
| CaseRun can reach Execution | 18.9% |
| CaseRun can reach Decision | 17.7% |
| All MetricObservation rows carrying EvidenceRefs | 9.2% |
| Citation/groundedness metrics carrying EvidenceRefs | 53.6% |

A low global metric→Evidence rate is not automatically a defect: latency/count/runtime metrics do not require EvidenceRefs. Citation/groundedness metrics do, so that row is the stronger evidence-chain readiness check.

## Frozen model-input replay readiness

| Artifact boundary | Coverage |
| --- | ---: |
| ModelRequest request artifact | 66.1% |
| ModelAttempt response artifact | 65.3% |
| PromptAssembly request artifact | 81.2% |

These three rows expose the R1 replay gap directly. Hashes/metadata alone support audit identity, but exact frozen model-input replay requires durable normalized request/response artifacts.

## Latest live QA provenance closure

BenchmarkRun `99da1f9b-441b-465c-a962-76549a7741c7` / `m6-real-product-qa-session@10`.

| Check | Coverage |
| --- | ---: |
| Citation/groundedness metrics → EvidenceRefs | 100.0% |
| ModelRequest → durable request artifact | 100.0% |
| Successful ModelAttempt → durable response artifact | 100.0% |
| Runtime MetricObservation rows | 28 |

This scope is intentionally separate from the historical cumulative rows above: old BenchmarkRuns remain immutable evidence of earlier infrastructure gaps, while the latest live run shows whether the current runner contract is closed.

## Latest live Long Investigation provenance closure

BenchmarkRun `21249f0f-80e5-4d53-a191-c8ca16e1ecd4` / `m6-long-investigation-harness-fixed-20261003@2`.

| Check | Coverage |
| --- | ---: |
| M5 planner ModelRequest → durable request artifact | 100.0% |
| M5 planner successful ModelAttempt → durable response artifact | 100.0% |
| PromptAssembly → direct request artifact binding | 100.0% |
| M6 Decision requests with an ExecutionRun coordinate | 100.0% |
| Execution-owned M6 Decision request artifact | 100.0% |
| Decision EvidenceRef → Observation → EvidenceArtifact | 100.0% |

M5 planner artifacts are execution-owned and therefore required for current runs. Standalone Case-owned M6 Decision calls currently have no independent ExecutionRun; their raw payload artifact rate is shown as not applicable rather than inventing a new Task/Execution owner. Historical episode debt is never backfilled.

## Status semantics

- `observed`: every metric in the group has at least one durable MetricObservation.
- `partial`: the contract exists and some metrics have real observations, but the group is not complete.
- `contract_ready`: all metric definitions are registered, while a real frozen denominator/runner is still absent.

Use `scripts/query_benchmark_evidence.py` with a CompetitionReport or explicit `--run-id`; `--require-closed` fails when the selected live trace cannot resolve its model/runtime/Evidence chain.
