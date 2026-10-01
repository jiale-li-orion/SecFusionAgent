# Benchmark evidence maintenance

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

For a formal multi-module batch, freeze the DeploymentRevision while the worktree is clean and send
runner JSON/Markdown to an untracked staging location first. Running a benchmark directly into a
tracked `current.*` file makes the repository dirty and changes the deployment coordinate seen by the
next runner. After every selected run is durable and the combined report succeeds, copy the reviewed
machine-readable artifacts into `benchmarks/` and regenerate presentation Markdown. Evidence
publication is therefore a final projection step, not part of measurement execution.
