<!-- GENERATED from CompetitionReport JSON; DO NOT EDIT BY HAND. -->
# SecFusionAgent Competition Evaluation Report

- Report: `97124d5a-0622-49b4-841c-d68bbc1d6ff6`
- Digest: `3eb03a81bd332147b27ad48805f856f0a0055244afa303320f2927171ecee671`
- Deployment: `deployment:cdf7f3d1be6deb3316cad1ae590737ed`
- Benchmark runs: `535d8476-ea17-4084-be10-78b409ef65c8`, `fe4eef45-a22b-4fbe-b21c-ff996da5e9b9`, `cc47bffe-99c0-4084-a3f0-3c4359fbe0e4`
- Generated at: `2026-10-01T15:49:01.409795+00:00`

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

- `m1.monitoring.evaluable_coverage`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['83a79ca9-d816-4211-8371-f9c708d39fa3']
- `m1.monitoring.max_seconds`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['83a79ca9-d816-4211-8371-f9c708d39fa3']
- `m1.monitoring.p50_seconds`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['83a79ca9-d816-4211-8371-f9c708d39fa3']
- `m1.monitoring.p95_seconds`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['83a79ca9-d816-4211-8371-f9c708d39fa3']
- `m1.monitoring.within_6h_rate`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['83a79ca9-d816-4211-8371-f9c708d39fa3']
- `m1.source_category_count`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['0f687a06-c1d4-4c72-806f-a9c89af46122']
- `m1.source_delivery_coverage`: runs=['535d8476-ea17-4084-be10-78b409ef65c8']; case_runs=['3bd313aa-25f1-40a0-964b-2d675603bd5d']
- `m3.dimension.advisory_reference.false_negative`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.advisory_reference.false_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.advisory_reference.precision`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.advisory_reference.recall`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.advisory_reference.true_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.exploit_likelihood.false_negative`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.exploit_likelihood.false_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.exploit_likelihood.precision`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.exploit_likelihood.recall`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.exploit_likelihood.true_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.fix_remediation.false_negative`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['2ce612ed-a370-432a-87b4-4dbbf1ff2247', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974']
- `m3.dimension.fix_remediation.false_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['2ce612ed-a370-432a-87b4-4dbbf1ff2247', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974']
- `m3.dimension.fix_remediation.precision`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['2ce612ed-a370-432a-87b4-4dbbf1ff2247', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974']
- `m3.dimension.fix_remediation.recall`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['2ce612ed-a370-432a-87b4-4dbbf1ff2247', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974']
- `m3.dimension.fix_remediation.true_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['2ce612ed-a370-432a-87b4-4dbbf1ff2247', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974']
- `m3.dimension.product_package.false_negative`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.product_package.false_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.product_package.precision`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.product_package.recall`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.product_package.true_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.severity.false_negative`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.severity.false_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.severity.precision`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.severity.recall`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.severity.true_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.version_applicability.false_negative`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.version_applicability.false_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.version_applicability.precision`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.version_applicability.recall`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.version_applicability.true_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.dimension.weakness.false_negative`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.weakness.false_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.weakness.precision`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.weakness.recall`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.dimension.weakness.true_positive`: runs=['fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785']
- `m3.false_negative`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.false_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.micro_precision`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.micro_recall`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']
- `m3.true_positive`: runs=['cc47bffe-99c0-4084-a3f0-3c4359fbe0e4', 'fe4eef45-a22b-4fbe-b21c-ff996da5e9b9']; case_runs=['16eb854b-956e-4f22-b3c2-9713c0bde61c', '180558e6-71f3-41cd-9483-853d9e1670e2', '26b50558-aa40-4d21-a98f-9a299f137014', '2ce612ed-a370-432a-87b4-4dbbf1ff2247', '2d828d1b-1f7a-4080-81d8-ec503488f898', '55614a99-f739-4c1d-b2f2-afc7aecf314a', '730b4860-dbf7-4301-a48e-bda5db66296c', '931d23d4-14ab-4fbf-b213-74f6ddc7973a', 'aabb359f-acbb-4b81-a25d-c04cd730c9e8', 'c1e26373-9390-489a-ace9-95db8656292a', 'df905299-1f79-4e71-9588-d381f6c2c974', 'e627f284-d70d-47a1-a41e-903ab1a1142a', 'faaaa49c-007c-41a3-9eba-b173d504e785', 'fed93fbd-fd0c-4e62-aa4d-469935f4866f', 'fef17dd5-2963-4de4-8cb9-0112d17935bc']

## Artifacts

- `provider-snapshot:6f23e9a0efccc6b88a9a2da60a8cfa43fa153f90da84123d5b1d1c1762cc1b1c`
- `provider-snapshot:2c7c06aa468439a08675cab1551ede352234656ff08a6b0ea00e04ceddf97a27`
- `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`
