# `apps.worker`

`apps.worker` owns background-process bootstrap and event-to-task wiring across the current TD1 data plane and TD2 Task Event control plane. It does not own collection, enrichment, investigation, indexing, projection, policy, or scheduling semantics; those remain in their domain/runtime packages and are composed here only at process boundaries.

## Processes

`celery_app.py` configures the Celery application using the dedicated broker Redis and defines queue routing. Current queue families are collection, normalization, enrichment, and indexing/projection.

`scheduler.py` is a lightweight control loop. Each tick:

1. recovers stale acquisition runs;
2. schedules due sources and writes outbox events;
3. dispatches committed outbox events to Celery;
4. sleeps for `scheduler_tick_seconds`.

The scheduler never performs provider collection inline.

`task_event_dispatcher.py` is the independent Task Event Plane delivery loop. It reads committed `task_event_deliveries` from PostgreSQL and publishes them to `redis_task_bus_url` Redis Streams. It does not reuse Celery broker routing.

`task_event_scheduler.py` is the consumer-side Task Event Plane loop. It reads the Task Bus through a Redis consumer group, reloads each event from PostgreSQL, applies the deterministic Task Runtime dependency relevance gate, commits any parent `waiting_dependency → queued` transition, then acknowledges the Redis message. Unacknowledged messages are reclaimable after `task_event_claim_idle_ms`; replay is safe because the source `event_id` is part of the durable wake idempotency key.

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
- document indexing always builds lexical state first, then optionally builds dense embeddings and semantic/normative extraction when model configuration is present.

Task Event scheduling intentionally stops at `TaskRun.status = queued`. The worker/runtime composition that executes a queued `InvestigationRole` remains separate from transport and relevance logic, so Redis delivery cannot itself invoke an LLM or bypass Capability/Policy controls.

The current explicit gap is a unified queued-Role executor. `EnrichmentRole` already has a production background composition in `tasks.py`; `InvestigationRole` does not yet have an equivalent production factory that assembles model provider, Context/Skill/Capability view, Perception, Policy/Budget/Execution, delegation and optional Sandbox backends. Until that owner exists, Task Event scheduling may queue an Investigation TaskRun but must not invent a second ad-hoc composition inside the Redis consumer.

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
