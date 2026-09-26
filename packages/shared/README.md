# `packages.shared`

`packages.shared` owns infrastructure contracts that are independent of security-intelligence domain semantics and are reused by multiple capability packages. Domain-specific parsing, source logic, enrichment rules, and Agent policy do not belong here.

## Configuration

`config.Settings` is the repository-wide environment contract. All keys use the `SECFUSION_` prefix. Current settings cover:

- PostgreSQL;
- Celery broker Redis and separate Hot Cache Redis;
- collection/incident TTL and scheduler timing;
- S3-compatible evidence storage;
- provider credentials;
- OpenAI-compatible model/embedding endpoint configuration.

Adding a deployment-varying value requires a typed setting. Security or protocol invariants that should not vary by deployment stay in their owner module instead of becoming environment variables.

## Database foundation

`db.py` owns the common SQLAlchemy declarative base, async engine creation, async session factory, and generic transaction scope. Domain ORM models remain in their owning packages and are registered by `apps.runtime_models` at process startup.

## Transactional outbox

`storage.OutboxEventModel` and `outbox.dispatch_pending_events` implement the shared database→broker handoff. Events are selected with row locks/`SKIP LOCKED`; broker publication and database acknowledgement are not an exactly-once transaction.

A broker success followed by database failure can redeliver an event. Consumers must therefore be idempotent using their domain event/run/revision identity. Shared outbox code deliberately does not contain topic-specific business routing; that belongs to `apps.worker`.

## Model provider protocol

`model_provider.ModelProvider` defines model-independent structured generation. `StructuredModelRequest` separates system instruction, data, and metadata. Concrete OpenAI-compatible configuration/HTTP behavior currently lives in `packages.enrichment.providers` because M1–M3 model use is an enrichment concern.

Future M4 runtime may add additional provider contracts only after its Task/Tool/Policy design is frozen; those contracts should not be guessed into this module early.

## Dependency boundary

`shared` is the bottom package layer and may depend only on `shared` itself plus third-party libraries. It must not import security-domain packages.

## Verification

Shared behavior is exercised by architecture tests and real infrastructure integration:

```bash
uv run pytest tests/test_architecture_dependencies.py tests/test_runtime_model_registry.py -q
make integration-core
```
