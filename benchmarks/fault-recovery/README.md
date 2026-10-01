# Engineering Fault/Recovery Benchmark

This directory owns the controlled engineering fault/recovery denominator used by `engineering.fault_recovery_success`.

The v1 suite contains two fixed cases executed against the real PostgreSQL state-transition code:

- stale acquisition recovery: a scoped injected `running` AcquisitionRun older than the timeout must become `queued` and emit exactly one pending `collection.requested` outbox event;
- outbox retry: a scoped injected pending event receives one synthetic publisher failure, remains pending with attempt/error provenance, then succeeds on the next dispatch and becomes delivered.

The benchmark adds explicit `run_ids` / `event_ids` scoping to recovery/dispatch services. Production callers omit those filters and retain their existing behavior. Benchmark operational rows live inside a SQLAlchemy savepoint and are rolled back after each probe; only TD3 BenchmarkCase/Suite/Run/MetricObservation rows persist. This lets the benchmark exercise the real locking/status-transition implementation without consuming unrelated production work or leaving fake acquisition/outbox rows behind.

`current.json` is the machine-readable current result and `current.md` is generated from it. Run `make fault-recovery` after freezing a clean DeploymentRevision, then `make fault-recovery-doc-check` to verify the projection.
