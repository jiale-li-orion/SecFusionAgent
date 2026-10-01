<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `d7b2078b-cc15-4733-aaa6-bd4a1247681b`
- Digest: `66040ac6e161d693f224e673752eefd20c94b5dab2103430ab8e8468ce0190db`
- Deployment: `deployment:711abec1f895ab4108b30f66788bd536`
- Benchmark runs: `966a2298-b2f4-4484-b2fd-e9bb562d29c2`, `b06d561b-ddbb-4c2c-b5b3-e56927b2a98b`, `9fea25f3-a28c-4040-b2dd-5da72eb8bf2e`, `780fb593-9dd1-4ed3-89d4-c10ff21dc25e`
- Generated at: `2026-10-01T16:17:26.904497+00:00`

## Competition target checks

| Target | Metric | Observed | Requirement | Status |
| --- | --- | ---: | --- | --- |
| source_category_coverage | `m1.source_category_count` | 8 | >= 7 | **pass** |
| enrichment_precision | `m3.micro_precision` | 0.996587 | >= 0.95 | **pass** |
| enrichment_recall | `m3.micro_recall` | 0.996587 | >= 0.95 | **pass** |
| qa_accuracy | `m6.answer_accuracy` | — | >= 0.95 | **not_evaluated** |
| qa_interactive_latency | `m6.interactive_latency_seconds` | — | <= 5 | **not_evaluated** |

## Metrics

| Metric | Value | Unit | Definition | Aggregation | Cases |
| --- | ---: | --- | --- | --- | ---: |
| `engineering.fault_recovery_success` | 1 | ratio | `@1` | mean | 2 |
| `m1.monitoring.evaluable_coverage` | 1 | ratio | `@1` | last | 1 |
| `m1.monitoring.max_seconds` | 7241.89 | seconds | `@1` | last | 1 |
| `m1.monitoring.p50_seconds` | 357.709 | seconds | `@1` | last | 1 |
| `m1.monitoring.p95_seconds` | 7241.89 | seconds | `@1` | last | 1 |
| `m1.monitoring.within_6h_rate` | 1 | ratio | `@1` | last | 1 |
| `m1.source_category_count` | 8 | categories | `@1` | last | 1 |
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
| `m3.false_negative` | 1 | facts | `@1` | sum | 15 |
| `m3.false_positive` | 1 | facts | `@1` | sum | 15 |
| `m3.micro_precision` | 0.996587 | ratio | `@1` | derived | 15 |
| `m3.micro_recall` | 0.996587 | ratio | `@1` | derived | 15 |
| `m3.true_positive` | 292 | facts | `@1` | sum | 15 |

## Metric definitions

### `engineering.fault_recovery_success@1`

- denominator: frozen fault-injection cases
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

## Not evaluated

- M6 QA quality
- M6 multi-hop
- Agent runtime
- Long Investigation completion

## Drill-down coordinates

- `engineering.fault_recovery_success`: runs=['780fb593-9dd1-4ed3-89d4-c10ff21dc25e']; case_runs=['3c1aa189-6f26-476f-b5df-62c700ce6b73', '5443be5d-ccf0-4448-9893-a597f93e5252']
- `m1.monitoring.evaluable_coverage`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['78af73a8-cba1-4061-b4df-71665b355204']
- `m1.monitoring.max_seconds`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['78af73a8-cba1-4061-b4df-71665b355204']
- `m1.monitoring.p50_seconds`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['78af73a8-cba1-4061-b4df-71665b355204']
- `m1.monitoring.p95_seconds`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['78af73a8-cba1-4061-b4df-71665b355204']
- `m1.monitoring.within_6h_rate`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['78af73a8-cba1-4061-b4df-71665b355204']
- `m1.source_category_count`: runs=['966a2298-b2f4-4484-b2fd-e9bb562d29c2']; case_runs=['6c868af0-1a85-4220-8a92-659c0a9096a7']
- `m3.dimension.advisory_reference.false_negative`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.advisory_reference.false_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.advisory_reference.precision`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.advisory_reference.recall`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.advisory_reference.true_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.exploit_likelihood.precision`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.exploit_likelihood.recall`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.fix_remediation.false_negative`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ef025bb7-cca4-401e-8509-b694960a7eb1']
- `m3.dimension.fix_remediation.false_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ef025bb7-cca4-401e-8509-b694960a7eb1']
- `m3.dimension.fix_remediation.precision`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ef025bb7-cca4-401e-8509-b694960a7eb1']
- `m3.dimension.fix_remediation.recall`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ef025bb7-cca4-401e-8509-b694960a7eb1']
- `m3.dimension.fix_remediation.true_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ef025bb7-cca4-401e-8509-b694960a7eb1']
- `m3.dimension.product_package.false_negative`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.product_package.false_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.product_package.precision`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.product_package.recall`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.product_package.true_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.severity.false_negative`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.severity.false_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.severity.precision`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.severity.recall`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.severity.true_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.version_applicability.false_negative`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.version_applicability.false_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.version_applicability.precision`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.version_applicability.recall`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.version_applicability.true_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.weakness.false_negative`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.weakness.false_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.weakness.precision`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.weakness.recall`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.dimension.weakness.true_positive`: runs=['b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '3901e5ad-291b-414c-99d5-abfdd499f6c9', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.false_negative`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.false_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.micro_precision`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.micro_recall`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']
- `m3.true_positive`: runs=['9fea25f3-a28c-4040-b2dd-5da72eb8bf2e', 'b06d561b-ddbb-4c2c-b5b3-e56927b2a98b']; case_runs=['0b45199b-38d9-4a4a-b37f-4ddbd99f14b1', '1ed250fc-1962-4753-976f-cccbdc3ac7dc', '231f2e1d-696f-4322-9948-9d64164883af', '32115f77-8069-4b8e-b84f-cd53b3cee449', '3901e5ad-291b-414c-99d5-abfdd499f6c9', '50be6077-6ff7-4cd2-a231-283483b7677a', 'a0279d95-7a16-4f62-9378-fcc16e5e3915', 'bac0623a-b827-4e6f-98e4-aa4da6d9be7d', 'be144b1b-374e-42fc-990f-d04d8c4bcbcf', 'd20c72db-7125-4835-bed5-c9b0bb836222', 'e09d1e36-e662-41b7-aa46-946af7dd82cb', 'e277fbf2-30dc-41e1-8c28-bf0c653e8b6b', 'ea44ec7b-4839-4e6e-8221-859f9dd11153', 'ef025bb7-cca4-401e-8509-b694960a7eb1', 'f6a1ea18-beea-4cef-a47a-39482b830bb9']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
