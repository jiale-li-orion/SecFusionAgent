<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `6b1477f4-1255-4e6b-835b-b6d4edff11de`
- Digest: `159f1eb4058eb6d10f67f8db1be25295c8055c162a70e2a90aff4c6e7f43a93f`
- Deployment: `deployment:c547c6cd953f4b1dbac8b3395d46d955`
- Benchmark runs: `be72d886-817f-4cf8-a025-764c32fa5939`, `e39c9360-214e-4f87-bd2d-f8d904b8f2bb`, `4a290259-d1f9-4947-a425-2432444d7c02`
- Generated at: `2026-10-01T15:58:37.230616+00:00`

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
- Engineering fault/recovery

## Drill-down coordinates

- `m1.monitoring.evaluable_coverage`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['664d1d47-54f3-4c08-b0f7-05fb03e167f0']
- `m1.monitoring.max_seconds`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['664d1d47-54f3-4c08-b0f7-05fb03e167f0']
- `m1.monitoring.p50_seconds`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['664d1d47-54f3-4c08-b0f7-05fb03e167f0']
- `m1.monitoring.p95_seconds`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['664d1d47-54f3-4c08-b0f7-05fb03e167f0']
- `m1.monitoring.within_6h_rate`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['664d1d47-54f3-4c08-b0f7-05fb03e167f0']
- `m1.source_category_count`: runs=['be72d886-817f-4cf8-a025-764c32fa5939']; case_runs=['0989b282-ad05-44d1-9266-12e00bc0e288']
- `m3.dimension.advisory_reference.false_negative`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.advisory_reference.false_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.advisory_reference.precision`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.advisory_reference.recall`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.advisory_reference.true_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.exploit_likelihood.precision`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.exploit_likelihood.recall`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.fix_remediation.false_negative`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '87fb65a2-de37-4dda-b44b-0b902282f91e', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.fix_remediation.false_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '87fb65a2-de37-4dda-b44b-0b902282f91e', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.fix_remediation.precision`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '87fb65a2-de37-4dda-b44b-0b902282f91e', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.fix_remediation.recall`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '87fb65a2-de37-4dda-b44b-0b902282f91e', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.fix_remediation.true_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '87fb65a2-de37-4dda-b44b-0b902282f91e', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.product_package.false_negative`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.product_package.false_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.product_package.precision`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.product_package.recall`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.product_package.true_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.severity.false_negative`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.severity.false_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.severity.precision`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.severity.recall`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.severity.true_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.version_applicability.false_negative`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.version_applicability.false_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.version_applicability.precision`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.version_applicability.recall`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.version_applicability.true_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.weakness.false_negative`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.weakness.false_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.weakness.precision`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.weakness.recall`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.dimension.weakness.true_positive`: runs=['e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.false_negative`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.false_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.micro_precision`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.micro_recall`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']
- `m3.true_positive`: runs=['4a290259-d1f9-4947-a425-2432444d7c02', 'e39c9360-214e-4f87-bd2d-f8d904b8f2bb']; case_runs=['01ba00bd-305b-4f6e-ad71-ab88a64ae850', '0583c6cb-645c-4cb0-8afe-6d9f8e8175c9', '07c1621d-7d7a-4cd5-ab62-fdb612131a64', '1419641c-32fc-49df-b3e3-b4da5f4e9ebd', '17228f15-7cbd-4f82-a711-7258c1626e9d', '2309ec08-e435-412b-a481-63c543cb613f', '2670c00c-e9c5-4d2e-a48c-75ae7965fe4c', '2ad0b754-8233-4bf6-a22d-0f2c52ebd174', '87fb65a2-de37-4dda-b44b-0b902282f91e', '8f537322-54be-4bec-b19a-7c0dca578d1b', '9a2dd3ae-7b6a-4431-96fe-b856667c6c2c', 'ae55e683-df9f-4af1-9912-c3bef96fd74c', 'b2102090-b679-4398-9145-e047e1487690', 'e1c4113c-fb79-485c-9239-e3a49a8b3f54', 'e760d107-cea3-419c-b149-f4d1f13b34f3']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
