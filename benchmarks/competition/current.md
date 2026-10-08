<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `eb0a1c43-a786-434e-904a-fd976d751105`
- Digest: `aefe8afcaf8eb943dc7e94e8a6eaeeb23c4f2fafba9c3eb4eac47be10e3ef001`
- Deployment: `deployment:2713f58f83915b2d0d0a9621ed4b7ac7`
- Benchmark runs: `5a1f53e7-87ca-466b-bef8-3f7140f36b66`, `c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88`, `ca4e9126-22fe-47bd-b272-b340ae7cc7a5`, `8ef12b6d-6d85-4c83-b6a9-4271f73452b6`, `39c86b60-779b-43e6-9162-3ccedd23d1af`, `f6a9641a-9c1e-4f7f-8186-746d9bda0116`
- Generated at: `2026-10-08T15:37:32.851706+00:00`

## Competition target checks

| Target | Metric | Observed | Requirement | Status |
| --- | --- | ---: | --- | --- |
| source_category_coverage | `m1.source_category_count` | 8 | >= 7 | **pass** |
| enrichment_precision | `m3.micro_precision` | 0.996587 | >= 0.95 | **pass** |
| enrichment_recall | `m3.micro_recall` | 0.996587 | >= 0.95 | **pass** |
| qa_accuracy | `m6.answer_accuracy` | 1 | >= 0.95 | **pass** |
| qa_interactive_latency | `m6.interactive_latency_seconds` | 3.65505 | <= 5 | **pass** |

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
| `m6.interactive_latency_seconds` | 3.65505 | seconds | `@1` | p95 | 18 |
| `m6.multi_hop_correctness` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_context_chain_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.session_retrieval_invocation_coverage` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_retrieval_reuse_rate` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_target_carry_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.unknown_correctness` | 1 | ratio | `@1` | mean | 18 |
| `runtime.capability_call_count` | 0 | calls | `@1` | mean | 18 |
| `runtime.model_attempt_count` | 1 | attempts | `@1` | mean | 18 |
| `runtime.model_cached_input_tokens` | 1024 | tokens | `@1` | mean | 18 |
| `runtime.model_input_tokens` | 14025.9 | tokens | `@1` | mean | 18 |
| `runtime.model_output_tokens` | 366.611 | tokens | `@1` | mean | 18 |
| `runtime.model_reasoning_tokens` | 204.944 | tokens | `@1` | mean | 18 |
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

- `agent.critical_evidence_need_recall`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af']; case_runs=['5faa84c9-e467-4c1e-8aef-8d29cdd33932']
- `agent.false_gap_rate`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af']; case_runs=['5faa84c9-e467-4c1e-8aef-8d29cdd33932']
- `engineering.bounded_termination`: runs=['8ef12b6d-6d85-4c83-b6a9-4271f73452b6']; case_runs=['9341dbf6-cba0-49f0-8e86-28ca69f25f7e', 'a62f7704-f909-4206-999b-f5eebce8d8f6', 'c3d12ce7-e529-48f7-ac3c-5516625eaee9']
- `engineering.failure_isolation`: runs=['8ef12b6d-6d85-4c83-b6a9-4271f73452b6']; case_runs=['9341dbf6-cba0-49f0-8e86-28ca69f25f7e', 'a62f7704-f909-4206-999b-f5eebce8d8f6', 'c3d12ce7-e529-48f7-ac3c-5516625eaee9']
- `engineering.fault_recovery_success`: runs=['8ef12b6d-6d85-4c83-b6a9-4271f73452b6']; case_runs=['9341dbf6-cba0-49f0-8e86-28ca69f25f7e', 'a62f7704-f909-4206-999b-f5eebce8d8f6', 'c3d12ce7-e529-48f7-ac3c-5516625eaee9']
- `engineering.retry_correctness`: runs=['8ef12b6d-6d85-4c83-b6a9-4271f73452b6']; case_runs=['9341dbf6-cba0-49f0-8e86-28ca69f25f7e', 'c3d12ce7-e529-48f7-ac3c-5516625eaee9']
- `m1.monitoring.evaluable_coverage`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['7b1f6c43-bef2-45a1-b834-5577de1a3527']
- `m1.monitoring.max_seconds`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['7b1f6c43-bef2-45a1-b834-5577de1a3527']
- `m1.monitoring.p50_seconds`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['7b1f6c43-bef2-45a1-b834-5577de1a3527']
- `m1.monitoring.p95_seconds`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['7b1f6c43-bef2-45a1-b834-5577de1a3527']
- `m1.monitoring.within_6h_rate`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['7b1f6c43-bef2-45a1-b834-5577de1a3527']
- `m1.source_category_count`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['6320c807-d64d-4fed-8f1e-c3a5fdf2b95c']
- `m1.source_delivery_coverage`: runs=['5a1f53e7-87ca-466b-bef8-3f7140f36b66']; case_runs=['52c87c37-ce4d-4435-9e48-1d9bfe38e13f']
- `m3.dimension.advisory_reference.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.advisory_reference.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.advisory_reference.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.advisory_reference.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.advisory_reference.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.exploit_likelihood.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.exploit_likelihood.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.fix_remediation.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['1e5152ae-a84b-4afb-9f5c-3d1218a20359', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7de82b74-281e-4f90-8633-8c030560f7ad', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.fix_remediation.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['1e5152ae-a84b-4afb-9f5c-3d1218a20359', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7de82b74-281e-4f90-8633-8c030560f7ad', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.fix_remediation.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['1e5152ae-a84b-4afb-9f5c-3d1218a20359', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7de82b74-281e-4f90-8633-8c030560f7ad', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.fix_remediation.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['1e5152ae-a84b-4afb-9f5c-3d1218a20359', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7de82b74-281e-4f90-8633-8c030560f7ad', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.fix_remediation.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['1e5152ae-a84b-4afb-9f5c-3d1218a20359', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7de82b74-281e-4f90-8633-8c030560f7ad', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.product_package.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.product_package.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.product_package.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.product_package.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.product_package.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.severity.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.severity.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.severity.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.severity.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.severity.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.version_applicability.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.version_applicability.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.version_applicability.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.version_applicability.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.version_applicability.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.weakness.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.weakness.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.weakness.precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.weakness.recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension.weakness.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '6e770934-4411-4b88-953e-fc57197d6f50', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension_macro_precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.dimension_macro_recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.false_negative`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.false_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.micro_precision`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.micro_recall`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m3.true_positive`: runs=['c53d68ad-00bd-4b76-a9b4-f0fa4cd13b88', 'ca4e9126-22fe-47bd-b272-b340ae7cc7a5']; case_runs=['0b7578c7-29b8-47b7-b075-c6553ee337fe', '1e5152ae-a84b-4afb-9f5c-3d1218a20359', '3276d954-4077-47d5-b720-c49b368315d0', '53fa4bed-e4bd-464a-9466-6e355c7d18c2', '5554fb17-f26a-4981-a7c8-93ae2cc3282b', '611169d0-9de3-4f87-af3a-848c7bad60da', '6e770934-4411-4b88-953e-fc57197d6f50', '7801c0e5-7577-4889-a140-0a981dbce6e4', '7c78fd70-8c34-44ec-9f24-45cd93279651', '7de82b74-281e-4f90-8633-8c030560f7ad', '93a3af5a-d65d-481d-b6f5-811cdff8390a', '9c636608-535a-47b4-af9c-210e5bc4392d', 'aa91b5d8-192a-4255-bf05-10dff27927d2', 'da580893-568b-4592-aa66-35f9aaff66a7', 'f45c4e2b-fac7-4a6f-bf0e-153367adde60']
- `m6.answer_accuracy`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.citation_completeness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.citation_correctness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.completion_correctness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.conflict_handling`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.groundedness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.interactive_latency_seconds`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `m6.multi_hop_correctness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af']; case_runs=['947b3e24-13c5-4026-aba6-52cb8f3c3795']
- `m6.session_context_chain_correctness`: runs=['f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['90e0e068-d867-4bc7-8921-a3f3edc4752f', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38']
- `m6.session_retrieval_invocation_coverage`: runs=['f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38']
- `m6.session_retrieval_reuse_rate`: runs=['f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38']
- `m6.session_target_carry_correctness`: runs=['f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['90e0e068-d867-4bc7-8921-a3f3edc4752f', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38']
- `m6.unknown_correctness`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.capability_call_count`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.model_attempt_count`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.model_cached_input_tokens`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.model_input_tokens`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.model_output_tokens`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.model_reasoning_tokens`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']
- `runtime.retrieval_invocation_count`: runs=['39c86b60-779b-43e6-9162-3ccedd23d1af', 'f6a9641a-9c1e-4f7f-8186-746d9bda0116']; case_runs=['01dc6c63-8681-4fc7-a107-3eb594d15b92', '05484b37-f9a3-4fb4-b658-8a0d2d679a65', '079faa02-07f0-476f-894d-8948c1bd8639', '15772c0f-cddf-49f8-b59b-bdec451f3808', '2b85b36a-c622-4938-9e75-896df61f7b57', '3d3dc266-2f4a-425c-99fc-900bdd6110f1', '5faa84c9-e467-4c1e-8aef-8d29cdd33932', '8e3b59f0-3631-4ca0-a81a-5943d621b4b7', '90e0e068-d867-4bc7-8921-a3f3edc4752f', '945d6438-b726-4c22-b6fb-0d2aa0941e10', '947b3e24-13c5-4026-aba6-52cb8f3c3795', '9d4f5657-3337-4a2c-9636-7b96813c968a', 'be9161b5-851d-4f36-bc82-ddc0dc6ce149', 'd6fb51f2-0abe-46de-845d-990e85c0bc38', 'e2fe1c5e-8d52-4db4-bf9e-96c7156c8c38', 'e91a0dcb-5288-493b-ac45-ce633711c366']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
- `knowledge-revision:1019`
- `knowledge-revision:596`
- `knowledge-revision:3443`
