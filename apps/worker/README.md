# `apps.worker`

`apps.worker` owns background-process bootstrap and event-to-task wiring across the current TD1 data plane and TD2 Task Event control plane. It does not own collection, enrichment, investigation, indexing, projection, policy, or scheduling semantics; those remain in their domain/runtime packages and are composed here only at process boundaries.

## Background model operating mode

Set `SECFUSION_BACKGROUND_LLM_ENABLED=false` and recreate the acquisition scheduler, Task Event scheduler and general
worker. The local Compose default is false; standalone `Settings` keeps its
previous enabled behavior unless explicitly configured. This skips document dense
embedding and semantic/normative model stages after committing lexical indexes,
prevents automatic WATCH episode spawning, and blocks editorial at both schedule
and execution time. Editorial additionally requires `SECFUSION_EDITORIAL_ENABLED=true`;
the local Compose default for editorial is now false too.

Collection, raw evidence storage, lexical search, deterministic vulnerability
enrichment, projections, user QA, investigation planning and user-requested report
generation retain their normal configuration. Do not clear the shared model API key
or stop the indexing/investigation queues to achieve this mode.

Already running calls finish on graceful worker shutdown. Queued editorial tasks
return `disabled`; document tasks finish lexical processing without spending model
tokens. Existing reports and semantic results remain intact. Re-enabling the flag
affects future processing; skipped document model stages and WATCH triggers are not
automatically backfilled. Reprocess selected revisions deliberately if needed.

## Processes

`celery_app.py` configures the Celery application using the dedicated broker Redis and defines queue routing. Current queue families are collection, normalization, enrichment, investigation, and indexing/projection.

`scheduler.py` is a lightweight control loop. Before its first tick it atomically
synchronizes configured source definitions and monitoring schedule rows, retrying
startup failures without resetting existing cursors or health. Each tick:

1. recovers stale acquisition runs;
2. schedules due sources and writes outbox events;
3. dispatches committed outbox events to Celery;
4. sleeps for `scheduler_tick_seconds`.

The scheduler never performs provider collection inline.

### Default local runtime

`make dev-up` starts PostgreSQL plus the three Redis roles. `make data-plane-up` is the canonical long-lived runtime path (`make dev-runtime-up` remains its lower-level alias): it runs migrations and registry/Skill synchronization, then starts Compose-managed acquisition `scheduler`, Task Event `task-event-dispatcher` + `task-event-scheduler`, a dedicated `worker-collection`, and the general Celery `worker` under the `runtime` profile. PostgreSQL, broker Redis, task-bus Redis and all runtime processes use restartable durable configuration; raw Evidence/runtime artifacts are bind-mounted from the host-backed `.local/secfusion-artifacts` filesystem store. LocalStack is now an explicit S3 compatibility/integration profile rather than a dependency of the default long-running data plane. Closing a terminal, restarting Docker, or rebuilding app containers therefore does not intentionally reset durable data or leave either the acquisition plane or Task Event control plane stopped once Docker itself is available. The hot-cache Redis remains disposable by design and rebuilds from authority.

`worker-collection` consumes only the `collection` queue with its own concurrency budget. The general worker consumes `enrichment,investigation,indexing`. This isolation keeps scheduled monitoring and catch-up reads from waiting behind projection/enrichment backlog after a long runtime outage.

The Product Observatory uses a bounded Celery control ping and `active_queues` probe to report responding workers and consumers for all four queues. This is a point-in-time control-plane observation, not durable heartbeat, uptime accounting or alert delivery. A missing reply is shown as unobserved/unavailable rather than assuming that a worker is healthy or dead.

The runtime image owns its own `/app/.venv`. Root `.dockerignore` excludes the host virtualenv and local caches from the build context, preventing `COPY . .` from replacing container interpreter entry points with host-specific symlinks or shebangs.

Use `make data-plane-status` to inspect dependencies plus all five runtime control/worker processes and `make data-plane-logs` for their logs. `make data-plane-down` stops only runtime processes; `make dev-down` tears down runtime plus dependencies. Host-process `make scheduler`, `make task-event-dispatcher`, `make task-event-scheduler`, `make worker`, and `make worker-collection` remain debugger paths. Formal live QA still quiesces only the three Knowledge-writer processes (`scheduler`, `worker-collection`, `worker`) long enough to freeze one Knowledge head; the Task Event loops may remain up because the general worker is stopped and no Agent execution can mutate Knowledge through that path.

`task_event_dispatcher.py` is the independent Task Event Plane delivery loop. It reads committed `task_event_deliveries` from PostgreSQL and publishes them to `redis_task_bus_url` Redis Streams. It does not reuse Celery broker routing.

`task_event_scheduler.py` is the consumer-side Task Event Plane loop. It reads the Task Bus through a Redis consumer group, reloads each event from PostgreSQL, applies the deterministic Task Runtime dependency relevance gate, and maps durable queued-Role `TaskPatched` events to coarse Celery tasks. Database scheduling commits before broker dispatch; Redis `XACK` happens only after any required Celery send succeeds. Unacknowledged messages are reclaimable after `task_event_claim_idle_ms`; replay may redeliver the coarse task, while the PostgreSQL queued-run claim prevents concurrent Role execution.

Before reading the stream, the same loop asks Runtime execution recovery to reconcile stranded queued Role runs and stale running episodes. Queued recovery emits a new durable `Progress` dispatch event for an unexpired run, or closes an expired/invalid run with explicit TaskRun and ExecutionRun state. Running recovery closes only after the absolute deadline; it does not replay a synchronous DecisionRole model call. The dispatcher publishes recovery events through the normal outbox; the scheduler only maps dispatch recovery events bearing the Task Runtime recovery producer and matching run ID to Celery. A pending or recent dispatch event suppresses another retry. Recovery errors are logged without stopping ordinary Task Event consumption.

## Outbox topic routing

The scheduler currently translates committed topics as follows:

| Topic | Celery task |
|---|---|
| `collection.requested` | `secfusion.collection.run` |
| `knowledge.changed` | `secfusion.projection.knowledge_changed` |
| `incident.changed` | `secfusion.projection.incident_changed` |
| `enrichment.requested` | `secfusion.enrichment.vulnerability` |
| `document.index.requested` | `secfusion.indexing.document_revision` |
| `editorial.requested` | `secfusion.editorial.run` (both model/editorial flags required) |

Unknown topics fail explicitly instead of being dropped.

## Task composition

`tasks.py` contains thin task entry points and runtime composition helpers:

- collection delegates to `packages.monitoring.runtime.execute_collection_run`;
- knowledge/incident change tasks rebuild current projections;
- vulnerability enrichment creates or resumes a deterministic background Enrichment TaskRun and executes the shared `EnrichmentRole`; provider/graph primitives still use acquisition, EvidenceIngress and Knowledge Writer;
- delegated EnrichmentRole and queued InvestigationRole execute through `QueuedRoleExecutor`; `apps/enrichment_runtime.py` and `apps/investigation_runtime.py` own their production composition;
- document indexing builds lexical state first, then builds dense embeddings and semantic/normative extraction only when background model work is enabled and providers are configured. A typed `DocumentMaterialRejectedError` is a terminal skip: the worker logs the document revision and returns zero without invoking providers. Other processing errors propagate normally.

Task Event scheduling and Role execution remain separate boundaries: Redis delivery only chooses the coarse Role task; the Celery handler constructs the domain runtime and the Task Runtime executor performs the durable claim. Investigation composes local Perception with official NVD reads, registered public HTML sources and exact GitHub development records for configured repositories. `apps/nvd_observation.py`, `apps/registered_source_observation.py` and `apps/github_investigation_observation.py` register bounded bindings through the Broker, Policy/Budget, AcquisitionRun, raw runtime artifacts and independent Evidence promotion. Generic web search, arbitrary repositories/assets and sandbox execution remain outside these bindings.

Background vulnerability enrichment no longer constructs executable contracts locally. `_enrich_vulnerability` passes the trigger provenance to `ensure_background_vulnerability_enrichment_run`, which enters the same `TaskIntent → task_admission → TaskContract` path used by other executable work. Any caller that enqueues this Celery task cannot bypass worker-side admission or the M3 Evidence/Knowledge write path.

Celery uses late acknowledgement, reject-on-worker-loss, prefetch 1, and at-least-once delivery semantics. Task handlers therefore rely on run ids, EvidenceIngress idempotency, Knowledge processing-run identity, and revision-aware projection rebuilds rather than assuming exactly-once broker delivery.

## Redis separation

`redis_broker_url` is reserved for Celery transport. Hot Bug and Incident transient state use `redis_hot_cache_url`. Task Event delivery uses `redis_task_bus_url` with no-eviction/persistent Stream semantics. Worker composition must not collapse these three failure domains into one Redis role.

## Automatic public editorial

With both `SECFUSION_BACKGROUND_LLM_ENABLED=true` and
`SECFUSION_EDITORIAL_ENABLED=true`, the existing scheduler reserves one UTC slot
per `SECFUSION_EDITORIAL_INTERVAL_HOURS` (default 6), writes `editorial.requested` to
the durable outbox and dispatches `secfusion.editorial.run` to the investigation queue.
The worker has an 840-second async budget, 870-second soft/900-second hard task limits;
its 1200-second database lease fences publication and allows scheduler recovery.
Model calls use the recorded provider and existing independent review gate. Private
material is never selected. `editorial_runs` retains selection, attempts, status,
brief identity and error type without secrets. No material is a normal skipped run.

Local Compose disables automatic editorial by default. When explicitly enabled,
it selects at most four documents from the last 14 days. Editorial defaults off
in Settings too; the general background-model flag has a compatible enabled
Settings default and must be set explicitly for standalone processes.
Setting `SECFUSION_EDITORIAL_ENABLED=false` stops scheduling and new worker claims;
an already running job may finish. Keep the worker and scheduler on the same config.
Use `editorial_runs` ordered by `slot_at` to inspect status; published `brief_id` values
resolve through `/api/v1/intelligence/briefs/{brief_id}/report.html` after visibility checks.

## Adding background work

A new background behavior should first define its owning package service and durable event contract. Worker code then adds a topic→task mapping and a thin composition entry point. Business semantics should not originate in `apps.worker.tasks`.

## Verification

```bash
uv run pytest apps/worker/tests -q
make integration-core
```
