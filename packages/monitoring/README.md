# `packages.monitoring`

`packages.monitoring` is the implementation owner of M1 acquisition lifecycle and source runtime state. Technical Design 1 defines the processing paths and M1→M2 boundary; this module records how scheduling, acquisition runs, cursors, retries, and query-time acquisition are concretely executed.

## Durable state

`SourceStateModel` stores cursor, last attempt/success/change, next due time, failure count, backoff, and rate-limit state. `AcquisitionRunModel` stores one durable collection/query attempt with trigger, parent run, query spec, cursor in/out, status, timestamps, attempt, and error fields.

An external request is not considered a completed acquisition merely because the provider returned bytes. Completion happens after the selected downstream path accepts the data and the run/cursor transition commits.

## Scheduled collection path

`scheduler/service.py` selects enabled sources whose `next_due_at` has passed, skips sources in backoff or with an active run, locks source state with `SKIP LOCKED`, creates a queued acquisition run, and writes a `collection.requested` outbox event in the same transaction.

The normal polling interval and catch-up cadence are separate concerns. A source may opt into `schedule_policy.catchup_interval_seconds`. When a completed adapter cursor reports `backfill_pending=true`, `complete_collection_run` shortens `SourceState.next_due_at` to the catch-up cadence instead of leaving the source parked until its ordinary polling interval. This is currently used by `oss-security`: live polling remains hourly, while an incomplete historical catch-up is drained at a 60-second cadence. The adapter still selects newest unseen messages first, so catch-up work cannot sit in front of newly published disclosures.

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

The 2026-10-01 investigation that motivated this contract found five apparent 16–22 hour samples from one `oss-security` run. Its queue delay was about 21 ms and Observation→Knowledge commit was 12–28 ms; the large value came from messages published the previous day being discovered during a legacy-cursor catch-up. The run's output cursor explicitly reported `backfill_pending=true`. That evidence means the online runtime was fast once work existed, while the sample itself was not a steady-state monitoring event.

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

For `durable_managed` sources the collection path also depends on the configured S3-compatible artifact store before Evidence ingress can commit. In the local stack this is the `minio` service on port 9000. `deploy/docker-compose.yml`, `config/env.example`, and `Settings` use the same development credentials; if MinIO is down, provider discovery can succeed while the acquisition run still terminates before cursor advancement. S3 transport failures are surfaced as `ArtifactStoreUnavailable`, recorded as acquisition status `dependency_unavailable`, and retried after 60 seconds. They are kept separate from provider `fetch_failed`, provider rate limiting, and generic code defects, so an internal storage outage does not impose the ordinary 15-minute internal-error backoff on monitoring recovery.

## Design → implementation map

TD1 的 M1 责任已经落到四个明确 owner：`packages.sources` 持有 source capability；`scheduler/service.py` 决定 due work；`run_service.py` 持有 acquisition lifecycle；`acquisition/service.py` 持有 query-time provider read；`runtime.py` 只根据 `RetentionMode` 把一次 run 交给对应 downstream owner。前端 Runtime Workbench 展示的 source health 直接读取这些 durable `SourceStateModel`，不是单独维护的演示状态。

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
