# `packages.intelligence`

`packages.intelligence` is the implementation owner of the evidence-backed information state used by M2 and M3. Technical Design 1 defines the Evidence/Knowledge/Incident/Insight separation and authority rules; this module records the concrete persistence models, write/read contracts, rebuildable projections, and submodule responsibilities.

## Evidence ingress

`ingestion/EvidenceIngress` is the durable evidence boundary for externally acquired content. It validates source ownership, deduplicates exact replay by idempotency key/content hash, persists raw bytes through `ArtifactStore`, then writes `Observation` and `EvidenceArtifact` records.

If a provider reuses `external_revision` while returning different content, the collision is preserved with a derived collision idempotency key. The second body is not silently treated as replay.

Raw evidence is immutable after acceptance. Parsed projections, chunks, embeddings, semantic output, current views, and hot caches are derived/rebuildable state.

## Identity and evidence correctness

Automatic cross-source identity merge is restricted to strong identifiers or reproducible deterministic cross-reference. Current strong identifiers include CVE/GHSA/OSV/CNVD/CNNVD identifiers, DOI/arXiv identifiers, GitHub repository full name, package PURL or ecosystem+name, and commit SHA. Different namespaces are merged only when a source explicitly cross-references them or a deterministic mapping proves identity. Name/title similarity and embedding proximity can create candidates, but they do not merge durable objects.

Every accepted claim/relation must resolve to an Observation/Artifact and locator. Structured mappings must point to the field or source fragment that supports the value/relation. Managed semantic extraction additionally requires the quoted text to be a literal substring of the fixed document chunk. A value can therefore be correct while its evidence binding is still invalid; evaluation treats those cases separately.

## Canonical Knowledge

`knowledge/` owns generic evidence-backed objects, identifiers, claims, relations, revisions, and reads.

The long-lived local data plane now treats this store as an accumulating operational corpus. `make data-plane-up` keeps scheduled acquisition plus enrichment/indexing consumers alive across terminal exit and Docker restart. PostgreSQL remains volume-backed; raw Evidence and runtime artifacts default to a content-addressed filesystem store mounted from the host at `.local/secfusion-artifacts`, so rebuilding an app container does not recreate the evidence namespace. Redis hot state remains rebuildable and is intentionally excluded from fact authority. Formal QA is the only workflow that temporarily quiesces data-plane writers so a live Product run can bind to one immutable current Knowledge head; the batch runner restores the writers in `finally`.

`EvidenceBackedKnowledgeWriter` is the canonical write path for structured/derived knowledge. Important implementation rules:

- root and target objects are upserted by stable canonical identity;
- claims/relations retain source identity and evidence locator;
- same-source replacement supersedes the selected predicate/relation type without deleting history;
- cross-source assertions remain separate so conflict can be represented;
- every successful material change advances the Knowledge revision and emits `KnowledgeChange` through the outbox;
- deterministic/source-asserted writes must conform to the registered vocabulary;
- semantic writes outside canonical shape remain `exploratory` instead of changing the canonical benchmark vocabulary.
- processor-version replay of an unchanged normalized tuple reactivates the existing immutable claim/relation after source-scoped supersession, so deterministic reprocessing cannot silently erase stable current facts.

Current deterministic structured coverage includes NVD CVSS score/severity/vector/version, NVD/GitHub CWE → canonical `Weakness` relations, NVD references explicitly tagged `Exploit` → canonical `ExploitArtifact / has-poc`, NVD references explicitly tagged `Vendor Advisory` → URL-addressed canonical `Document / vendor-advisory`, NVD CPE configuration trees → qualifier-rich `nvd_cpe` applicability relations without flattening boolean topology, CVE Record Format 5.x scoped version/default-status applicability, Red Hat CSAF/VEX product-status assertions → canonical `affected / not_affected / fixed / under_investigation` with exact product scope and justification, Red Hat VEX documents → canonical URL-addressed `Document / vendor-advisory`, GitHub package and first-patched `SoftwareVersion` relations, GitHub vulnerable-range applicability and advisory `Document`/`described-by`, GitHub EPSS snapshots, dedicated FIRST EPSS point-in-time probability/percentile with `score_date`, OSV package + `osv_range` applicability + ecosystem/semver fixed-version mappings, CISA KEV state, Shodan InternetDB explicit host-level `vulns[]` → `InternetAsset --asset-potentially-affected--> Vulnerability`, Shodan service-level CPE observations → `asset-runs-product` / `asset-version` plus full-configuration NVD applicability joins, and frozen managed research chunks with exact CVE identifiers → `ResearchWork --discusses-vulnerability--> Vulnerability`. OSV CVE-conversion and GHSA-native observations remain separate Evidence records while their explicit strong aliases converge on the same vulnerability. InternetDB records with no explicit vulnerability association remain time-bounded context only; derived asset affectedness is fail-closed unless the target CPE version and the complete NVD configuration tree (including companion conditions) match. Positive derived asset relations retain Evidence from both the asset and NVD observations. Exact paper-CVE relations use chunk/page/character Evidence locators and remain separate from semantic research extraction. Source-native fields remain alongside canonical projections when their broader semantics are not yet unified.

`knowledge/vocabulary.py` owns the executable `enrichment-v1` registry used by both writes and M7 scoring. It records term dimension, benchmark status, subject/target shape, required qualifier keys, canonical object types, source-specific field rules, and applicability states.

The registry separates three scopes:

- `canonical` — versioned terms with stable object/qualifier semantics; only terms also marked `benchmarked=True` may enter formal enrichment P/R;
- `source_specific` — provider-native fields retained without pretending they are canonical benchmark facts;
- `exploratory` — evidence-backed semantic discoveries that are intentionally outside the current closed set.

`enrichment-v1` freezes twelve dimensions: identity, severity, weakness, product/package, version applicability, fix/remediation, exploit state, exploit likelihood, advisory/reference, asset exposure, research/paper, and incident context. Identity primarily supports M2 normalization diagnostics rather than formal M3 P/R. Internal repository graph edges, inference-support edges, and open semantic relations may remain canonical while `benchmarked=False`. A vocabulary-semantic change requires a new `VOCABULARY_REVISION`; adding an unregistered deterministic/source-asserted term is not a local mapper edit.

Version applicability is represented as a scoped relation rather than a boolean on the vulnerability object:

```text
Vulnerability --applicability-status--> Product | Package | SoftwareVersion
qualifier.state = affected | not_affected | fixed | under_investigation | unknown
qualifier.source_semantics = cve5_version_rule | cve5_default_status | osv_range | nvd_cpe | csaf_vex | vendor_assertion
qualifier.scope / version_range / platform / configuration / justification = optional
```

`state` and `source_semantics` are required canonical qualifiers. Query/source miss or an incomparable version remains `unknown`; `not_affected` requires an explicit structured rule/status or VEX-style justification. Conflicting source assertions remain distinct durable assertions even when a current projection chooses one display value.

CVE Record Format 5.x keeps its native rule scopes instead of turning `affected[]` into one global
status. `versions[]` rules and `defaultStatus` are separate applicability assertions; original CVE
status text and product context remain in qualifiers, while `unaffected` is normalized to canonical
`not_affected`. Enrichment state conflict detection groups applicability by target plus normalized
scope, so `1.0 affected` and `2.0 not_affected` are compatible scoped facts; two incompatible states
for the same target and same scope remain a conflict.

CSAF/VEX uses the same scope discipline without discarding VEX semantics. The canonical target is
stable over publisher namespace + CSAF product ID; `qualifier.scope` keeps the original product-status
product ID, `product_context` keeps component/platform relationship snapshots and PURL/CPE helpers,
and `justification` keeps VEX flags such as `vulnerable_code_not_present`. Conflict grouping ignores
status-label/justification metadata while retaining the actual product scope, so two explanations of
the same state do not become artificial scopes and incompatible states for one scope still surface as
conflict.

## Workload-specific state

The subpackages keep lifecycle-specific storage out of the generic Knowledge model:

- `hot_cache/` — evictable Redis Hot Bug working set;
- `normalization/` — Hot Bug and durable canonical source normalization;
- `promotion/` — explicit hot/source state → durable Evidence/Knowledge promotion;
- `structured/` — GitHub `Repo / Issue / PullRequest / Commit / Release` mapping and graph relations;
- `documents/` — managed document identity, revision, parser output, chunks, and InsightCandidate state;
- `retrieval/` — PostgreSQL lexical/dense index build/read contracts plus reference-preserving Knowledge/Evidence context reads used by M4 Perception; `by_chunk_refs` can deterministically re-read an already-selected ordered chunk set at exact DocumentRevision identity, while runtime reuse policy/provenance stays outside the information plane; retrieval returns candidates/refs and never grants factual authority by itself;
- `incident/` — Redis signal/candidate correlation plus durable Incident revisions/timeline/source links after promotion; each source stream arrives with one primary role/path, while promotion and later material updates change Incident state rather than mutating the source definition;
- `assets/` — provider-neutral time-bounded `AssetObservation` normalization;
- `projections/` — materialized current views over durable state.

## Incident lifecycle boundary

Incident signal input follows the single-valued `source_role` / `retention_mode` contract from `packages.sources`. An `incident_signal` stream creates short-lived signal/candidate state; promotion fixes supporting evidence into durable `SecurityIncident` state. Later material signals append revision/timeline/source-link/evidence records, while exact duplicate input remains replay. Forensic/authority/primary documents on `durable_managed` enter through Managed Content + EvidenceIngress before Incident enrichment consumes them.

`source_family` and `upstream_source` are retained so republication does not inflate independent corroboration. Incident persistence never upgrades secondary media authority merely because a signal is promoted.

## Managed document lifecycle

A managed document keeps provider/source revision identity separately from parsed/indexed state. Parsers support the media types explicitly registered by the collection runtime. A new parser or media type must be wired in both the parser layer and runtime ownership tests; recognizing a MIME type in a source definition without a parser owner is invalid.

Document indexing produces lexical state first. Dense embedding and semantic extraction are optional runtime continuations when model configuration exists; lack of model credentials does not invalidate the lexical document path.

`retrieval/context.py`, `operators.py`, and `validation.py` form the current M3→M4 read seam. They resolve current Knowledge/Evidence references and validate world revision/freshness for Investigation context. They intentionally remain below Investigation policy: deciding which evidence need to pursue, whether to perform external observation, and how to integrate a Percept belongs to `packages.investigation`.

## Current projections

`projections/CurrentProjectionService` owns rebuildable read models including current vulnerability, affected versions, fix status, repository security state, and incident state. Projection rows carry upstream revision information. PostgreSQL serializes writes for the same deterministic projection identity with a transaction-scoped advisory lock, then performs the monotonic atomic upsert and advances only when the incoming `upstream_revision` is newer. This preserves both the deterministic primary key and the `(projection_type, subject_id)` database uniqueness invariant without allowing concurrent redelivery to deadlock, race through read-then-insert, or regress a current projection; unrelated projection identities remain independently writable. SQLite keeps the simpler deterministic path for fast tests. Projections remain caches/read models, not evidence authority.

## Design → implementation map

TD1 的 M2/M3 information plane 在实现里保持四层分离：`Observation/EvidenceArtifact` 记录“外部实际观察到了什么”；canonical object/claim/relation 记录经 gate 接受的结构化 Knowledge；document/incident/asset 等 workload-specific state 保留各自生命周期；current projection 只负责加速读取。下游 M4/M6 使用的 `evidence:<link_id>` 由 `EvidenceAttachmentService` 绑定到 Observation/Artifact/locator，前端和 Agent 都不能靠一段自然语言把结果升级成事实。

HTTP vulnerability read、Product Intelligence 与 M4 Perception 都复用 `knowledge.read` / retrieval seam，而不是各自直查表。这保证用户看到的 current view 与 Agent 看到的 accepted/superseded/evidence 语义一致。当前唯一刻意未补齐的是 historical Knowledge read：M7 replay 在 pinned revision 不可精确读取时 fail closed，直到 M1–M3 提供 versioned historical reader。

当前 Knowledge read 会批量装载关系目标、外部标识符、证据链接和 Observation。单个 CVE 的查询次数不会随着 claim/relation 数量线性增长；大对象的问答上下文仍保留完整的证据引用与原有排序语义。

## Artifact storage

`storage/artifacts.py` defines the `ArtifactStore` boundary. The default single-host deployment uses `FilesystemArtifactStore`; an explicit S3-compatible implementation remains available for integration/deployment environments. Both are content-addressed by SHA-256, while PostgreSQL stores artifact metadata and URI rather than arbitrary large body bytes. Filesystem writes use a temporary sibling followed by atomic replace and validate the declared content hash; URI resolution is confined to the configured bucket root. `EvidenceIngress` exact replay verifies that the referenced blob still exists and may restore exact content when the same durable backend can recover the bytes. A replay never accepts mismatched content or upgrades missing historical bytes into fabricated evidence.

The public continuous-monitoring epoch is intentionally later than the bootstrap corpus. A LocalStack lifecycle audit found that pre-epoch PostgreSQL artifact metadata outlived its temporary object namespace; those rows remain an internal bootstrap diagnostic and are excluded from public runtime-integrity claims. Since the durable filesystem cutover, `data-plane-metrics` measures distinct referenced EvidenceArtifact URIs against physical objects and reports public-epoch integrity directly.

## Dependency boundary

Allowed package dependencies: `shared`, `sources`, `intelligence`.

This module does not own provider scheduling, LLM selection, Agent policy, or evaluation. It must not import `monitoring`, `enrichment`, `investigation`, `evaluation`, or `apps`.

## Verification

```bash
uv run pytest packages/intelligence -q
make integration-core
make integration-object-store
make data-plane-status
```

For changes to evidence or canonical state, prefer a real PostgreSQL integration case when SQLite cannot enforce the same FK/locking/query behavior.
