# Evaluation infrastructure status

Snapshot `2026-10-02T20:29:31.736620+00:00`. This is an infrastructure/readiness projection, not a competition score.
Observation readiness is evaluated against the current MetricDefinition revision. Older observations remain historical evidence but do not satisfy a revised contract.

## Metric contract coverage

| Group | Owner | Implementation | Observation status | Observed / Contract | Open metrics |
| --- | --- | --- | --- | ---: | --- |
| `m1.competition` | M1 + M7 | `runner_ready` | **observed** | 7/7 | — |
| `m6.session` | M6 + M7 | `runner_ready` | **partial** | 4/5 | `m6.session_retrieval_overlap_rate` |
| `m2.diagnostics` | M2 + M7 | `runner_ready` | **observed** | 6/6 | — |
| `m3.competition` | M3 + M7 | `runner_ready` | **observed** | 7/7 | — |
| `m6.qa` | M6 + M7 | `runner_ready` | **observed** | 9/9 | — |
| `m6.long_investigation` | M5/M6 + M7 | `runner_ready` | **observed** | 6/6 | — |
| `m5.requirements_runtime` | M5 + M7 | `runner_ready` | **partial** | 5/9 | `agent.capability_selection_correctness`, `agent.argument_correctness`, `agent.recovery_success_rate`, `runtime.model_provider_cost` |
| `m5.gap_acquisition` | M5 + M7 | `scorer_ready` | **contract_ready** | 0/6 | `agent.critical_evidence_need_recall`, `agent.false_gap_rate`, `agent.useful_acquisition_precision`, `agent.redundant_acquisition_rate`, `agent.source_role_satisfaction`, `agent.freshness_satisfaction` |
| `m5.state_integration` | M4/M5 + M7 | `runner_ready` | **partial** | 2/4 | `agent.wrong_version_attachment_rate`, `agent.conflict_collapse_rate` |
| `m5.planning_tool` | M5 + M7 | `scorer_ready` | **contract_ready** | 0/5 | `agent.capability_selection_correctness`, `agent.argument_correctness`, `agent.unnecessary_denied_request_rate`, `agent.fallback_success_rate`, `agent.capability_invocation_count` |
| `m5.delegation` | M5 + M7 | `scorer_ready` | **contract_ready** | 0/4 | `agent.delegation_precision`, `agent.child_task_usefulness`, `agent.parent_child_budget_adherence`, `agent.stale_child_result_rate` |
| `m5.stop` | M5/M6 + M7 | `runner_ready` | **partial** | 2/4 | `agent.no_progress_iteration_rate`, `agent.budget_deadline_stop_correctness` |
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
| `benchmark_runs` | 100 |
| `benchmark_case_runs` | 390 |
| `metric_observations` | 5898 |
| `task_runs` | 134 |
| `task_events` | 787 |
| `execution_runs` | 61 |
| `trajectory_events` | 0 |
| `capability_invocations` | 0 |
| `retrieval_invocations` | 2 |
| `model_requests` | 58 |
| `model_attempts` | 58 |
| `prompt_assembly_records` | 11 |
| `decision_results` | 40 |
| `evidence_links` | 4401 |
| `observations` | 1110 |
| `evidence_artifacts` | 1110 |

## Provenance closure

| Check | Coverage |
| --- | ---: |
| CaseRun has artifact refs | 25.6% |
| CaseRun can reach TaskRun | 11.5% |
| CaseRun can reach Execution | 11.5% |
| CaseRun can reach Decision | 11.0% |
| All MetricObservation rows carrying EvidenceRefs | 4.6% |
| Citation/groundedness metrics carrying EvidenceRefs | 4.4% |

A low global metric→Evidence rate is not automatically a defect: latency/count/runtime metrics do not require EvidenceRefs. Citation/groundedness metrics do, so that row is the stronger evidence-chain readiness check.

## Frozen model-input replay readiness

| Artifact boundary | Coverage |
| --- | ---: |
| ModelRequest request artifact | 31.0% |
| ModelAttempt response artifact | 31.0% |
| PromptAssembly request artifact | 72.7% |

These three rows expose the R1 replay gap directly. Hashes/metadata alone support audit identity, but exact frozen model-input replay requires durable normalized request/response artifacts.

## Latest live QA provenance closure

BenchmarkRun `6cf10dd4-37f0-4131-ae32-367389437472` / `m6-eval-infra-trace-20261002@9`.

| Check | Coverage |
| --- | ---: |
| Citation/groundedness metrics → EvidenceRefs | 100.0% |
| ModelRequest → durable request artifact | 100.0% |
| Successful ModelAttempt → durable response artifact | 100.0% |
| Runtime MetricObservation rows | 7 |

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
