# Controlled M5 Agent runtime benchmark

Run `f92f0f4c-3296-42c7-ad9b-7e14284ef968` on `deployment:99a6169e04f3143e323baca720e0146e` / suite `m5-agent-runtime-controlled-v1@6`.

Scope: **controlled runtime regression, not a live-external Agent quality score**. Each case exercises the production owner for one M5 failure-chain property with deterministic fixtures and persists the result as TD3 BenchmarkRun/CaseRun/MetricObservation.

| Case | Metrics |
| --- | --- |
| `agent-perception-capability` | `agent.useful_acquisition_precision`=1.000, `agent.redundant_acquisition_rate`=0.000, `agent.source_role_satisfaction`=1.000, `agent.freshness_satisfaction`=1.000, `agent.capability_selection_correctness`=1.000, `agent.argument_correctness`=1.000, `agent.unnecessary_denied_request_rate`=0.000, `agent.capability_invocation_count`=1.000 |
| `agent-delegated-enrichment-resume` | `agent.delegation_precision`=1.000, `agent.child_task_usefulness`=1.000, `agent.parent_child_budget_adherence`=1.000, `agent.stale_child_result_rate`=0.000 |
| `agent-health-ranked-fallback` | `agent.fallback_success_rate`=1.000 |
| `agent-conflict-preservation` | `agent.conflict_collapse_rate`=0.000 |
| `agent-episode-recovery` | `agent.recovery_success_rate`=1.000 |
| `agent-no-progress-stop` | `agent.no_progress_iteration_rate`=0.667 |
| `agent-deadline-stop` | `agent.budget_deadline_stop_correctness`=1.000 |

The controlled denominator currently covers:

- Evidence acquisition usefulness/redundancy, source-role and freshness satisfaction;
- Capability selection, canonical arguments and invocation audit;
- Parent/child delegation, budget inheritance and dependency wake/resume;
- Health-ranked capability binding fallback before invocation;
- Conflict preservation in the M4 StatePatch gate;
- Failed InvestigationRole episode → same Case/EvidenceNeed → successful recovery episode;
- No-progress and pre-execution deadline bounded-stop behavior.

Health-ranked fallback does not claim automatic retry after an already-selected binding fails. Current TD2 semantics choose among eligible bindings using provider health and `fallback_rank`; invocation-failure retry would be a separate runtime policy.

Monetary provider/capability cost is not synthesized here. It remains `not_evaluated` unless the executing provider/capability returns an exact amount.
