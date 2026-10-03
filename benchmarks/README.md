# Benchmark evidence maintenance

<!-- BEGIN GENERATED EVALUATION STATUS -->
## Current formal evaluation evidence (generated)

This block is rendered from `benchmarks/**/current*.json`. Run `make evidence-doc` after benchmark changes; `make evidence-doc-check` fails when Markdown drifts from structured evidence.

| Finals target | Metric | Observed | Threshold | Status |
| --- | --- | ---: | ---: | --- |
| `source_category_coverage` | `m1.source_category_count` | 8 | >= 7 | **pass** |
| `enrichment_precision` | `m3.micro_precision` | 99.659% | >= 95.000% | **pass** |
| `enrichment_recall` | `m3.micro_recall` | 99.659% | >= 95.000% | **pass** |
| `qa_accuracy` | `m6.answer_accuracy` | 100.000% | >= 95.000% | **pass** |
| `qa_interactive_latency` | `m6.interactive_latency_seconds` | 4.032s | <= 5.000s | **pass** |

Current CompetitionReport: `2735331f-1f7d-419c-80d2-72c4ce157b5f` on `deployment:0e16e1b574d5b6383434e7fc80f64cc4`.

M1 fixed window `2026-10-01T10:00:00+00:00` → `2026-10-01T14:02:00+00:00`: 12/12 evaluable samples, p50 357.709s (5.96min), p95 7241.893s (2.01h), within 6h 100.000%; source categories=8.

Selected M3 runs aggregate to TP=292, FP=1, FN=1, precision=99.659%, recall=99.659%. Controlled engineering recovery `engineering-fault-recovery@4` is 100.000% across 3 cases.

Evaluation areas not selected into the current CompetitionReport: `M2 parser/entity/evidence diagnostics`, `Agent runtime`, `Long Investigation completion`, `Security adversarial hard gates`, `Security adversarial breadth`. Their separate controlled/diagnostic evidence is not mixed into the report's six-run formal profile.

Across the evaluation infrastructure, 85/87 core metrics have durable observations at the current MetricDefinition revision; 15 metric groups are observed and 2 are partial. The only unobserved core metrics are `runtime.capability_external_cost`, `runtime.model_provider_cost`; both are exact monetary costs that remain absent when the provider/executor does not report them and are never inferred from token counts or public price tables.

Query the durable rows with `make benchmark-query METRIC=m3.micro_precision`; reproduce the report projection with `make competition-render-doc`; refresh every maintained evidence projection with `make evidence-doc`; verify without writes with `make evidence-doc-check`.
<!-- END GENERATED EVALUATION STATUS -->

The benchmark tree stores reviewable projections of the durable evaluation state. Measurement logic remains in executable runners and `packages.evaluation`; Markdown is a presentation surface and must not become an independent source of metric values.

## Evidence flow

The maintained flow is:

```text
runtime / provider observation
        ↓
benchmark runner
        ↓
PostgreSQL BenchmarkRun / MetricObservation
        +
machine-readable result JSON
        ↓
deterministic documentation renderer
        ↓
generated README / site status block
        ↓
CompetitionReport from explicit benchmark run IDs
```

Benchmark runners own denominators, eligibility, timestamps, metric definitions and durable provenance. Result JSON exposes the same run coordinates plus human-debuggable diagnostics. Documentation renderers consume result JSON only; they do not query PostgreSQL and they do not reimplement scoring rules.

## Maintenance rules

Dynamic counts, percentages, latency values, benchmark run IDs and evaluated/not-evaluated states belong in generated blocks. Explanatory prose may define semantics, failure classes and operational interpretation, but it must not copy a current metric value by hand. A new benchmark result is accepted into documentation by regenerating its JSON snapshot and renderer output together.

Generated blocks carry explicit begin/end markers and a source-file reference. `--check` mode recomputes the block and fails when the checked-in Markdown differs, which lets CI detect stale evidence without rerunning live providers. Reviewers should read the JSON diff first and the Markdown diff second.

Historical truth stays in durable `BenchmarkRun`, `BenchmarkCaseRun`, `MetricObservation` and `CompetitionReport` rows. A mutable `current-result.json` is only the repository's reviewed pointer to the evidence currently presented in docs; it never replaces the database provenance or an explicit CompetitionReport run set.

Competition reports continue to require explicit run IDs from one deployment revision. Documentation automation must not select “the newest run” and silently compose a report, because recency is not an evaluation policy.

The reviewed current projections are split by evidence type instead of forcing unlike states into one document:

- `m1/current.json|md` — formal M1 run plus steady-state latency and provisional/final delivery diagnostics;
- `m2/current.json|md` — controlled parser/replay/entity/evidence/conflict diagnostics; it does not replace M3 competition P/R;
- `m3/current-structured.json` and `m3/current-csaf-vex.json` — frozen-world enrichment scorer outputs used by registered M3 runs;
- `qa/current-*-preflight.json` + `qa/current-preflight.md` — no-model gold-provenance and live-readiness evidence only;
- `qa/current-live-batch.json` + `qa/current-product*.json` + `qa/current-session*.json` — reviewed formal Product/session QA batch artifacts and the exact frozen manifests/results selected into the current report;
- `investigation/current-readiness.json|md` — prospective-denominator readiness only, never an Agent score;
- `fault-recovery/current.json|md` — formal controlled engineering fault/recovery BenchmarkRun;
- `retrieval/current.json|md` — diagnostic PostgreSQL lexical execution-plan/latency regression evidence; it does not replace QA relevance/accuracy;
- `agent-runtime/current.json|md` — controlled M5 runtime regression over acquisition, capability, delegation, fallback, conflict preservation, recovery and bounded-stop owners; it is not a live-external Agent score;
- `evaluation-infra/current.json|md` — metric-contract and provenance-closure readiness for the evaluation system itself, including explicit unobserved metrics;
- `competition/current-run-set.json` + `competition/current.json|md` — explicit same-deployment aggregation of the formal selected runs.

Run `make evidence-doc-check` to recompute every deterministic Markdown projection from its checked-in machine-readable source. This command does not call external providers and does not mutate benchmark state.

For a formal multi-module batch, freeze the DeploymentRevision while the worktree is clean and send
runner JSON/Markdown to an untracked staging location first. Running a benchmark directly into a
tracked `current.*` file makes the repository dirty and changes the deployment coordinate seen by the
next runner. After every selected run is durable and the combined report succeeds, copy the reviewed
machine-readable artifacts into `benchmarks/` and regenerate presentation Markdown. Evidence
publication is therefore a final projection step, not part of measurement execution.
