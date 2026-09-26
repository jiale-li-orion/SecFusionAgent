# `packages.evaluation`

`packages.evaluation` owns executable M1–M3 evaluation contracts. Requirements and Technical Design 1 define what must be measured; this module defines the concrete denominator identities, validation models, aggregation behavior, and regression tests so later benchmark runners do not reinterpret the metrics.

## Competition reporting profile

Requirements remain the authority for competition targets. The executable evaluation layer uses the finals target as the stricter development profile: enrichment micro precision and recall both target `>=95%`. The preliminary-round report can reuse the same fixed benchmark and report the required accuracy/precision view without maintaining a second enrichment ontology.

The scoring threshold does not redefine the data contract. Formal enrichment P/R is always calculated over the versioned, benchmarked closed set; open semantic discoveries and non-benchmarked support edges do not enter the denominator merely to improve coverage.

## Source category coverage

`PRODUCT_SOURCE_CATEGORY_ORDER` freezes the eight product categories in product order:

```text
vulnerability / development / academic / vendor /
independent / normative / assets / incidents
```

`source_coverage_report` derives support from `config/source-inventory.json`. A category counts only when inventory ownership is `owned` and backed by a fixed/grouped executable owner. Provider reachability and dynamic resolution do not inflate category coverage.

Website catalog conformance is tested against the same category order.

## Source delivery coverage

`SourceDeliveryKey` defines the fixed-window source event identity:

```text
source_id
external_object_id
external_revision OR content_hash
```

At least one revision discriminator is required. `source_delivery_coverage` separately reports expected, accepted expected, missed, and unexpected keys. Unexpected observations do not increase the coverage numerator.

## Monitoring latency

`MonitoringLatencySample` measures `published_at -> M2 available_at/committed_at`. Samples without reliable publication time remain in `evaluable_coverage` but are excluded from numeric latency aggregation.

The helper reports p50, p95, max, and the rate within six hours. These are diagnostics; the competition text defines the six-hour threshold but does not define one aggregate statistic as the official gate.

## M2 diagnostic metrics

M2 correctness is reported separately from formal M3 enrichment P/R:

- `parser_field_accuracy` — extracted value + locator correctness on fixed source revisions;
- `replay_suppression_accuracy` — replay does not create duplicate factual versions;
- `entity_resolution_precision / recall` — same-object decisions on a gold identity-pair set;
- `evidence_correctness` — accepted claim/relation evidence resolves and actually supports the assertion;
- `conflict_preservation` — competing source assertions remain represented instead of becoming last-write-wins.

These metrics diagnose why enrichment failed; they are not added to the official P/R numerator/denominator.

## Enrichment gold identity

`EnrichmentFactKey` is a closed-set benchmark fact, not a generic Knowledge record. It contains:

```text
root_object_key + root_object_type
vocabulary_revision
dimension
kind = claim | relation
predicate_or_relation_type
normalized value or target id
target_object_type when relevant
qualifier keys + normalized qualifier
temporal scope
```

Construction validates the fact against `enrichment-v1`: the term must be canonical and `benchmarked=True`, dimension must match, subject/target shape must match, required qualifiers must be present, and vocabulary revision must be supported.

This prevents fixture authors from creating gold that the runtime vocabulary itself considers invalid.

Benchmark dimension membership is evidence-conditional. A dimension enters a case gold set when the frozen world/source snapshot contains adjudicable evidence for that dimension; the closed set does not imply every vulnerability must have every one of the twelve dimensions. Missing source evidence therefore does not create an artificial FN, while a system miss on evidence that exists in the frozen snapshot does.

## Evidence-aware scoring

`EnrichmentPrediction` wraps a fact with evidence references and `evidence_correct`. A tuple match without valid evidence is not a TP. If the fact has only invalid-evidence predictions, it contributes FP and the corresponding gold remains FN. A valid duplicate dominates invalid duplicates for the same fact.

The scorer returns micro precision/recall and per-dimension scores plus dimension-macro P/R. Empty prediction with non-empty gold reports zero precision/recall instead of a false perfect precision.

Canonical Knowledge can contain non-benchmarked information. Open text, repository support edges, intermediate asset edges, and exploratory semantic relations stay available to the product while remaining outside the formal closed-set scorer.

## Gold source policy

Gold prefers evidence that can be adjudicated independently of the model under test:

- structured authority records: CVE Record, NVD, OSV, GHSA, CSAF/VEX, CISA KEV, FIRST EPSS;
- repository relations: fixed repository snapshot plus commit/release ancestry;
- asset relations: fixed `AssetObservation` plus product/version/applicability gold;
- paper exact association: fixed paper revision and exact identifier/text evidence;
- open semantic research relations: human dual annotation/adjudication before they can become official gold. LLM-as-judge alone does not create formal gold.

## Benchmark strata and snapshot identity

The fixed suite must include at least:

- structured-only CVE enrichment;
- multi-source conflict on severity/version assertions;
- CVE 5.x version ranges;
- OSV SEMVER/ECOSYSTEM and GIT fixed ranges;
- release containment for fixed commits;
- NVD CPE AND/OR configurations;
- CSAF/VEX `not_affected` / `under_investigation`;
- KEV exploited vs non-KEV cases;
- EPSS point-in-time score;
- PoC present without known exploitation and known exploitation without public PoC;
- time-bounded asset observation + affected-version matching;
- paper exact association and semantic-relation cases;
- Incident strong-anchor association;
- alias/entity ambiguity and wrong-version traps.

A benchmark case freezes `world_snapshot`, source availability, source revisions, vocabulary revision, and evaluator revision. Historical evaluation must not silently consume later provider updates, patches, or postmortems.

## Deterministic baseline comparison

The baseline used to measure Agent/semantic gain contains no LLM planner or free semantic relation generation. It performs exact identifier normalization, structured provider lookup, fixed schema projection, product/package identity mapping, source-specific applicability evaluation, repository graph closure, KEV/EPSS exact joins, asset observation joins, exact paper association, EvidenceRef binding, conflict preservation, and unknown-on-miss behavior.

Agent/semantic improvements are measured as additional canonical recall/gap resolution under the same gold and evidence rules, with latency/cost reported separately rather than by changing the denominator.

## Current scope

This module intentionally stops at M1–M3 contracts. M4–M6 task/tool/policy evaluation, trajectory intervention/replay, QA scoring, and security benchmark runners will be added only after those runtime contracts are frozen.

## Dependency boundary

Allowed dependencies: `shared`, `sources`, `intelligence`, `evaluation`.

Evaluation must not depend on the runtime decisions of `monitoring`, `enrichment`, or future Agent modules; it evaluates their outputs through stable contracts.

## Verification

```bash
uv run pytest packages/evaluation -q
```
