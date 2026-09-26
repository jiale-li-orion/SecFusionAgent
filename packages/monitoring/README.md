# `packages.monitoring`

`packages.monitoring` is the implementation owner of M1 acquisition lifecycle and source runtime state. Technical Design 1 defines the processing paths and M1→M2 boundary; this module records how scheduling, acquisition runs, cursors, retries, and query-time acquisition are concretely executed.

## Durable state

`SourceStateModel` stores cursor, last attempt/success/change, next due time, failure count, backoff, and rate-limit state. `AcquisitionRunModel` stores one durable collection/query attempt with trigger, parent run, query spec, cursor in/out, status, timestamps, attempt, and error fields.

An external request is not considered a completed acquisition merely because the provider returned bytes. Completion happens after the selected downstream path accepts the data and the run/cursor transition commits.

## Scheduled collection path

`scheduler/service.py` selects enabled sources whose `next_due_at` has passed, skips sources in backoff or with an active run, locks source state with `SKIP LOCKED`, creates a queued acquisition run, and writes a `collection.requested` outbox event in the same transaction.

`runtime.execute_collection_run` resolves the persisted source definition and dispatches by `RetentionMode`:

```text
hot_window       -> HotWindowCollector
selective_index  -> StructuredIndexCollector
durable_managed  -> ManagedContentCollector
incident_signal  -> IncidentSignalCollector
time_bounded     -> not scheduled; query-time only
```

The acquisition cursor advances only after the downstream owner reports accepted processing. No-change runs can complete without fabricating a change event.

## Query-time acquisition

`acquisition/AcquisitionService` is the only generic entry for M3 code that needs fresh provider data. It creates its own durable `AcquisitionRunModel`, records the query spec and parent run, invokes `SourceAdapter.query`, and closes the run as success/no-change/failed.

This service deliberately stops at `IngestEnvelope`. The caller must still send returned envelopes through `EvidenceIngress` or the appropriate downstream processor. Query-time acquisition therefore does not bypass M2.

## Run transitions and recovery

`run_service.py` owns start/complete/fail transitions. Collection runs are idempotent at the run-id boundary: re-executing a terminal or already-running run returns no new work. Failure classification maps provider/runtime exceptions into stable statuses and backoff behavior.

The scheduler process also calls stale-run recovery. Recovery changes durable run/source state and emits work through the normal outbox path instead of invoking collectors inline.

## Outbox interaction

Monitoring writes `collection.requested` and other domain events into the shared outbox inside PostgreSQL transactions. `apps.worker.scheduler` dispatches committed events to Celery. Broker delivery is at-least-once, so collection consumers and downstream writes must remain idempotent.

## Dependency boundary

Allowed package dependencies: `shared`, `sources`, `intelligence`, `monitoring`.

Monitoring may compose M2/M3 ingestion services because it owns runtime dispatch, but it does not own their storage semantics. It must not depend on `enrichment`, `investigation`, or `evaluation` policy.

## Verification

```bash
uv run pytest packages/monitoring/tests -q
make integration-core
```

The real core integration exercises PostgreSQL, the separated Redis roles, acquisition state, outbox delivery, and M3 handoff.
