# Engineering Fault/Recovery Benchmark

This directory owns the controlled engineering fault/recovery denominator used by `engineering.fault_recovery_success`.

The current controlled suite contains three fixed cases executed against the real runtime/storage
state-transition code:

- stale acquisition recovery: a scoped injected `running` AcquisitionRun older than the timeout must become `queued` and emit exactly one pending `collection.requested` outbox event;
- outbox retry: a scoped injected pending event receives one synthetic publisher failure, remains pending with attempt/error provenance, then succeeds on the next dispatch and becomes delivered.
- legacy artifact replay recovery: an immutable EvidenceArtifact is temporarily represented with its legacy `s3://` locator while the filesystem blob is absent; exact replay must restore readable bytes without rewriting the persisted URI, and the recovered bytes must match the original SHA256.

Each case still emits `engineering.fault_recovery_success`, while applicable cases additionally emit
`engineering.failure_isolation`, `engineering.retry_correctness`, and
`engineering.bounded_termination`. Missing submetrics are `not_evaluated`; one aggregate success flag
does not hide whether retry, isolation, or termination was the failing property.

The benchmark adds explicit `run_ids` / `event_ids` scoping to recovery/dispatch services. Production callers omit those filters and retain their existing behavior. Benchmark operational rows live inside a SQLAlchemy savepoint and are rolled back after each probe; the artifact-replay probe also uses a unique content-addressed object and removes it after rollback. Only TD3 BenchmarkCase/Suite/Run/MetricObservation rows persist. This lets the benchmark exercise the real locking/status-transition and EvidenceIngress implementations without consuming unrelated production work or leaving fake acquisition/outbox/evidence rows behind.

`current.json` is the machine-readable current result and `current.md` is generated from it. Run `make fault-recovery` after freezing a clean DeploymentRevision, then `make fault-recovery-doc-check` to verify the projection.
