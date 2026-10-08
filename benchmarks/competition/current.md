<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `a7254bd2-03e2-41ce-8329-8af5a9c248a1`
- Digest: `2279414c293ad61938a994be6087cf8b0059f24f4984826fc1ca62f04b4d2f21`
- Deployment: `deployment:a811b6b5d5316d9d23d28d2ff132a73f`
- Benchmark runs: `d8c2d686-90a1-4226-ad41-170db40a115b`, `5bd53dc2-5650-484b-8cda-18a41cd7c62f`, `355f3814-e4e4-48b8-9a11-57df90024908`, `ec8557e7-50f8-442c-be4b-92a680bbd2d2`, `48f4f6e2-4975-4ac3-9769-7347d9e16989`, `5e947779-7fba-45ac-8041-ce4287a05230`
- Generated at: `2026-10-08T15:25:01.758580+00:00`

## Competition target checks

| Target | Metric | Observed | Requirement | Status |
| --- | --- | ---: | --- | --- |
| source_category_coverage | `m1.source_category_count` | 8 | >= 7 | **pass** |
| enrichment_precision | `m3.micro_precision` | 0.996587 | >= 0.95 | **pass** |
| enrichment_recall | `m3.micro_recall` | 0.996587 | >= 0.95 | **pass** |
| qa_accuracy | `m6.answer_accuracy` | 1 | >= 0.95 | **pass** |
| qa_interactive_latency | `m6.interactive_latency_seconds` | 6.06326 | <= 5 | **fail** |

## Metrics

| Metric | Value | Unit | Definition | Aggregation | Cases |
| --- | ---: | --- | --- | --- | ---: |
| `agent.critical_evidence_need_recall` | 1 | ratio | `@1` | mean | 1 |
| `agent.false_gap_rate` | 0 | ratio | `@1` | mean | 1 |
| `engineering.bounded_termination` | 1 | ratio | `@1` | mean | 3 |
| `engineering.failure_isolation` | 1 | ratio | `@1` | mean | 3 |
| `engineering.fault_recovery_success` | 1 | ratio | `@1` | mean | 3 |
| `engineering.retry_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m1.monitoring.evaluable_coverage` | 1 | ratio | `@1` | last | 1 |
| `m1.monitoring.max_seconds` | 7241.89 | seconds | `@1` | last | 1 |
| `m1.monitoring.p50_seconds` | 357.709 | seconds | `@1` | last | 1 |
| `m1.monitoring.p95_seconds` | 7241.89 | seconds | `@1` | last | 1 |
| `m1.monitoring.within_6h_rate` | 1 | ratio | `@1` | last | 1 |
| `m1.source_category_count` | 8 | categories | `@1` | last | 1 |
| `m1.source_delivery_coverage` | 0.615385 | ratio | `@1` | mean | 1 |
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
| `m6.answer_accuracy` | 1 | ratio | `@1` | mean | 18 |
| `m6.citation_completeness` | 1 | ratio | `@1` | mean | 18 |
| `m6.citation_correctness` | 1 | ratio | `@1` | mean | 18 |
| `m6.completion_correctness` | 1 | ratio | `@1` | mean | 18 |
| `m6.conflict_handling` | 1 | ratio | `@1` | mean | 18 |
| `m6.groundedness` | 1 | ratio | `@1` | mean | 18 |
| `m6.interactive_latency_seconds` | 6.06326 | seconds | `@1` | p95 | 18 |
| `m6.multi_hop_correctness` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_context_chain_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.session_retrieval_invocation_coverage` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_retrieval_reuse_rate` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_target_carry_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.unknown_correctness` | 1 | ratio | `@1` | mean | 18 |
| `runtime.capability_call_count` | 0 | calls | `@1` | mean | 18 |
| `runtime.model_attempt_count` | 1 | attempts | `@1` | mean | 18 |
| `runtime.model_cached_input_tokens` | 1024 | tokens | `@1` | mean | 18 |
| `runtime.model_input_tokens` | 14025.2 | tokens | `@1` | mean | 18 |
| `runtime.model_output_tokens` | 386.611 | tokens | `@1` | mean | 18 |
| `runtime.model_reasoning_tokens` | 228.833 | tokens | `@1` | mean | 18 |
| `runtime.retrieval_invocation_count` | 0.111111 | calls | `@1` | mean | 18 |

## Metric definitions

### `agent.critical_evidence_need_recall@1`

- denominator: adjudicated critical EvidenceNeeds in frozen Agent cases
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `agent.false_gap_rate@1`

- denominator: EvidenceNeeds opened by the Agent in adjudicated frozen cases
- missing-value policy: `not_evaluated`
- direction: `lower_is_better`

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

### `m1.source_delivery_coverage@1`

- denominator: frozen expected source delivery keys
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

### `m6.answer_accuracy@1`

- denominator: frozen QA cases with adjudicated answer gold
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.citation_completeness@1`

- denominator: factual conclusions requiring citation coverage
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.citation_correctness@1`

- denominator: answer citations checked against supporting evidence
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.completion_correctness@1`

- denominator: frozen QA cases with expected DIRECT/ANSWER/CONTINUE behavior
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.conflict_handling@1`

- denominator: QA cases with adjudicated source conflicts
- missing-value policy: `exclude`
- direction: `higher_is_better`

### `m6.groundedness@1`

- denominator: factual conclusions requiring evidence
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.interactive_latency_seconds@1`

- denominator: interactive QA cases only; long investigations excluded
- missing-value policy: `fail`
- direction: `lower_is_better`

### `m6.multi_hop_correctness@1`

- denominator: QA cases requiring adjudicated intermediate relation paths
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m6.session_context_chain_correctness@1`

- denominator: live Product QA session cases with at least two turns
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.session_retrieval_invocation_coverage@1`

- denominator: follow-up RETRIEVE turns in a QASessionCase
- missing-value policy: `not_evaluated`
- direction: `higher_is_better`

### `m6.session_retrieval_reuse_rate@1`

- denominator: follow-up RETRIEVE turns with one durable retrieval invocation
- missing-value policy: `not_evaluated`
- direction: `informational`

### `m6.session_target_carry_correctness@1`

- denominator: follow-up turns with frozen expected canonical target keys
- missing-value policy: `fail`
- direction: `higher_is_better`

### `m6.unknown_correctness@1`

- denominator: QA cases with adjudicated unknown/abstention behavior
- missing-value policy: `exclude`
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

## Not evaluated

- M2 parser/entity/evidence diagnostics
- Agent runtime
- Long Investigation completion
- Security adversarial hard gates
- Security adversarial breadth

## Drill-down coordinates

- `agent.critical_evidence_need_recall`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989']; case_runs=['b386c904-2621-42e1-b0fa-38c7e768f09b']
- `agent.false_gap_rate`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989']; case_runs=['b386c904-2621-42e1-b0fa-38c7e768f09b']
- `engineering.bounded_termination`: runs=['ec8557e7-50f8-442c-be4b-92a680bbd2d2']; case_runs=['1a930fa2-82f1-461d-9718-da65d7a9700d', '345840dc-2f63-4fab-93c9-a83b230dac70', 'f9a17848-63a8-4dac-8a4c-2f10bddbf83a']
- `engineering.failure_isolation`: runs=['ec8557e7-50f8-442c-be4b-92a680bbd2d2']; case_runs=['1a930fa2-82f1-461d-9718-da65d7a9700d', '345840dc-2f63-4fab-93c9-a83b230dac70', 'f9a17848-63a8-4dac-8a4c-2f10bddbf83a']
- `engineering.fault_recovery_success`: runs=['ec8557e7-50f8-442c-be4b-92a680bbd2d2']; case_runs=['1a930fa2-82f1-461d-9718-da65d7a9700d', '345840dc-2f63-4fab-93c9-a83b230dac70', 'f9a17848-63a8-4dac-8a4c-2f10bddbf83a']
- `engineering.retry_correctness`: runs=['ec8557e7-50f8-442c-be4b-92a680bbd2d2']; case_runs=['1a930fa2-82f1-461d-9718-da65d7a9700d', 'f9a17848-63a8-4dac-8a4c-2f10bddbf83a']
- `m1.monitoring.evaluable_coverage`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['9696e971-efc0-48e6-88db-06eac13dfb75']
- `m1.monitoring.max_seconds`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['9696e971-efc0-48e6-88db-06eac13dfb75']
- `m1.monitoring.p50_seconds`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['9696e971-efc0-48e6-88db-06eac13dfb75']
- `m1.monitoring.p95_seconds`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['9696e971-efc0-48e6-88db-06eac13dfb75']
- `m1.monitoring.within_6h_rate`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['9696e971-efc0-48e6-88db-06eac13dfb75']
- `m1.source_category_count`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['eb1901ac-537b-4b43-b198-12d13b7c9f93']
- `m1.source_delivery_coverage`: runs=['d8c2d686-90a1-4226-ad41-170db40a115b']; case_runs=['d9578c98-dc20-46c4-a8ed-ec04ffe3e54b']
- `m3.dimension.advisory_reference.false_negative`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.advisory_reference.false_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.advisory_reference.precision`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.advisory_reference.recall`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.advisory_reference.true_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.exploit_likelihood.precision`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.exploit_likelihood.recall`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.fix_remediation.false_negative`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6']
- `m3.dimension.fix_remediation.false_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6']
- `m3.dimension.fix_remediation.precision`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6']
- `m3.dimension.fix_remediation.recall`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6']
- `m3.dimension.fix_remediation.true_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6']
- `m3.dimension.product_package.false_negative`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.product_package.false_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.product_package.precision`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.product_package.recall`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.product_package.true_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.severity.false_negative`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.severity.false_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.severity.precision`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.severity.recall`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.severity.true_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.version_applicability.false_negative`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.version_applicability.false_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.version_applicability.precision`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.version_applicability.recall`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.version_applicability.true_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.weakness.false_negative`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.weakness.false_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.weakness.precision`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.weakness.recall`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension.weakness.true_positive`: runs=['5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension_macro_precision`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.dimension_macro_recall`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.false_negative`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.false_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.micro_precision`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.micro_recall`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m3.true_positive`: runs=['355f3814-e4e4-48b8-9a11-57df90024908', '5bd53dc2-5650-484b-8cda-18a41cd7c62f']; case_runs=['0558f998-9e43-4078-9afb-da19fe9e9485', '137dd9eb-250d-4824-88a9-3d5dad691ca0', '2815d5a1-d4fc-40d2-aec7-9ab1507659c9', '720b548b-29f0-4a4d-a5ba-5069a1d0e899', '928b2dfb-0951-43d3-a76f-094f47470304', '979a2e61-2adf-4d0c-a03c-cee57604ed1d', 'a4ee2b00-228e-4120-981f-26d6a8fb95a6', 'a61ea18f-96fa-4676-a56d-fc07ba6a5a66', 'b0c471fd-acad-4ede-9e08-730438960ad8', 'c0432487-e1f9-47da-8859-ed76b15cdcac', 'c2ce70f1-ba83-41e9-8920-f84adc49ab08', 'd6b731de-0072-42e1-adbb-545363fffc52', 'e2fb4888-253b-401d-9a07-86dba4faf11b', 'e8a8c189-1015-494d-b49b-a3361508f6d6', 'ecc6275e-d038-4801-a4cf-ed109b76570a']
- `m6.answer_accuracy`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.citation_completeness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.citation_correctness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.completion_correctness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.conflict_handling`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.groundedness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.interactive_latency_seconds`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `m6.multi_hop_correctness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989']; case_runs=['6c526e80-6e0e-4a2f-86cb-22c7933f0bfd']
- `m6.session_context_chain_correctness`: runs=['5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41']
- `m6.session_retrieval_invocation_coverage`: runs=['5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['7a2fc4bb-634b-4be9-b3d0-addc14b36a41']
- `m6.session_retrieval_reuse_rate`: runs=['5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['7a2fc4bb-634b-4be9-b3d0-addc14b36a41']
- `m6.session_target_carry_correctness`: runs=['5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41']
- `m6.unknown_correctness`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.capability_call_count`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.model_attempt_count`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.model_cached_input_tokens`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.model_input_tokens`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.model_output_tokens`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.model_reasoning_tokens`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']
- `runtime.retrieval_invocation_count`: runs=['48f4f6e2-4975-4ac3-9769-7347d9e16989', '5e947779-7fba-45ac-8041-ce4287a05230']; case_runs=['5734d01d-3d45-49c3-8ea1-a225aa41e65d', '6236a523-d3f5-4090-b139-0c5efb43c78f', '63c85374-c2ae-42d6-96ff-00486376e80c', '6b74c3c7-a8a0-47e7-91bf-9d92cb2b82c9', '6c526e80-6e0e-4a2f-86cb-22c7933f0bfd', '6d9e0e13-ab67-42ae-9c4e-7b016d35b4ac', '7724cb7e-c2c0-462b-a4fe-6f7446b7a981', '7a2fc4bb-634b-4be9-b3d0-addc14b36a41', 'a7dc35c2-4f1d-4637-a897-2c2a1d914136', 'aa3f1666-38d2-4b5d-bbd0-957bc5073245', 'b386c904-2621-42e1-b0fa-38c7e768f09b', 'ba7db946-e0a9-4322-9a02-8bb9989313d6', 'bd4cad48-af5b-478a-b37b-bbf5a05ba995', 'bdd5f2b9-4498-43bc-a07e-8b02f9218694', 'c08d223b-3f19-44d1-88ba-d15513e11c37', 'c28a2eda-7622-4a51-883d-dedcc6917d55']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
- `knowledge-revision:1019`
- `knowledge-revision:596`
- `knowledge-revision:3443`
