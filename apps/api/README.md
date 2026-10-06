# `apps.api`

`apps.api` owns the HTTP process boundary only. It bootstraps FastAPI, registers runtime SQLAlchemy models, creates the database session factory, wires route modules, and exposes transport-level request/response behavior. Domain rules remain in capability packages.

## Current API surface

`main.py` creates the application and owns process lifespan. The current stable routes are:

```text
GET /health/live
GET /health/ready
GET /health
GET /api/v1/vulnerabilities/{cve_id}
GET /api/v1/a2a/tasks/{task_id}
POST /api/v1/investigations
GET /api/v1/investigations
GET /api/v1/investigations/{case_id}
```

The vulnerability route calls `packages.intelligence.knowledge.read.get_vulnerability_by_cve` and returns the evidence-rich `KnowledgeObjectView`. HTTP 404 is a transport representation of a missing object; the route does not implement fallback search or enrichment.

`GET /api/v1/a2a/tasks/{task_id}` is the first A2A compatibility transport seam. It maps an existing internal TaskRun/TaskContract/ContextManifest into the A2A 1.0 Task view and returns `application/a2a+json`. `A2A-Version: 1.0` and compatible `1.0.x` requests are accepted. This is intentionally **not** advertised as a complete A2A server yet: SendMessage, SubscribeToTask/SSE, Agent Card discovery, push-registration/authentication and task cancellation remain transport work above the deterministic mapper in `packages.task_runtime.a2a`.


## Product Application boundary

Technical Design 2A separates Product API from A2A transport and domain/runtime owners. Product Investigation routes call `apps.application` use cases/read projections instead of composing domain storage directly. `POST /api/v1/investigations` returns `202 Accepted` plus `Location`, while GET routes return stable `InvestigationView` / cursor-paged `InvestigationPage`. The Application layer reuses the canonical Case/State/Task admission/Budget/Execution owners, while Product DTOs do not expose runtime-internal schema.

`POST /api/v1/questions` also carries Product session identity. Investigation-class follow-up may send only `session_id` after the prior InvestigationRole episode is terminal; the Application layer reuses the same durable Case, opens the next EvidenceNeed and returns `202 Accepted` with the same investigation `Location`. A non-terminal InvestigationRole episode produces a lifecycle conflict instead of creating a concurrent TaskRun or orphan EvidenceNeed. Session-only LOOKUP/RETRIEVE is also a valid Product contract: when the session still owns an active/waiting Investigation and no explicit target is supplied, Application may execute a read-only DecisionRole against that live M4 Case. HTTP only validates/transports the request; Case selection, world-revision guards, citation projection and authority remain below the route.

LOOKUP/RETRIEVE model calls use the same recorded provider wrapper as formal QA and Agent runtime. A logical request has one `ModelRequest`; transient network/408/429/selected-5xx retries become additional `ModelAttempt` rows, while authentication and response-validation failures fail immediately. Route-level `interactive_timeout_seconds` still bounds the HTTP-facing Product operation; retry count/backoff are deployment configuration and are frozen into formal benchmark deployment identity.

`dependencies.py` owns the shared SQLAlchemy session dependency and `RequestContext`. `main.py` creates a request id at the HTTP edge and returns it as `X-Request-ID`; Product Application links that id into the created ExecutionEnvelope trace context. `errors.py` maps Application failures and Product validation errors to RFC 9457-style `ProblemDetail`. Runtime diagnostics that belong in the product are exposed through Product-safe read models.

`GET /api/v1/observatory/system` is the Product-safe system health aggregate. It reports PostgreSQL and the three separated Redis roles, durable outbox / TaskEvent delivery backlog, and Redis Stream pending work. It deliberately reports worker-process health as unavailable until a heartbeat owner exists; model-provider status is configuration state rather than a fabricated live provider probe, while ArtifactStore integrity remains owned by the Data Plane operational snapshot.

`routes/health.py` separates liveness from readiness: liveness only means process alive; readiness verifies the database/schema and required runtime-policy configuration. Aggregate `/health` reports optional model-provider absence as disabled/degraded rather than making the whole API unready.

## Retired Runtime Workbench

The former diagnostic route set and static operator console were retired after the Product App gained Product-safe Data Plane, Evidence, Investigation, Agent runtime and Observatory reads. No domain capability was owned by that transport layer; execution remains in the existing Application/domain services and workers.

## Adding routes

A route may validate HTTP input, translate domain errors into HTTP responses, inject request-scoped dependencies, and select a package service. Reusable query, enrichment, evidence, evaluation, or Agent behavior belongs to its capability owner rather than the route module.

Database transactions that change domain state should be owned by the called application/domain service. The API process should not bypass those services with direct ORM writes.

## Configuration

The application uses `packages.shared.config.Settings`. Database engine/session lifecycle is process-owned here; credentials and provider configuration remain environment-backed settings. For model-backed Product QA, `SECFUSION_MODEL_BASE_URL` and `SECFUSION_MODEL_API_KEY` are the common minimum. `make model-provider-probe` may resolve a unique chat model through OpenAI-compatible `/models`; if several plausible chat models are exposed, set `SECFUSION_MODEL_NAME` explicitly so formal runs do not choose a model nondeterministically.

## Verification

API transport tests live under `apps/api/tests`. `test_product_questions.py` covers Investigation session continuation and verifies that session-only LOOKUP without `cve_id/object_id` is accepted by the transport and reaches the model dependency rather than failing schema validation. Domain behavior remains covered by its owning package tests.
