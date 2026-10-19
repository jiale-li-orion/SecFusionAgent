<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

Profile: **preliminary**. Numeric checks do not assign qualitative rubric points.
Source category support requires separate real-time operational evidence.

- Report: `20fcc81a-cbef-46b6-9d90-a30a8498a4a9`
- Digest: `5684a71fc07f015bf5d1dc71bb1726beab4de7aa25cb44280c8030a76bfc711e`
- Deployment: `deployment:056e482bdb3598135b48cb6c192e5e2a`
- Benchmark runs: `5246ac59-9f97-4458-b780-efe63dda2799`, `3bc6320f-16db-4af3-9d2d-9649d9f06d6a`, `1ba81c21-bef9-4419-b0a8-264907798dd9`, `437981bf-27f7-49bb-87d3-c67e3aeebc9d`, `56cfbb86-de40-4033-abc7-9ba6b616000c`, `d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2`, `205df724-1232-4700-8b2b-e3764e4d4a2a`, `40afd9cb-9b61-425b-9045-52add6e1a1ee`, `69cdc26d-72f0-4ccc-a466-08c90d48071d`, `2f9000dd-154b-402d-9d4f-69af09dce629`
- Generated at: `2026-10-17T12:04:15.016859+00:00`

## Competition target checks

| Target | Metric | Observed | Requirement | Status |
| --- | --- | ---: | --- | --- |
| source_category_coverage | `m1.source_category_count` | 8 | >= 7 | **pass** |
| monitoring_timeliness | `m1.monitoring.max_seconds` | 1.3454e+08 | <= 21600 | **fail** |
| enrichment_precision | `m3.micro_precision` | 0.996587 | >= 0.95 | **pass** |
| qa_multihop | `m6.multi_hop_correctness` | 0.961538 | >= 0.85 | **pass** |

source_category_coverage: Category support only; real-time monitoring requires separate operational review.

## Metrics

| Metric | Value | Unit | Definition | Aggregation | Cases |
| --- | ---: | --- | --- | --- | ---: |
| `agent.argument_correctness` | 1 | ratio | `@1` | mean | 1 |
| `agent.budget_deadline_stop_correctness` | 1 | ratio | `@1` | mean | 1 |
| `agent.capability_invocation_count` | 1 | calls | `@1` | mean | 1 |
| `agent.capability_selection_correctness` | 1 | ratio | `@1` | mean | 1 |
| `agent.child_task_usefulness` | 1 | ratio | `@1` | mean | 1 |
| `agent.conflict_collapse_rate` | 0 | ratio | `@1` | mean | 1 |
| `agent.delegation_precision` | 1 | ratio | `@1` | mean | 1 |
| `agent.fallback_success_rate` | 1 | ratio | `@1` | mean | 1 |
| `agent.freshness_satisfaction` | 1 | ratio | `@1` | mean | 1 |
| `agent.no_progress_iteration_rate` | 0.666667 | ratio | `@1` | mean | 1 |
| `agent.parent_child_budget_adherence` | 1 | ratio | `@1` | mean | 1 |
| `agent.recovery_success_rate` | 1 | ratio | `@1` | mean | 1 |
| `agent.redundant_acquisition_rate` | 0 | ratio | `@1` | mean | 1 |
| `agent.source_role_satisfaction` | 1 | ratio | `@1` | mean | 1 |
| `agent.stale_child_result_rate` | 0 | ratio | `@1` | mean | 1 |
| `agent.unnecessary_denied_request_rate` | 0 | ratio | `@1` | mean | 1 |
| `agent.useful_acquisition_precision` | 1 | ratio | `@1` | mean | 1 |
| `engineering.bounded_termination` | 1 | ratio | `@1` | mean | 3 |
| `engineering.failure_isolation` | 1 | ratio | `@1` | mean | 3 |
| `engineering.fault_recovery_success` | 1 | ratio | `@1` | mean | 3 |
| `engineering.retry_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m1.monitoring.evaluable_coverage` | 0.854167 | ratio | `@1` | last | 1 |
| `m1.monitoring.max_seconds` | 1.3454e+08 | seconds | `@1` | last | 1 |
| `m1.monitoring.p50_seconds` | 365.099 | seconds | `@1` | last | 1 |
| `m1.monitoring.p95_seconds` | 3.6492e+06 | seconds | `@1` | last | 1 |
| `m1.monitoring.within_6h_rate` | 0.856369 | ratio | `@1` | last | 1 |
| `m1.source_category_count` | 8 | categories | `@1` | last | 1 |
| `m2.conflict_preservation` | 1 | ratio | `@1` | mean | 1 |
| `m2.entity_resolution_precision` | 1 | ratio | `@1` | mean | 1 |
| `m2.entity_resolution_recall` | 1 | ratio | `@1` | mean | 1 |
| `m2.evidence_correctness` | 1 | ratio | `@1` | mean | 1 |
| `m2.parser_field_accuracy` | 1 | ratio | `@1` | mean | 1 |
| `m2.replay_suppression_accuracy` | 1 | ratio | `@1` | mean | 1 |
| `m3.dimension.advisory_reference.false_negative` | 0 | facts | `@1` | sum | 15 |
| `m3.dimension.advisory_reference.false_positive` | 0 | facts | `@1` | sum | 15 |
| `m3.dimension.advisory_reference.precision` | 1 | ratio | `@1` | mean | 15 |
| `m3.dimension.advisory_reference.recall` | 1 | ratio | `@1` | mean | 15 |
| `m3.dimension.advisory_reference.true_positive` | 21 | facts | `@1` | sum | 15 |
| `m3.dimension.exploit_likelihood.false_negative` | 1 | facts | `@1` | sum | 12 |
| `m3.dimension.exploit_likelihood.false_positive` | 1 | facts | `@1` | sum | 12 |
| `m3.dimension.exploit_likelihood.precision` | 0.979167 | ratio | `@1` | mean | 12 |
| `m3.dimension.exploit_likelihood.recall` | 0.979167 | ratio | `@1` | mean | 12 |
| `m3.dimension.exploit_likelihood.true_positive` | 47 | facts | `@1` | sum | 12 |
| `m3.dimension.fix_remediation.false_negative` | 0 | facts | `@1` | sum | 6 |
| `m3.dimension.fix_remediation.false_positive` | 0 | facts | `@1` | sum | 6 |
| `m3.dimension.fix_remediation.precision` | 1 | ratio | `@1` | mean | 6 |
| `m3.dimension.fix_remediation.recall` | 1 | ratio | `@1` | mean | 6 |
| `m3.dimension.fix_remediation.true_positive` | 18 | facts | `@1` | sum | 6 |
| `m3.dimension.product_package.false_negative` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.product_package.false_positive` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.product_package.precision` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.product_package.recall` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.product_package.true_positive` | 16 | facts | `@1` | sum | 12 |
| `m3.dimension.severity.false_negative` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.severity.false_positive` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.severity.precision` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.severity.recall` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.severity.true_positive` | 48 | facts | `@1` | sum | 12 |
| `m3.dimension.version_applicability.false_negative` | 0 | facts | `@1` | sum | 15 |
| `m3.dimension.version_applicability.false_positive` | 0 | facts | `@1` | sum | 15 |
| `m3.dimension.version_applicability.precision` | 1 | ratio | `@1` | mean | 15 |
| `m3.dimension.version_applicability.recall` | 1 | ratio | `@1` | mean | 15 |
| `m3.dimension.version_applicability.true_positive` | 127 | facts | `@1` | sum | 15 |
| `m3.dimension.weakness.false_negative` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.weakness.false_positive` | 0 | facts | `@1` | sum | 12 |
| `m3.dimension.weakness.precision` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.weakness.recall` | 1 | ratio | `@1` | mean | 12 |
| `m3.dimension.weakness.true_positive` | 15 | facts | `@1` | sum | 12 |
| `m3.dimension_macro_precision` | 0.997222 | ratio | `@1` | mean | 15 |
| `m3.dimension_macro_recall` | 0.997222 | ratio | `@1` | mean | 15 |
| `m3.false_negative` | 1 | facts | `@1` | sum | 15 |
| `m3.false_positive` | 1 | facts | `@1` | sum | 15 |
| `m3.micro_precision` | 0.996587 | ratio | `@1` | derived | 15 |
| `m3.micro_recall` | 0.996587 | ratio | `@1` | derived | 15 |
| `m3.true_positive` | 292 | facts | `@1` | sum | 15 |
| `m6.answer_accuracy` | 0.964286 | ratio | `@2` | mean | 28 |
| `m6.citation_completeness` | 1 | ratio | `@2` | mean | 28 |
| `m6.citation_correctness` | 0.985714 | ratio | `@2` | mean | 28 |
| `m6.completion_correctness` | 1 | ratio | `@2` | mean | 28 |
| `m6.groundedness` | 0.991071 | ratio | `@2` | mean | 28 |
| `m6.interactive_latency_seconds` | 5.57679 | seconds | `@1` | p95 | 28 |
| `m6.multi_hop_correctness` | 0.961538 | ratio | `@2` | mean | 26 |
| `m6.task_correctness` | 0.964286 | ratio | `@1` | mean | 28 |
| `runtime.capability_call_count` | 0 | calls | `@1` | mean | 28 |
| `runtime.model_attempt_count` | 1 | attempts | `@1` | mean | 28 |
| `runtime.model_cached_input_tokens` | 1728 | tokens | `@1` | mean | 28 |
| `runtime.model_input_tokens` | 7242.5 | tokens | `@1` | mean | 28 |
| `runtime.model_output_tokens` | 840.357 | tokens | `@1` | mean | 28 |
| `runtime.model_reasoning_tokens` | 318.429 | tokens | `@1` | mean | 28 |
| `runtime.retrieval_invocation_count` | 0 | calls | `@1` | mean | 28 |
| `security.adversarial_case_pass_rate` | 1 | ratio | `@1` | mean | 1 |
| `security.adversarial_class_coverage` | 1 | ratio | `@1` | mean | 1 |
| `security.authority_violation_count` | 0 | violations | `@1` | sum | 3 |
| `security.policy_conformance` | 1 | ratio | `@1` | mean | 3 |
| `security.secret_exposure_count` | 0 | exposures | `@1` | sum | 3 |

## Metric definitions

### `agent.argument_correctness@1`

- denominator: capability invocations with adjudicated argument expectations
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.budget_deadline_stop_correctness@1`

- denominator: Agent cases reaching a frozen budget/deadline boundary
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.capability_invocation_count@1`

- denominator: frozen Agent case runs
- missing-value policy: `not_evaluated`
- direction: `informational`

### `agent.capability_selection_correctness@1`

- denominator: tool-selection decisions with adjudicated acceptable capability set
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.child_task_usefulness@1`

- denominator: completed delegated child tasks in frozen Agent cases
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.conflict_collapse_rate@1`

- denominator: adjudicated conflicting assertion groups encountered by Agent cases
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `agent.delegation_precision@1`

- denominator: Agent child-task delegations with adjudicated usefulness
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.fallback_success_rate@1`

- denominator: Agent tool/provider actions that entered an adjudicated fallback path
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.freshness_satisfaction@1`

- denominator: frozen EvidenceNeeds with explicit freshness constraints
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.no_progress_iteration_rate@1`

- denominator: Agent planning iterations in frozen cases
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `agent.parent_child_budget_adherence@1`

- denominator: delegated child tasks with inherited budget envelopes
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.recovery_success_rate@1`

- denominator: Agent episodes that encountered a recoverable runtime/provider/tool failure
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.redundant_acquisition_rate@1`

- denominator: Agent acquisition actions in frozen cases
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `agent.source_role_satisfaction@1`

- denominator: frozen EvidenceNeeds with required source-role constraints
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.stale_child_result_rate@1`

- denominator: child-task results returned to a parent execution
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `agent.unnecessary_denied_request_rate@1`

- denominator: Agent capability requests evaluated by policy in frozen cases
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `agent.useful_acquisition_precision@1`

- denominator: Agent acquisition actions in adjudicated frozen cases
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `engineering.bounded_termination@1`

- denominator: controlled fault cases with an expected bounded terminal outcome
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `engineering.failure_isolation@1`

- denominator: controlled fault cases with an explicit unrelated-state sentinel
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `engineering.fault_recovery_success@1`

- denominator: frozen fault-injection cases
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `engineering.retry_correctness@1`

- denominator: controlled fault cases whose expected behavior includes retry semantics
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m1.monitoring.evaluable_coverage@1`

- denominator: all monitoring latency samples in the frozen window
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m1.monitoring.max_seconds@1`

- denominator: latency-evaluable samples only
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `m1.monitoring.p50_seconds@1`

- denominator: latency-evaluable samples only
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `m1.monitoring.p95_seconds@1`

- denominator: latency-evaluable samples only
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

### `m1.monitoring.within_6h_rate@1`

- denominator: latency-evaluable samples only
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m1.source_category_count@1`

- denominator: fixed eight-category product source taxonomy
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m2.conflict_preservation@1`

- denominator: frozen source-conflict cases whose competing assertions must remain represented
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m2.entity_resolution_precision@1`

- denominator: predicted same-entity bindings in a frozen identity-pair set
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m2.entity_resolution_recall@1`

- denominator: gold same-entity bindings in a frozen identity-pair set
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m2.evidence_correctness@1`

- denominator: accepted claim/relation assertions checked against frozen EvidenceRef support
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m2.parser_field_accuracy@1`

- denominator: frozen parser field assertions with value and locator gold
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m2.replay_suppression_accuracy@1`

- denominator: frozen replay cases with expected duplicate suppression behavior
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m3.dimension.advisory_reference.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.advisory_reference.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.advisory_reference.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.advisory_reference.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.advisory_reference.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.exploit_likelihood.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.exploit_likelihood.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.exploit_likelihood.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.exploit_likelihood.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.exploit_likelihood.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.fix_remediation.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.fix_remediation.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.fix_remediation.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.fix_remediation.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.fix_remediation.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.product_package.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.product_package.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.product_package.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.product_package.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.product_package.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.severity.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.severity.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.severity.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.severity.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.severity.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.version_applicability.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.version_applicability.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.version_applicability.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.version_applicability.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.version_applicability.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension.weakness.false_negative@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.weakness.false_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `lower_is_better`

### `m3.dimension.weakness.precision@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.weakness.recall@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m3.dimension.weakness.true_positive@1`

- denominator: closed-set facts in the named enrichment dimension
- missing-value policy: `exclude`
- direction: `informational`

### `m3.dimension_macro_precision@1`

- denominator: enrichment dimensions present in the frozen scored denominator
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m3.dimension_macro_recall@1`

- denominator: enrichment dimensions present in the frozen scored denominator
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m3.false_negative@1`

- denominator: evidence-aware closed-set facts
- missing-value policy: `fail`
- direction: `lower_is_better`

### `m3.false_positive@1`

- denominator: evidence-aware closed-set facts
- missing-value policy: `fail`
- direction: `lower_is_better`

### `m3.micro_precision@1`

- denominator: evidence-aware closed-set predicted facts
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m3.micro_recall@1`

- denominator: evidence-aware closed-set gold facts
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m3.true_positive@1`

- denominator: evidence-aware closed-set facts
- missing-value policy: `fail`
- direction: `informational`

### `m6.answer_accuracy@2`

- denominator: qa-v2 canonical answer cases; unsupported extra assertions fail
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.citation_completeness@2`

- denominator: qa-v2 required citation facts actually asserted and supported
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.citation_correctness@2`

- denominator: qa-v2 nonempty supported citations bound to asserted conclusions
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.completion_correctness@2`

- denominator: qa-v2 expected answered/continuation outcomes; failure is never success
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.groundedness@2`

- denominator: qa-v2 all asserted conclusions; unknown labels cannot hide assertions
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.interactive_latency_seconds@1`

- denominator: interactive QA cases only; long investigations excluded
- missing-value policy: `fail`
- direction: `lower_is_better`

### `m6.multi_hop_correctness@2`

- denominator: qa-v2 whole-task success with every required Decision-used supported path
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m6.task_correctness@1`

- denominator: qa-v2 complete answers with supported assertions/citations, required unknowns/conflicts and all Decision-used paths
- missing-value policy: `fail`
- direction: `higher_is_better`

### `runtime.capability_call_count@1`

- denominator: benchmark case runs with durable capability invocations
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.model_attempt_count@1`

- denominator: benchmark case runs with recorded model execution
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.model_cached_input_tokens@1`

- denominator: benchmark case runs with provider-reported cached-input usage
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.model_input_tokens@1`

- denominator: benchmark case runs with provider/tokenizer model usage
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.model_output_tokens@1`

- denominator: benchmark case runs with provider/tokenizer model usage
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.model_reasoning_tokens@1`

- denominator: benchmark case runs with provider-reported reasoning-token usage
- missing-value policy: `not_evaluated`
- direction: `informational`

### `runtime.retrieval_invocation_count@1`

- denominator: benchmark case runs with durable retrieval invocation provenance
- missing-value policy: `not_evaluated`
- direction: `informational`

### `security.adversarial_case_pass_rate@1`

- denominator: executed cases in the frozen M7 adversarial security suite
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `security.adversarial_class_coverage@1`

- denominator: required adversarial classes in the frozen M7 security profile
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `security.authority_violation_count@1`

- denominator: frozen security benchmark case runs
- missing-value policy: `not_evaluated`
- direction: `target_zero`

### `security.policy_conformance@1`

- denominator: frozen security cases with required/forbidden policy outcomes
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `security.secret_exposure_count@1`

- denominator: frozen security benchmark case runs
- missing-value policy: `not_evaluated`
- direction: `target_zero`

## Not evaluated

- Agent runtime
- Long Investigation completion
- Preliminary qualitative review: source breadth with real-time monitoring
- Preliminary qualitative review: automatic association and deep cross-document QA
- Preliminary qualitative review: Agent architecture, end-to-end self-healing and documentation

## Drill-down coordinates

- `agent.argument_correctness`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.budget_deadline_stop_correctness`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['18fd4219-4276-413b-bd53-60572facf757']
- `agent.capability_invocation_count`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.capability_selection_correctness`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.child_task_usefulness`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['87eb7dc6-b5cf-4528-8e44-b1df173c1bef']
- `agent.conflict_collapse_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['7d73778e-3e71-4a34-8eb0-58dd0c386bf2']
- `agent.delegation_precision`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['87eb7dc6-b5cf-4528-8e44-b1df173c1bef']
- `agent.fallback_success_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['9dcdbc76-6278-431d-b342-248d8092164a']
- `agent.freshness_satisfaction`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.no_progress_iteration_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['1a4fc94a-529d-47ae-8103-8aa6bca9b2a3']
- `agent.parent_child_budget_adherence`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['87eb7dc6-b5cf-4528-8e44-b1df173c1bef']
- `agent.recovery_success_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['5b5f543f-4565-4e50-857b-cb57ac70b58d']
- `agent.redundant_acquisition_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.source_role_satisfaction`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.stale_child_result_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['87eb7dc6-b5cf-4528-8e44-b1df173c1bef']
- `agent.unnecessary_denied_request_rate`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `agent.useful_acquisition_precision`: runs=['205df724-1232-4700-8b2b-e3764e4d4a2a']; case_runs=['806430ad-b905-42be-a9b5-b08a24f911e6']
- `engineering.bounded_termination`: runs=['2f9000dd-154b-402d-9d4f-69af09dce629']; case_runs=['478e6599-dda3-4a55-8082-a4f0c065ccbc', '5020d7d5-3e18-4249-8f9c-564eaed7f25a', 'd061c397-1653-4222-8c5f-9fc4a7f58a49']
- `engineering.failure_isolation`: runs=['2f9000dd-154b-402d-9d4f-69af09dce629']; case_runs=['478e6599-dda3-4a55-8082-a4f0c065ccbc', '5020d7d5-3e18-4249-8f9c-564eaed7f25a', 'd061c397-1653-4222-8c5f-9fc4a7f58a49']
- `engineering.fault_recovery_success`: runs=['2f9000dd-154b-402d-9d4f-69af09dce629']; case_runs=['478e6599-dda3-4a55-8082-a4f0c065ccbc', '5020d7d5-3e18-4249-8f9c-564eaed7f25a', 'd061c397-1653-4222-8c5f-9fc4a7f58a49']
- `engineering.retry_correctness`: runs=['2f9000dd-154b-402d-9d4f-69af09dce629']; case_runs=['5020d7d5-3e18-4249-8f9c-564eaed7f25a', 'd061c397-1653-4222-8c5f-9fc4a7f58a49']
- `m1.monitoring.evaluable_coverage`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['90e08fc3-9391-4145-be17-bc15cac9e28a']
- `m1.monitoring.max_seconds`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['90e08fc3-9391-4145-be17-bc15cac9e28a']
- `m1.monitoring.p50_seconds`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['90e08fc3-9391-4145-be17-bc15cac9e28a']
- `m1.monitoring.p95_seconds`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['90e08fc3-9391-4145-be17-bc15cac9e28a']
- `m1.monitoring.within_6h_rate`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['90e08fc3-9391-4145-be17-bc15cac9e28a']
- `m1.source_category_count`: runs=['56cfbb86-de40-4033-abc7-9ba6b616000c']; case_runs=['6a8c8617-0ff1-4ccf-a568-d8cfd037c24f']
- `m2.conflict_preservation`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['23801632-dfa1-44e8-b6d0-8c4d953bfae8']
- `m2.entity_resolution_precision`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['971e4fe6-7627-404e-9e32-24e08a5d7d82']
- `m2.entity_resolution_recall`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['971e4fe6-7627-404e-9e32-24e08a5d7d82']
- `m2.evidence_correctness`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['662533d9-d163-4c8b-944f-0c72ed844fb0']
- `m2.parser_field_accuracy`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['662533d9-d163-4c8b-944f-0c72ed844fb0']
- `m2.replay_suppression_accuracy`: runs=['d3a9ce51-6175-4d8a-a0bb-ce1653ce03f2']; case_runs=['662533d9-d163-4c8b-944f-0c72ed844fb0']
- `m3.dimension.advisory_reference.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.advisory_reference.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.advisory_reference.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.advisory_reference.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.advisory_reference.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.exploit_likelihood.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.exploit_likelihood.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.fix_remediation.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718']
- `m3.dimension.fix_remediation.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718']
- `m3.dimension.fix_remediation.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718']
- `m3.dimension.fix_remediation.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718']
- `m3.dimension.fix_remediation.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718']
- `m3.dimension.product_package.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.product_package.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.product_package.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.product_package.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.product_package.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.severity.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.severity.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.severity.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.severity.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.severity.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.version_applicability.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.version_applicability.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.version_applicability.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.version_applicability.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.version_applicability.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.weakness.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.weakness.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.weakness.precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.weakness.recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension.weakness.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension_macro_precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.dimension_macro_recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.false_negative`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.false_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.micro_precision`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.micro_recall`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m3.true_positive`: runs=['1ba81c21-bef9-4419-b0a8-264907798dd9', '437981bf-27f7-49bb-87d3-c67e3aeebc9d']; case_runs=['0be5c4a8-6cf1-451b-b33e-288740f568e1', '0c65edb5-d2b7-4a8e-b4ae-cd0d8055bf72', '11424bf7-6af4-45a2-bdc8-28cea0cf2cf7', '215a5daf-f4fb-4271-90a2-b44f39910e82', '5af6ffca-6c64-43d2-b80e-38f393a7882e', '66511e4b-9822-4c54-9ac3-7c50495eeaeb', '67d0c73a-7538-44eb-b588-a8c72166d6fb', '74da6659-bd4d-43a2-9df4-43c2d8e7afc0', '8501cad3-510f-4d22-8fad-c074cbfbbe0d', 'b513c7c6-7326-4f5c-8e0f-151ce571e284', 'b6588049-b7e3-499d-9deb-e29feb4f4ebb', 'bc46c4fa-5537-435e-9c07-44154f715718', 'ceda46f4-eae2-4baa-84d2-5498e36c22f2', 'e234610e-6885-4e89-a8d0-4b815e7b7677', 'f1d1d0b2-4ffb-49ba-ad97-6445ac33a58f']
- `m6.answer_accuracy`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.citation_completeness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.citation_correctness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.completion_correctness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.groundedness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.interactive_latency_seconds`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.multi_hop_correctness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `m6.task_correctness`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.capability_call_count`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.model_attempt_count`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.model_cached_input_tokens`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.model_input_tokens`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.model_output_tokens`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.model_reasoning_tokens`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `runtime.retrieval_invocation_count`: runs=['3bc6320f-16db-4af3-9d2d-9649d9f06d6a', '5246ac59-9f97-4458-b780-efe63dda2799']; case_runs=['05272355-88c5-4d9f-9b70-ff6611903d41', '12d26ddb-e3b3-4a16-8f4a-8d9f37fc01db', '136e0ed9-596a-4670-93e0-4fa82ac6cb8c', '1a7fc14a-b499-4c26-9d39-2bbf52ea97ee', '1dedbae9-ccbb-4e35-b4b8-3877686c4b29', '1e96d9b1-be6e-47e4-a0e6-3746ec482a73', '227389fc-4e68-4695-a108-5d8041aa48da', '239cd62f-4f63-47a2-8729-0d248b919881', '35fa0660-b61d-40e7-8ca9-d54ecd6f5c4d', '4548b70b-2fe1-40ff-a66f-6e6f483e9dd9', '551a65c1-e580-43ec-8b7a-331c01611af7', '67811816-e363-4d1d-82af-d0c3bfbc5722', '71b309b5-acd9-4486-a954-a9d97c6af7fa', '77b069d9-5a3c-4eea-ab0e-7e04ddf5c15b', '85650b73-509f-4a13-b04e-8bc5dbc27ae0', '86f4df90-c3bf-4cbb-b390-4ef3dfc7ee19', '91d13d5b-f316-4315-9ffe-f5231d7f6c8c', 'af34af7f-6c02-40a9-a22f-7892c43757bf', 'b0579ad9-0624-48fb-bb4c-3d4b5db13856', 'b44473f5-5598-4248-968b-062eee324224', 'b91cd0f1-c53e-4283-ada4-84c534606d08', 'c19fecb8-d7cf-4f4f-a2fb-7bfff64ef225', 'c8b8db51-d22a-436f-a334-8c1a493b9224', 'd3a6cb57-c3ed-4439-9888-39ff39416b0b', 'e74d62eb-fb1a-478b-9121-1363a204b5af', 'ef1c8295-8caf-4fe4-9413-b6a3c357fa14', 'f1c7344a-36b3-4697-95dd-4f3d1a9d4b5c', 'f5aea852-6271-47bd-9df5-2660d07b60f5']
- `security.adversarial_case_pass_rate`: runs=['69cdc26d-72f0-4ccc-a466-08c90d48071d']; case_runs=['c5649392-feb9-4bfb-8de9-568532548dd6']
- `security.adversarial_class_coverage`: runs=['69cdc26d-72f0-4ccc-a466-08c90d48071d']; case_runs=['c5649392-feb9-4bfb-8de9-568532548dd6']
- `security.authority_violation_count`: runs=['40afd9cb-9b61-425b-9045-52add6e1a1ee']; case_runs=['90cb9ae0-b8d1-46ee-8696-de5e27314e5d', 'ecb834db-77ff-4d5a-8057-7a84c8751e73', 'f35a80f3-f930-431e-8160-0715016c81d1']
- `security.policy_conformance`: runs=['40afd9cb-9b61-425b-9045-52add6e1a1ee']; case_runs=['90cb9ae0-b8d1-46ee-8696-de5e27314e5d', 'ecb834db-77ff-4d5a-8057-7a84c8751e73', 'f35a80f3-f930-431e-8160-0715016c81d1']
- `security.secret_exposure_count`: runs=['40afd9cb-9b61-425b-9045-52add6e1a1ee']; case_runs=['90cb9ae0-b8d1-46ee-8696-de5e27314e5d', 'ecb834db-77ff-4d5a-8057-7a84c8751e73', 'f35a80f3-f930-431e-8160-0715016c81d1']

## Artifacts

- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
