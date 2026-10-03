# Controlled M5 Agent runtime benchmark

This directory owns the machine-readable and rendered evidence for the controlled M5 runtime
regression suite. It complements prospective live Investigation benchmarks: the live denominator
measures end-to-end behavior on real Product Cases, while this suite isolates protocol owners that
need deterministic failure-chain coverage.

`current.json` is a durable projection of one `m5-agent-runtime-controlled-v1` BenchmarkRun.
`current.md` is generated from that JSON; edit neither metric value by hand.

The suite deliberately exercises the real owner for each property:

- `InvestigationRole -> Perception -> CapabilityBroker -> EvidenceIngress -> StatePatch` for
  acquisition/tool metrics;
- Enrichment child TaskRun + TaskEvent dependency wake for delegation metrics;
- `CapabilityRegistry.resolve_binding` for provider-health/fallback-rank selection;
- `InvestigationStateService.apply_patch` for conflict preservation;
- two InvestigationRole TaskRuns over the same durable Case/EvidenceNeed for recovery;
- InvestigationRole loop bounds/deadline checks for no-progress and bounded-stop metrics.

This is `live_controlled`, not `live_external`. Passing the suite proves the runtime contract under
controlled inputs; it does not replace frozen real-world Agent cases or external-provider quality
evaluation.
