# `packages.monitoring`

<!-- BEGIN GENERATED MONITORING STATUS -->
## Current M1 evidence (generated)

Suite `m1-monitoring-current@21`, run `651b4167-a2a2-4af3-a74a-0630d5ac1916`, deployment `deployment:0e16e1b574d5b6383434e7fc80f64cc4`.

| Measurement | Current result |
| --- | ---: |
| Product source categories | 8 |
| Raw scheduled candidates | 244 |
| Excluded bootstrap/backfill candidates | 232 |
| Evaluable steady-state samples | 12/12 |
| End-to-end p50 | 357.709s (5.96min) |
| End-to-end p95 | 7241.893s (2.01h) |
| End-to-end max | 7241.893s (2.01h) |
| Within 6h | 100.000% |
| Delivery status | `evaluated_deadline` |
| Provisional independent-provider delivery | 8/13 (61.538%) |

Latency is source event time → earliest Knowledge commit. `monitoring_diagnostics` keeps provider-discovery, queue-dispatch and ingestion-commit components separate; bootstrap/input/output backfill stays outside the steady-state denominator.

Current diagnostic split: raw=244, eligible=12, excluded=232. Read the complete machine result in `benchmarks/m1/current.json` and reproduce the Markdown projection with `make m1-render-doc`.

### Live data-plane status (generated)

Public continuous-monitoring epoch: `2026-10-02T04:19:42+08:00`. Pre-epoch rows are bootstrap/corpus-prefill and stay outside public runtime throughput.

Source contract: 101 catalog entries → 66 executable sources → 39 scheduled monitors; 7/8 categories are actively scheduled and `assets` remains query-time.

Current health: 29 healthy / 8 degraded / 2 blocked / 0 warming. Last-hour runtime: run success 82.353%, queue p95 10.931s, execution p95 9.436s, fresh changes 19, fresh contributing sources/categories 1/1. Public-epoch Evidence integrity: 100.000%.

`benchmarks/data-plane/current.json` owns 1h/6h/24h/7d rolling windows plus chart-ready hourly/category series; `make data-plane-metrics` refreshes the snapshot.
<!-- END GENERATED MONITORING STATUS -->

`packages.monitoring` is the implementation owner of M1 acquisition lifecycle and source runtime state. Technical Design 1 defines the processing paths and M1→M2 boundary; this module records how scheduling, acquisition runs, cursors, retries, and query-time acquisition are concretely executed.

## Durable state

`SourceStateModel` stores cursor, last attempt/success/change, next due time, failure count, backoff, and rate-limit state. `AcquisitionRunModel` stores one durable collection/query attempt with trigger, parent run, query spec, cursor in/out, status, timestamps, attempt, and error fields.

An external request is not considered a completed acquisition merely because the provider returned bytes. Completion happens after the selected downstream path accepts the data and the run/cursor transition commits.

## Scheduled collection path

`scheduler/service.py` selects enabled sources whose `next_due_at` has passed, skips sources in backoff or with an active run, locks source state with `SKIP LOCKED`, creates a queued acquisition run, and writes a `collection.requested` outbox event in the same transaction.

The scheduling policy only has operational meaning while the control loop and collection consumer are alive. The canonical unattended path is `make data-plane-up`: Compose keeps `apps.worker.scheduler` running and gives the `collection` queue its own `worker-collection` process. PostgreSQL/broker/task-bus remain restartable durable services; raw Evidence artifacts use the host-backed filesystem ArtifactStore by default so container recreation cannot erase evidence bytes. Runtime startup first runs a one-shot ownership reconciliation for the host bind mount, then `runtime-entrypoint.sh` performs the same write/delete probe under the non-root runtime UID before scheduler/workers are allowed to start. This keeps a legacy root-owned `sha256/` tree from degrading individual sources with delayed `artifact_store_unavailable` failures. This separates monitoring freshness from enrichment/projection backlog and removes terminal lifetime or Docker-daemon restart as an implicit scheduler dependency. `make data-plane-status` is the operator check; host-process `make scheduler` / `make worker-collection` remain debugging paths.

The normal polling interval and catch-up cadence are separate concerns. A source may opt into `schedule_policy.catchup_interval_seconds`. When a completed adapter cursor reports `backfill_pending=true`, `complete_collection_run` shortens `SourceState.next_due_at` to the configured catch-up cadence instead of leaving the source parked until its ordinary polling interval. `oss-security` uses this path while historical catch-up remains incomplete. The adapter still selects newest unseen messages first, so catch-up work cannot sit in front of newly published disclosures. Numeric tuning remains owned by the versioned source definition.

Provider quota is a third scheduling input. A `DiscoveryBatch` may return `rate_limit_state`; successful completion persists it on `SourceState`. For sources whose `rate_limit_policy.adaptive_schedule=true`, `run_service.py` derives the next due time from the provider's remaining requests/reset time and the number of requests actually consumed by that discovery pass, while preserving configured request headroom and a minimum interval. This keeps the policy provider-agnostic: GitHub parses GitHub headers in its adapter, while monitoring only reasons over the normalized budget state. When quota metadata is absent, the fixed interval chosen by the scheduler remains in force. Catch-up cadence and quota cadence compose conservatively: the later safe due time wins.

Failure backoff is also a lower bound, never an accelerated retry schedule. If a daily source fails with a transient network error, `fail_acquisition_run` preserves the later of the already-scheduled next run and the calculated backoff; a single failure can no longer turn a daily source into a 5-minute retry loop. HTTP 401/403 at public adapter boundaries are classified as `provider_blocked` and receive a 24-hour cooldown, keeping long-running health honest without hammering a provider that has rejected automated access.

Operational measurement lives in `benchmarks/data-plane/current.json`. It separates scheduled monitoring from query-time/investigation ingestion and exports 1h/6h/24h/7d rolling windows plus hourly/category series for fresh changes, backfill, queue delay, execution time, event→Knowledge latency, write amplification, document growth, source concentration, source health, and public-epoch Evidence integrity. Formal M1 benchmark evidence stays frozen separately under `benchmarks/m1`; current runtime health never overwrites competition benchmark history.

This matters for mutable snapshot sources such as `github-target-repos`. An hourly snapshot can miss a repository revision that appears and is superseded between polls. A blindly shortened interval is also unsafe because the anonymous GitHub primary quota is shared with other GitHub reads. Adaptive scheduling uses the observed quota instead: authenticated environments naturally poll more densely when the provider grants a larger bucket, while anonymous environments reserve enough headroom for other work instead of repeatedly entering provider backoff.

`oss-security` also bounds one discovery run with `discovery_method.max_items` and uses `schedule_policy.catchup_interval_seconds` between incomplete catch-up batches. Smaller batches reduce the replay work exposed to one late transport failure, while repeated catch-up scheduling supplies throughput across batches. The adapter retries one transient HTTP transport failure before classifying the run as `fetch_failed`. The source JSON owns the numeric tuning values; this README documents their semantics so configuration changes do not require hand-updating duplicated numbers.

`runtime.execute_collection_run` resolves the persisted source definition and dispatches by `RetentionMode`:

```text
hot_window       -> HotWindowCollector
selective_index  -> StructuredIndexCollector
durable_managed  -> ManagedContentCollector
incident_signal  -> IncidentSignalCollector
time_bounded     -> not scheduled; query-time only
```

The acquisition cursor advances only after the downstream owner reports accepted processing. No-change runs can complete without fabricating a change event.

### Freshness decomposition

M1 latency is diagnosed as three different delays instead of treating every large end-to-end number as scheduler latency:

```text
source event_time
  -> Observation.observed_at          provider/discovery delay
  -> KnowledgeRevision.committed_at  ingestion/commit delay

AcquisitionRun.created_at
  -> AcquisitionRun.started_at       queue/dispatch delay
```

The investigation that motivated this contract found that an apparent high-latency `oss-security` result came from a legacy-cursor catch-up rather than queue or Knowledge-commit delay. The run's output cursor reported `backfill_pending=true`, so the evaluator now treats that run as historical catch-up and leaves it outside steady-state monitoring latency. Current numeric evidence is generated by the M1 benchmark pipeline rather than copied into this module README.

The M1 evaluator therefore rejects a latency candidate when either the acquisition input cursor or output cursor carries `backfill_pending=true`. Checking only `cursor_in` is insufficient during a migration run: a legacy cursor can enter without the marker and discover during execution that historical work remains. This exclusion changes benchmark classification only; the production catch-up cadence above changes how quickly the runtime drains that historical work.

## Query-time acquisition

`acquisition/AcquisitionService` is the only generic entry for M3 code that needs fresh provider data. It creates its own durable `AcquisitionRunModel`, records the query spec and parent run, invokes `SourceAdapter.query`, and closes the run as success/no-change/failed.

This service deliberately stops at `IngestEnvelope`. The caller must still send returned envelopes through `EvidenceIngress` or the appropriate downstream processor. Query-time acquisition therefore does not bypass M2.

## Run transitions and recovery

`run_service.py` owns start/complete/fail transitions. Collection runs are idempotent at the run-id boundary: re-executing a terminal or already-running run returns no new work. Failure classification maps provider/runtime exceptions into stable statuses and backoff behavior.

The scheduler process also calls stale-run recovery. Recovery changes durable run/source state and emits work through the normal outbox path instead of invoking collectors inline.

For a source that opts into catch-up scheduling, successful completion can move `next_due_at` earlier than the value chosen when the run was queued. This update happens in the same durable completion transaction as `cursor_out`, so a crash cannot persist “backfill pending” while losing the accelerated next-due decision.

## Outbox interaction

Monitoring writes `collection.requested` and other domain events into the shared outbox inside PostgreSQL transactions. `apps.worker.scheduler` dispatches committed events to Celery. Broker delivery is at-least-once, so collection consumers and downstream writes must remain idempotent.

For `durable_managed` sources the collection path also depends on the configured ArtifactStore before Evidence ingress can commit. The canonical single-host development/runtime path is the host-backed content-addressed filesystem under `.local/secfusion-artifacts`; `make dev-up` does not require an S3 service. LocalStack is started only by the explicit S3 integration path, while other S3-compatible backends remain deployment/compatibility options. A deployment must still keep one coherent artifact namespace: persisted legacy `s3://bucket/key` locators must resolve against the backend that actually owns those immutable bytes rather than whichever S3 endpoint happens to be configured later.

The historical freshness investigation exposed exactly that configuration drift: pre-cutover artifact metadata could outlive the temporary LocalStack namespace that originally held the bytes. The durable-filesystem cutover makes new local writes survive container recreation and keeps scheduler/worker processes on the same host-backed namespace. Historical S3 locators remain immutable metadata and are recovered only by exact-content replay/compatibility resolution; current run counts and timing evidence stay in the generated M1 benchmark artifacts rather than this module README.

Artifact-store availability failures are surfaced as `ArtifactStoreUnavailable`, recorded as acquisition status `dependency_unavailable`, and retried with the dependency-unavailable backoff owned by `run_service.py`. They are kept separate from provider `fetch_failed`, provider rate limiting, and generic code defects, so an internal storage outage does not inherit the generic internal-error policy. Existing content-addressed replay recovery remains the repair path for historical artifact metadata whose blob is absent from the active backend: the replay must reproduce the exact content hash and make the persisted Evidence locator readable again. Backend migration does not rewrite immutable Evidence metadata merely because new writes use a different URI scheme; the active ArtifactStore owns compatibility resolution for any accepted legacy locator.

## Design → implementation map

TD1 的 M1 责任已经落到四个明确 owner：`packages.sources` 持有 source capability；`scheduler/service.py` 决定 due work；`run_service.py` 持有 acquisition lifecycle；`acquisition/service.py` 持有 query-time provider read；`runtime.py` 只根据 `RetentionMode` 把一次 run 交给对应 downstream owner。Product WORLD / OBSERVATORY 展示的 source health 直接读取这些 durable `SourceStateModel` / Data Plane read model，不维护第二套演示状态。

比赛口径也保持分离：来源类别覆盖来自 versioned source inventory；监测时效和运行健康来自真实 acquisition state。provider 临时不可达不会让一个已拥有的 source category 从覆盖定义里消失，反过来一次 live probe 成功也不会凭空增加产品 coverage。

## Dependency boundary

Allowed package dependencies: `shared`, `sources`, `intelligence`, `monitoring`.

Monitoring may compose M2/M3 ingestion services because it owns runtime dispatch, but it does not own their storage semantics. It must not depend on `enrichment`, `investigation`, or `evaluation` policy.

## Verification

```bash
uv run pytest packages/monitoring/tests -q
uv run pytest tests/test_m1_benchmark_contract.py -q
make integration-core
```

The real core integration exercises PostgreSQL, the separated Redis roles, acquisition state, outbox delivery, and M3 handoff.
