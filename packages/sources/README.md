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

OSV exact CVE lookup has one additional identity-preserving rule. Some OSV `CVE-*` conversion records contain only GIT ranges and omit package identity, while a strong `GHSA-*` alias for the same vulnerability carries the ecosystem-native package/range record. When a CVE lookup has no package-bearing `affected[]`, `OSVAdapter` follows strong GHSA aliases and returns both envelopes. The conversion and native records remain separate Evidence observations; downstream identity merge is justified by the explicit CVE↔GHSA alias, not by text similarity. This preserves commit-level evidence while recovering package/version applicability without inventing package identity.

CVE Program / cvelistV5 exact records are also retained as raw Evidence before applicability is
projected. The CVE5 path preserves `affected[]`, per-version status/range rules and `defaultStatus`;
formal replay can therefore rebuild gold directly from the persisted provider bytes without calling
the production normalizer. CPE-bearing CVE5 products use the same canonical CPE product identity as
NVD, while non-CPE package/vendor-product entries use source-scoped stable identities rather than
guessing an ecosystem.

FIRST EPSS is modeled as its own fixed on-demand source (`first-epss`) rather than as a field owned by GitHub Advisory. The adapter preserves the provider score date as `external_revision` / `updated_at`, and the M3 mapper carries `source_semantics=first_epss` plus `score_date` into canonical EPSS claims. This lets evaluation and replay distinguish daily point-in-time scores instead of treating EPSS as an unversioned mutable scalar. CLI refresh paths synchronize version-controlled source definitions into PostgreSQL before creating AcquisitionRuns, so newly added providers cannot fail the source foreign-key boundary merely because the registry has not been manually seeded yet.

Red Hat CSAF/VEX is an owned public exact-CVE source (`redhat-csaf-vex`) backed by Red Hat Security
Data's static CSAF/VEX tree. The adapter addresses a document by CVE year/id, validates that the
requested CVE is present in `vulnerabilities[]`, and binds `external_revision` / `updated_at` to
`document.tracking.current_release_date`. Raw CSAF JSON is retained as Evidence before M3 projection.
The deterministic mapper preserves `product_status` membership, exact CSAF product IDs,
component/platform relationships, PURL/CPE helpers and VEX flags. The adapter's canonical document
URL is also retained as the stable identity for a vendor-native `Document / vendor-advisory`
relation when the frozen VEX payload explicitly contains the requested CVE; no domain-name heuristic
is used. Source miss remains an empty exact query result rather than an inferred applicability state.

Shodan InternetDB remains a passive, time-bounded asset source. Its `vulns[]` field is treated as an
explicit provider **host-level** vulnerability association, not as proof that any particular port is
vulnerable. M3 may therefore materialize a canonical host-level `InternetAsset` relation when
`vulns[]` explicitly names a CVE, with the relation bound to the exact InternetDB Observation.
Records with empty `vulns[]`, or with only CPE/product context, remain context-only and do not become
`asset-potentially-affected` by inference.

## Design → implementation map

TD1 的“来源能力 ≠ 调度状态 ≠ 产品 coverage”在实现里分别落到三个位置：`SourceDefinition/SourceAdapter` 描述 provider 能做什么；`packages.monitoring` 决定何时做并保存 cursor/backoff；`config/source-inventory.json` 冻结八类产品 coverage denominator。`registry/sync.py` 只把 declarative source definition 同步进 PostgreSQL，不把一次 live probe 或一个 runtime failure 改写成产品 taxonomy。

固定 source 的 runtime construction 统一经 `adapters/factory.py`；target-dependent provider 走 resolver/query path。这样 TD1 的 acquisition/authority contract 可以新增 provider 而不要求 M2/M3/M5 认识 SDK-specific 类型。

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
