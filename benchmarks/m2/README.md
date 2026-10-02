# M2 controlled diagnostics

This directory holds the deterministic M2 diagnostic benchmark required by `Requirements-SPEC`.
It keeps parser/locator correctness, exact replay suppression, entity resolution, Evidence correctness,
and conflict preservation separate from M3 enrichment precision/recall.

The fixture workload executes production `EvidenceIngress`, `NVDCanonicalNormalizer`, and
`EnrichmentStateBuilder` against an isolated SQLite database with an in-memory ArtifactStore. The
benchmark records immutable BenchmarkCase/Suite/Run/MetricObservation rows in the normal TD3
evaluation store, so fixture state cannot pollute the long-running Data Plane.

This suite is controlled diagnostic evidence, not a competition enrichment score. Broader provider
coverage and the official enrichment threshold remain owned by M1/M3 frozen provider datasets.
