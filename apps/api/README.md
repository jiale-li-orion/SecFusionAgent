# `apps.api`

`apps.api` owns the HTTP process boundary only. It bootstraps FastAPI, registers runtime SQLAlchemy models, creates the database session factory, wires route modules, and exposes transport-level request/response behavior. Domain rules remain in capability packages.

## Current API surface

`main.py` creates the application and owns process lifespan. The current stable routes are:

```text
GET /health/live
GET /api/v1/vulnerabilities/{cve_id}
GET /api/v1/a2a/tasks/{task_id}
```

The vulnerability route calls `packages.intelligence.knowledge.read.get_vulnerability_by_cve` and returns the evidence-rich `KnowledgeObjectView`. HTTP 404 is a transport representation of a missing object; the route does not implement fallback search or enrichment.

`GET /api/v1/a2a/tasks/{task_id}` is the first A2A compatibility transport seam. It maps an existing internal TaskRun/TaskContract/ContextManifest into the A2A 1.0 Task view and returns `application/a2a+json`. `A2A-Version: 1.0` and compatible `1.0.x` requests are accepted. This is intentionally **not** advertised as a complete A2A server yet: SendMessage, SubscribeToTask/SSE, Agent Card discovery, push-registration/authentication and task cancellation remain transport work above the deterministic mapper in `packages.task_runtime.a2a`.

## Adding routes

A route may validate HTTP input, translate domain errors into HTTP responses, inject request-scoped dependencies, and select a package service. Reusable query, enrichment, evidence, evaluation, or Agent behavior belongs to its capability owner rather than the route module.

Database transactions that change domain state should be owned by the called application/domain service. The API process should not bypass those services with direct ORM writes.

## Configuration

The application uses `packages.shared.config.Settings`. Database engine/session lifecycle is process-owned here; credentials and provider configuration remain environment-backed settings.

## Verification

API transport tests should live under `tests/e2e` or an `apps/api/tests` directory once an externally meaningful API behavior is added. Domain behavior is covered by its owning package tests.
