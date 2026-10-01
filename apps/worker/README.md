# `apps.worker`

`apps.worker` owns background-process bootstrap and event-to-task wiring across the current TD1 data plane and TD2 Task Event control plane. It does not own collection, enrichment, investigation, indexing, projection, policy, or scheduling semantics; those remain in their domain/runtime packages and are composed here only at process boundaries.

## Processes

`celery_app.py` configures the Celery application using the dedicated broker Redis and defines queue routing. Current queue families are collection, normalization, enrichment, investigation, and indexing/projection.

`scheduler.py` is a lightweight control loop. Each tick:

1. recovers stale acquisition runs;
2. schedules due sources and writes outbox events;
3. dispatches committed outbox events to Celery;
4. sleeps for `scheduler_tick_seconds`.

The scheduler never performs provider collection inline.

### Default local runtime

`make dev-up` starts dependency services only. `make data-plane-up` is the canonical long-lived M1–M3 path (`make dev-runtime-up` remains its lower-level alias): it brings up PostgreSQL/Redis/LocalStack, runs migrations and registry/Skill synchronization, then starts Compose-managed `scheduler`, a dedicated `worker-collection`, and the general Celery `worker` under the `runtime` profile. PostgreSQL, broker Redis, task-bus Redis, LocalStack S3 and all runtime processes use `restart: unless-stopped`; PostgreSQL/broker/task-bus/S3 use named volumes. Closing a terminal, restarting Docker, or rebooting the host therefore does not intentionally reset durable data or leave the scheduler stopped once Docker itself is available. The hot-cache Redis remains disposable by design and rebuilds from authority.

`worker-collection` consumes only the `collection` queue with its own concurrency budget. The general worker consumes `enrichment,investigation,indexing`. This isolation keeps scheduled monitoring and catch-up reads from waiting behind projection/enrichment backlog after a long runtime outage.

The runtime image owns its own `/app/.venv`. Root `.dockerignore` excludes the host virtualenv and local caches from the build context, preventing `COPY . .` from replacing container interpreter entry points with host-specific symlinks or shebangs.

Use `make data-plane-status` to inspect dependencies plus runtime processes and `make data-plane-logs` for the three active control/worker logs. `make data-plane-down` stops only runtime processes; `make dev-down` tears down runtime plus dependencies. Host-process `make scheduler`, `make worker`, and `make worker-collection` remain debugger paths. Formal live QA is the one intentional short quiesce: `make qa-live` stops the three writer processes only long enough to freeze one Knowledge head, and its `finally` path always brings them back up after success or failure.

`task_event_dispatcher.py` is the independent Task Event Plane delivery loop. It reads committed `task_event_deliveries` from PostgreSQL and publishes them to `redis_task_bus_url` Redis Streams. It does not reuse Celery broker routing.

`task_event_scheduler.py` is the consumer-side Task Event Plane loop. It reads the Task Bus through a Redis consumer group, reloads each event from PostgreSQL, applies the deterministic Task Runtime dependency relevance gate, and maps durable queued-Role `TaskPatched` events to coarse Celery tasks. Database scheduling commits before broker dispatch; Redis `XACK` happens only after any required Celery send succeeds. Unacknowledged messages are reclaimable after `task_event_claim_idle_ms`; replay may redeliver the coarse task, while the PostgreSQL queued-run claim prevents concurrent Role execution.

## Outbox topic routing

The scheduler currently translates committed topics as follows:

| Topic | Celery task |
|---|---|
| `collection.requested` | `secfusion.collection.run` |
| `knowledge.changed` | `secfusion.projection.knowledge_changed` |
| `incident.changed` | `secfusion.projection.incident_changed` |
| `enrichment.requested` | `secfusion.enrichment.vulnerability` |
| `document.index.requested` | `secfusion.indexing.document_revision` |

Unknown topics fail explicitly instead of being dropped.

## Task composition

`tasks.py` contains thin task entry points and runtime composition helpers:

- collection delegates to `packages.monitoring.runtime.execute_collection_run`;
- knowledge/incident change tasks rebuild current projections;
- vulnerability enrichment creates or resumes a deterministic background Enrichment TaskRun and executes the shared `EnrichmentRole`; provider/graph primitives still use acquisition, EvidenceIngress and Knowledge Writer;
- delegated EnrichmentRole and queued InvestigationRole execute through `QueuedRoleExecutor`; `apps/enrichment_runtime.py` and `apps/investigation_runtime.py` own their production composition;
- document indexing always builds lexical state first, then optionally builds dense embeddings and semantic/normative extraction when model configuration is present.

Task Event scheduling and Role execution remain separate boundaries: Redis delivery only chooses the coarse Role task; the Celery handler constructs the domain runtime and the Task Runtime executor performs the durable claim. The current Investigation production factory is intentionally local-Perception-first. It does not advertise or invoke external/sandbox capabilities until a production Capability catalog/binding/executor is configured, so missing execution-control composition fails as unavailable capability rather than bypassing Policy.

Background vulnerability enrichment no longer constructs executable contracts locally. `_enrich_vulnerability` passes the trigger provenance to `ensure_background_vulnerability_enrichment_run`, which enters the same `TaskIntent → task_admission → TaskContract` path used by other executable work. The workbench API may enqueue this Celery task, but it cannot bypass worker-side admission or the M3 Evidence/Knowledge write path.

Celery uses late acknowledgement, reject-on-worker-loss, prefetch 1, and at-least-once delivery semantics. Task handlers therefore rely on run ids, EvidenceIngress idempotency, Knowledge processing-run identity, and revision-aware projection rebuilds rather than assuming exactly-once broker delivery.

## Redis separation

`redis_broker_url` is reserved for Celery transport. Hot Bug and Incident transient state use `redis_hot_cache_url`. Task Event delivery uses `redis_task_bus_url` with no-eviction/persistent Stream semantics. Worker composition must not collapse these three failure domains into one Redis role.

## Adding background work

A new background behavior should first define its owning package service and durable event contract. Worker code then adds a topic→task mapping and a thin composition entry point. Business semantics should not originate in `apps.worker.tasks`.

## Verification

```bash
uv run pytest apps/worker/tests -q
make integration-core
```
