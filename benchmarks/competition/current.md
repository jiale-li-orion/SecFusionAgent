<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `9227c091-3076-4d86-8a88-bc2631b26fe2`
- Digest: `48871f12862b3718bbb0b0c4e4ecd180a35461d59d8c6cd44e7d45cb3dbbd4f8`
- Deployment: `deployment:f518d9f8fd7a776996354d34afa7f299`
- Benchmark runs: `21803fd4-4aaf-42a5-992d-4364e9e31dd2`, `216b901f-12b7-4c4d-8c0f-4a41da0a7108`, `44915032-a39c-46f3-ad83-36e7cc96f89e`, `e8cb92f6-42fd-4492-8284-863e9afca0b8`
- Generated at: `2026-10-01T17:47:52.076399+00:00`

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

- `engineering.fault_recovery_success`: runs=['e8cb92f6-42fd-4492-8284-863e9afca0b8']; case_runs=['4611364b-79fe-4d73-9bda-6f282ec10a4c', 'e5a5cb64-ba25-4bc5-b96a-221311ef570a']
- `m1.monitoring.evaluable_coverage`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['2b11f5f5-1663-40da-b9e4-151b6d040202']
- `m1.monitoring.max_seconds`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['2b11f5f5-1663-40da-b9e4-151b6d040202']
- `m1.monitoring.p50_seconds`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['2b11f5f5-1663-40da-b9e4-151b6d040202']
- `m1.monitoring.p95_seconds`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['2b11f5f5-1663-40da-b9e4-151b6d040202']
- `m1.monitoring.within_6h_rate`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['2b11f5f5-1663-40da-b9e4-151b6d040202']
- `m1.source_category_count`: runs=['21803fd4-4aaf-42a5-992d-4364e9e31dd2']; case_runs=['5e925ac6-d9ae-4d27-84bf-f85801bfed55']
- `m3.dimension.advisory_reference.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.advisory_reference.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.advisory_reference.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.advisory_reference.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.advisory_reference.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.exploit_likelihood.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.exploit_likelihood.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.fix_remediation.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.fix_remediation.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.fix_remediation.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.fix_remediation.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.fix_remediation.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.product_package.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.product_package.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.product_package.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.product_package.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.product_package.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.severity.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.severity.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.severity.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.severity.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.severity.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.version_applicability.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.version_applicability.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.version_applicability.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.version_applicability.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.version_applicability.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.weakness.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.weakness.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.weakness.precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.weakness.recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.dimension.weakness.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.false_negative`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.false_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.micro_precision`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.micro_recall`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']
- `m3.true_positive`: runs=['216b901f-12b7-4c4d-8c0f-4a41da0a7108', '44915032-a39c-46f3-ad83-36e7cc96f89e']; case_runs=['0f1d0f00-7eb2-46ba-a7d5-521a63f18f3b', '1da2654d-24f5-48c0-9a41-c8471fb52acc', '2d2a2f18-33d2-40d6-9096-ab8198d0b235', '31ccbc77-8f9f-4344-bb33-b2903e5b25e5', '631754ba-fdb0-49d4-9ba7-c5ece9efef73', '6a0eb81a-9ed9-4d2b-bfaa-76883ecfe210', '70ed4845-d746-4441-a0e0-f6b7701f60f7', '92f6d9d8-0d8c-4713-a925-bef801ab1a2e', '9931582d-50be-4709-81a6-96a936c0d5b9', 'a08fa200-fe4d-4cf4-8a52-54e389cfe3e5', 'ad841f4a-31a6-44a4-b720-086636054b2b', 'afb367d6-ca48-46df-b69b-83f8a280e844', 'afc1e548-e5a4-4983-996f-927deffdb997', 'd70bb98b-9609-4397-bdb4-2e67fd9abca8', 'f6a77896-b603-48df-850c-76f3b98f1e58']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
- `knowledge-revision:1019`
- `knowledge-revision:596`
