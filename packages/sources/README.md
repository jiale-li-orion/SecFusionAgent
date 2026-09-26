# `packages.sources`

`packages.sources` is the implementation owner of external source definitions and provider adapters. Technical Design 1 fixes source authority, the eight-category product taxonomy, processing-path semantics, and the M1→M2 boundary; this module documents the concrete contracts used to implement those decisions.

## Owned contracts

`SourceDefinition` is the runtime source contract. It separates provider identity from processing policy and records `source_id`, `adapter_type`, `source_class`, authority scope, one primary `source_role`, source family/upstream source, access/update/identity/time semantics, authentication/rate-limit metadata, one `retention_mode`, and schedule policy. A source stream that needs another lifecycle is represented by another SourceDefinition or an explicit downstream promotion, not by compound role/retention strings.

`SourceAdapter` is the provider boundary. Adapters expose `discover`, `fetch`, and `query`; they return `DiscoveredRef`, `DiscoveryBatch`, or `IngestEnvelope` and never write canonical Knowledge directly. Provider SDK types and provider-specific errors stay behind this boundary.

`IngestEnvelope` is the handoff into M1/M2. It carries acquisition-run identity, source/object identity, source timestamps, observation time, provider revision when available, media type, payload/body, request metadata, content hash, and idempotency key. JSON payloads are canonicalized before hashing. The idempotency identity is:

```text
source_id + external_object_id + (external_revision | content_hash)
```

The same identity is reused by M1 evaluation through `SourceDeliveryKey`.

## Taxonomy, access mode, and processing path

These are independent dimensions:

- product taxonomy: `vulnerability / development / academic / vendor / independent / normative / assets / incidents`;
- access mode: API, Git, RSS, Web, search, query, etc.;
- processing path: encoded by `RetentionMode`.

`RetentionMode` maps to the concrete M1–M3 runtime path:

| Retention mode | Runtime path |
|---|---|
| `hot_window` | high-frequency vulnerability working set |
| `selective_index` | structured development index |
| `durable_managed` | long-lived managed document / insight corpus |
| `incident_signal` | short-lived incident signal staging |
| `time_bounded` | query-bound observation side path |

One provider may expose multiple source streams. The eight product categories are coverage taxonomy rather than `SourceDefinition.source_class`; they are not required to be a one-to-one partition of provider/source IDs. One executable source stream may support more than one coverage category when it genuinely carries both information roles, while its runtime `source_class`, provenance, authority and processing path remain unchanged. One taxonomy category may use several retention modes. `durable_promoted` is a downstream state after promotion and is not a sixth source retention mode.

A product source category counts as executable coverage only when the inventory has an `owned` fixed/grouped owner whose adapter/runtime owner can be constructed. `partial` ownership, `dynamic_resolution`, and a successful point-in-time live probe do not create a new supported category. Live reachability remains an operational snapshot rather than taxonomy/coverage evidence.

## Registry and adapter extension

Declarative definitions live under `config/sources/*.json`; the product source catalog lives in `config/source-inventory.json`. `registry/loader.py` loads source definitions and `registry/sync.py` synchronizes them into PostgreSQL. `adapters/factory.py` is the only adapter-construction switch used by runtime code.

Adding a fixed provider normally requires all of the following in one change:

1. add/update a declarative `SourceDefinition`;
2. implement or extend the adapter under `adapters/`;
3. register the adapter type in `adapters/factory.py`;
4. add the source to `source-inventory.json` with the correct taxonomy/ownership mode;
5. ensure the selected `RetentionMode` has a downstream owner in `lifecycle_audit.py`;
6. add deterministic adapter/inventory/runtime-ownership tests;
7. update the Website source catalog only when product-facing source coverage changes.

A provider whose availability depends on target/domain resolution uses the resolver path rather than being counted as a new fixed source category.

## Scheduling semantics

`schedule_policy.enabled` answers whether a source participates in periodic scheduling; it is independent from adapter/query capability. A source can remain queryable while disabled for scheduled collection. `time_bounded` asset providers are intentionally on-demand and are expected to have scheduling disabled.

The source module does not own `next_due_at`, backoff, acquisition-run state, or cursor commit. Those belong to `packages.monitoring`.

## Failure and authority semantics

Boundary errors are translated into project source errors such as authentication failure, rate limiting, schema change, and fetch failure. Higher layers consume those stable classifications instead of provider exceptions.

A reachable provider is not automatically authoritative. `source_role`, `authority_scope`, `source_family`, and `upstream_source` remain attached to source definitions so later conflict/corroboration logic can distinguish authority and source independence.

## Dependency boundary

Allowed package dependencies: `shared`, `sources`.

This module must not import `monitoring`, `intelligence`, `enrichment`, `investigation`, `evaluation`, or deployable `apps`. The architecture dependency test enforces this direction.

## Verification

```bash
make source-inventory-check
make verify-data-sources
uv run pytest packages/sources/tests -q
```

`make probe-live-sources` is a manual reachability snapshot. It is not a deterministic source-coverage gate.

Cross-module semantics remain authoritative in [Data Sources and Processing](https://github.com/jiale-li-orion/SecFusionAgent/wiki/01-Data-Sources-and-Processing) and [Technical Design 1](https://github.com/jiale-li-orion/SecFusionAgent/wiki/Technical-Design-1).
