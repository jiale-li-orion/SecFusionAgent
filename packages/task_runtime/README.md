# `packages.task_runtime`

`packages.task_runtime` owns the shared execution protocol used by Agent workloads. Technical Design 2 fixes Task/Role/Context/Event semantics; this package implements those contracts, durable TaskRun state, reference-preserving context handling, and Task Event delivery. Domain facts remain in their owner packages.

## Public contracts

`contracts/` exposes `TaskIntent`, immutable versioned `TaskContract`, `TaskRun`, `RoleProfile`, `ContextManifest`, `ExecutionEnvelope`, TaskEvent types, delegation/effect ceilings, and conformance helpers. A TaskRun references fixed contract/context revisions; terminal TaskRun states never return to running.

`context/` owns ContextManifest derivation and compatibility operations. `inherit / filter / pin / refresh / diff / fork / merge` preserve references and revisions. Child/peer results carry `based_on_context_revision`; compatibility checks distinguish valid, rebase-required, stale, and conflict outcomes. Summaries are presentation/model material and do not replace evidence/state/artifact references.

`ContextMaterializer` converts a pinned manifest plus explicitly selected disclosure/dynamic/ephemeral fragments into a `PromptAssembly`. Every materialized fragment preserves source reference/revision, trust class, cache class and content hash. Prompt assembly identity includes context revision, platform/execution/policy/state revisions, percept refs and ordered fragment IDs; changing any model-visible selection reason or percept therefore changes replay identity. Untrusted external/evidence/state fragments are emitted as model data rather than system instructions.

`cache_hint` and generated stable-prefix hints affect performance only. They do not participate in fact freshness, Context revision or permission decisions.

## Durable runtime state

`storage/` persists:

- immutable TaskContract revisions;
- immutable ContextManifest revisions;
- TaskRun lifecycle/current pointers;
- append-only TaskEvent rows with task-local monotonic `seq`;
- TaskEvent delivery state.

TaskEvent append acquires the TaskRun row before allocating sequence/idempotency state. Replayed event keys return the existing event. Context updates require monotonic revision advance or an explicit fork from the current context.

## Event plane

`events/redis_stream.py` publishes committed TaskEvents to the dedicated Task Bus Redis. PostgreSQL is the durable authority; Redis Streams is delivery. Publish success followed by database acknowledgement failure can produce duplicate stream delivery with the same stable `event_id` and `idempotency_key`; consumers must deduplicate.

Task Event delivery is independent from Celery broker and Hot Cache Redis. Healthy-path dispatch preserves task-local sequence order, while consumers must still tolerate retry gaps and duplicate delivery.

`scheduler/` owns generic TaskRun dependency wake semantics. A waiting parent records a structured `task_dependency:<child_run_id>` stop reason; relevant child `EnrichmentStateChanged` or terminal TaskEvents can move that parent from `waiting_dependency` to `queued`. Wake identity is derived from the durable source `event_id` and checked before status mutation, so an old Redis delivery replay cannot accidentally wake a later wait cycle. Domain-specific Case/WATCH relevance remains outside Task Runtime.

The Redis consumer uses a consumer group with `XAUTOCLAIM` before reading fresh entries. Database scheduling commits before `XACK`; consumer loss therefore replays an event, while PostgreSQL wake idempotency prevents duplicate state transitions.

The scheduler deliberately owns only lifecycle/relevance transitions. It does not instantiate domain Roles or model/tool providers. A queued TaskRun is an executable intent; the worker-side Role executor is a separate composition boundary.

## Delegation and execution envelopes

Child Task creation validates parent TaskRun state, allowed task kinds, effect ceiling, and delegation depth before child state is persisted. `ExecutionEnvelope` adds capability scope, identity scope, absolute deadline, budget/policy/network/sandbox references. Child envelopes cannot extend parent deadline, capability scope, or identity scope.

`task_runtime` validates ceilings; invocation authorization, budget accounting, credential use, network policy, and sandbox execution belong to `packages.runtime`.

## Current boundary

The durable protocol, context revisioning, Task Event plane, delegation ceilings, dependency wake and replay semantics are implemented. The remaining TD2 runtime-level gap is not another Task schema: it is the production executor that claims queued Role runs and dispatches them to the correct bounded Role composition. A2A mapping remains Slice 9 work rather than part of this scheduler.

## Dependency boundary

Allowed package dependencies: `shared`, `task_runtime`. Domain packages may depend on Task Runtime to run their Role workloads. Task Runtime does not import vulnerability, Incident, enrichment, or investigation domain state.

## Verification

```bash
uv run pytest packages/task_runtime -q
uv run pytest tests/test_task_capability_policy_conformance.py -q
make integration-core
```
