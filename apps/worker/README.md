# `apps.worker`

`apps.worker` owns background-process bootstrap and event-to-task wiring for M1–M3. It does not own collection, enrichment, indexing, or projection semantics; those remain in the capability packages called by worker tasks.

## Processes

`celery_app.py` configures the Celery application using the dedicated broker Redis and defines queue routing. Current queue families are collection, normalization, enrichment, and indexing/projection.

`scheduler.py` is a lightweight control loop. Each tick:

1. recovers stale acquisition runs;
2. schedules due sources and writes outbox events;
3. dispatches committed outbox events to Celery;
4. sleeps for `scheduler_tick_seconds`.

The scheduler never performs provider collection inline.

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
- vulnerability enrichment composes acquisition, evidence ingress, deterministic processors, GitHub reference graph, and fix-boundary services;
- document indexing always builds lexical state first, then optionally builds dense embeddings and semantic/normative extraction when model configuration is present.

Celery uses late acknowledgement, reject-on-worker-loss, prefetch 1, and at-least-once delivery semantics. Task handlers therefore rely on run ids, EvidenceIngress idempotency, Knowledge processing-run identity, and revision-aware projection rebuilds rather than assuming exactly-once broker delivery.

## Redis separation

`redis_broker_url` is reserved for Celery transport. Hot Bug and Incident transient state use `redis_hot_cache_url`; worker composition must not collapse those failure domains into one Redis role.

## Adding background work

A new background behavior should first define its owning package service and durable event contract. Worker code then adds a topic→task mapping and a thin composition entry point. Business semantics should not originate in `apps.worker.tasks`.

## Verification

```bash
uv run pytest apps/worker/tests -q
make integration-core
```
