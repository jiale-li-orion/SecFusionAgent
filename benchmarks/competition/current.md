<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `2735331f-1f7d-419c-80d2-72c4ce157b5f`
- Digest: `ec06389d10b787f18abf4aa99b06e9c1d1d13470c8287f1c6ccd8f994033fa8b`
- Deployment: `deployment:0e16e1b574d5b6383434e7fc80f64cc4`
- Benchmark runs: `651b4167-a2a2-4af3-a74a-0630d5ac1916`, `ea3e6082-ef63-4836-82b3-dc6448d1a917`, `66a86f1e-e0aa-49bc-b931-51808f623836`, `dcdd9e23-3fc8-407d-af39-8b5ef93ff62d`, `82a5e288-6d09-40f1-bd80-d4171fc9b629`, `99da1f9b-441b-465c-a962-76549a7741c7`
- Generated at: `2026-10-03T11:16:46.524279+00:00`

## Competition target checks

| Target | Metric | Observed | Requirement | Status |
| --- | --- | ---: | --- | --- |
| source_category_coverage | `m1.source_category_count` | 8 | >= 7 | **pass** |
| enrichment_precision | `m3.micro_precision` | 0.996587 | >= 0.95 | **pass** |
| enrichment_recall | `m3.micro_recall` | 0.996587 | >= 0.95 | **pass** |
| qa_accuracy | `m6.answer_accuracy` | 1 | >= 0.95 | **pass** |
| qa_interactive_latency | `m6.interactive_latency_seconds` | 4.03175 | <= 5 | **pass** |

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
| `m6.interactive_latency_seconds` | 4.03175 | seconds | `@1` | p95 | 18 |
| `m6.multi_hop_correctness` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_context_chain_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.session_retrieval_invocation_coverage` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_retrieval_reuse_rate` | 1 | ratio | `@1` | mean | 1 |
| `m6.session_target_carry_correctness` | 1 | ratio | `@1` | mean | 2 |
| `m6.unknown_correctness` | 1 | ratio | `@1` | mean | 18 |
| `runtime.capability_call_count` | 0 | calls | `@1` | mean | 18 |
| `runtime.model_attempt_count` | 1 | attempts | `@1` | mean | 18 |
| `runtime.model_cached_input_tokens` | 1024 | tokens | `@1` | mean | 18 |
| `runtime.model_input_tokens` | 14025.4 | tokens | `@1` | mean | 18 |
| `runtime.model_output_tokens` | 404.167 | tokens | `@1` | mean | 18 |
| `runtime.model_reasoning_tokens` | 228.5 | tokens | `@1` | mean | 18 |
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

- `agent.critical_evidence_need_recall`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629']; case_runs=['a8b5622b-3c74-420a-b252-7bd0005e569d']
- `agent.false_gap_rate`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629']; case_runs=['a8b5622b-3c74-420a-b252-7bd0005e569d']
- `engineering.bounded_termination`: runs=['dcdd9e23-3fc8-407d-af39-8b5ef93ff62d']; case_runs=['2ed15c49-3eaa-47e3-a354-44aebbfb7a4b', '71dbc834-39ae-42f6-bc23-900a5ab902ed', 'd67f0577-1391-41cb-9178-dba183bc4e98']
- `engineering.failure_isolation`: runs=['dcdd9e23-3fc8-407d-af39-8b5ef93ff62d']; case_runs=['2ed15c49-3eaa-47e3-a354-44aebbfb7a4b', '71dbc834-39ae-42f6-bc23-900a5ab902ed', 'd67f0577-1391-41cb-9178-dba183bc4e98']
- `engineering.fault_recovery_success`: runs=['dcdd9e23-3fc8-407d-af39-8b5ef93ff62d']; case_runs=['2ed15c49-3eaa-47e3-a354-44aebbfb7a4b', '71dbc834-39ae-42f6-bc23-900a5ab902ed', 'd67f0577-1391-41cb-9178-dba183bc4e98']
- `engineering.retry_correctness`: runs=['dcdd9e23-3fc8-407d-af39-8b5ef93ff62d']; case_runs=['2ed15c49-3eaa-47e3-a354-44aebbfb7a4b', 'd67f0577-1391-41cb-9178-dba183bc4e98']
- `m1.monitoring.evaluable_coverage`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['cc437469-f4b0-4642-ab98-243a520455de']
- `m1.monitoring.max_seconds`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['cc437469-f4b0-4642-ab98-243a520455de']
- `m1.monitoring.p50_seconds`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['cc437469-f4b0-4642-ab98-243a520455de']
- `m1.monitoring.p95_seconds`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['cc437469-f4b0-4642-ab98-243a520455de']
- `m1.monitoring.within_6h_rate`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['cc437469-f4b0-4642-ab98-243a520455de']
- `m1.source_category_count`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['7ee7a582-e7bc-409c-95fe-7c1b801449a4']
- `m1.source_delivery_coverage`: runs=['651b4167-a2a2-4af3-a74a-0630d5ac1916']; case_runs=['f9b1b9ad-c0de-43d5-8c33-51f5d83649b6']
- `m3.dimension.advisory_reference.false_negative`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.advisory_reference.false_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.advisory_reference.precision`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.advisory_reference.recall`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.advisory_reference.true_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.exploit_likelihood.precision`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.exploit_likelihood.recall`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.fix_remediation.false_negative`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', 'c4ef9d74-83c2-49fa-aa86-928ea1063181']
- `m3.dimension.fix_remediation.false_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', 'c4ef9d74-83c2-49fa-aa86-928ea1063181']
- `m3.dimension.fix_remediation.precision`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', 'c4ef9d74-83c2-49fa-aa86-928ea1063181']
- `m3.dimension.fix_remediation.recall`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', 'c4ef9d74-83c2-49fa-aa86-928ea1063181']
- `m3.dimension.fix_remediation.true_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', 'c4ef9d74-83c2-49fa-aa86-928ea1063181']
- `m3.dimension.product_package.false_negative`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.product_package.false_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.product_package.precision`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.product_package.recall`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.product_package.true_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.severity.false_negative`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.severity.false_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.severity.precision`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.severity.recall`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.severity.true_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.version_applicability.false_negative`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.version_applicability.false_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.version_applicability.precision`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.version_applicability.recall`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.version_applicability.true_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension.weakness.false_negative`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.weakness.false_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.weakness.precision`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.weakness.recall`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension.weakness.true_positive`: runs=['ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30']
- `m3.dimension_macro_precision`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.dimension_macro_recall`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.false_negative`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.false_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.micro_precision`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.micro_recall`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m3.true_positive`: runs=['66a86f1e-e0aa-49bc-b931-51808f623836', 'ea3e6082-ef63-4836-82b3-dc6448d1a917']; case_runs=['03acdc9d-3aa1-4ee9-83f4-58793a6ad986', '146e795b-cc8b-4560-93f8-907e67e5fb5f', '39655640-aae3-4c0e-9e55-d94657dc9d61', '3dbc2a41-04b6-49ad-b085-ea4d55c1bbf2', '4340140f-e241-425d-b184-f83a571282de', '4ab691d7-d4f8-4a0c-aa63-b04b5b29b471', '4b83e0ac-3f7c-426a-a348-a3509ecf1263', '9744bb50-6ff9-4435-a8bf-ad98d4867390', '982c4781-e5aa-4501-b163-5a5d0586e248', '9b6c4484-a951-40af-a965-2563bf048b81', 'c4ef9d74-83c2-49fa-aa86-928ea1063181', 'c884106e-67e9-42b3-bfd4-47ae0f05c2f1', 'c9bf1311-f34c-4532-925c-a321b76094de', 'f216ad1d-c6c9-4ca5-b27d-49864d6e6b30', 'fe66d281-3d5c-49fb-b6c7-055585eea06a']
- `m6.answer_accuracy`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.citation_completeness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.citation_correctness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.completion_correctness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.conflict_handling`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.groundedness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.interactive_latency_seconds`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `m6.multi_hop_correctness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629']; case_runs=['ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab']
- `m6.session_context_chain_correctness`: runs=['99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['659b663d-a3e7-46cc-97ba-c1e5891e15fa', 'a8b04555-2f63-4a80-b972-38e78e4447de']
- `m6.session_retrieval_invocation_coverage`: runs=['99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['a8b04555-2f63-4a80-b972-38e78e4447de']
- `m6.session_retrieval_reuse_rate`: runs=['99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['a8b04555-2f63-4a80-b972-38e78e4447de']
- `m6.session_target_carry_correctness`: runs=['99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['659b663d-a3e7-46cc-97ba-c1e5891e15fa', 'a8b04555-2f63-4a80-b972-38e78e4447de']
- `m6.unknown_correctness`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.capability_call_count`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.model_attempt_count`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.model_cached_input_tokens`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.model_input_tokens`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.model_output_tokens`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.model_reasoning_tokens`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']
- `runtime.retrieval_invocation_count`: runs=['82a5e288-6d09-40f1-bd80-d4171fc9b629', '99da1f9b-441b-465c-a962-76549a7741c7']; case_runs=['1d3868f5-ee33-478d-a896-fa5badfcac4d', '3b6edf7c-0cd2-4427-bf22-93312096cee2', '4bba4450-fc30-41d8-96a0-c4964f0f3e3d', '5ce36b05-84c1-4518-b80a-f86b717a4114', '62c159a9-85f4-4226-9d02-31ed5211f032', '659b663d-a3e7-46cc-97ba-c1e5891e15fa', '90c9fb64-5036-40da-a182-679412f72592', 'a8b04555-2f63-4a80-b972-38e78e4447de', 'a8b5622b-3c74-420a-b252-7bd0005e569d', 'ad100ffd-bb0d-4ec5-a56d-9cbea66b9bab', 'b359e7e1-9c76-486a-9e1d-b340bf77763f', 'ba205a5b-82fc-43db-8686-fdedc845a6c6', 'c63a51af-db1b-4b1e-b1fa-654730f723ff', 'd3f90c8b-e411-4bd8-a388-81735ea5f5e1', 'd74b1daf-9026-4040-991d-90412beff6ca', 'e624c962-76ed-4271-a3a9-011c8d290f09']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
- `knowledge-revision:1019`
- `knowledge-revision:596`
- `knowledge-revision:2053`
