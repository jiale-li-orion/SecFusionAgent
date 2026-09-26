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

`EvidenceBackedKnowledgeWriter` is the canonical write path for structured/derived knowledge. Important implementation rules:

- root and target objects are upserted by stable canonical identity;
- claims/relations retain source identity and evidence locator;
- same-source replacement supersedes the selected predicate/relation type without deleting history;
- cross-source assertions remain separate so conflict can be represented;
- every successful material change advances the Knowledge revision and emits `KnowledgeChange` through the outbox;
- deterministic/source-asserted writes must conform to the registered vocabulary;
- semantic writes outside canonical shape remain `exploratory` instead of changing the canonical benchmark vocabulary.

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
qualifier.source_semantics = cve_range | osv_range | nvd_cpe | csaf_vex | vendor_assertion
qualifier.version_range / platform / configuration / justification = optional
```

`state` and `source_semantics` are required canonical qualifiers. Query/source miss or an incomparable version remains `unknown`; `not_affected` requires an explicit structured rule/status or VEX-style justification. Conflicting source assertions remain distinct durable assertions even when a current projection chooses one display value.

## Workload-specific state

The subpackages keep lifecycle-specific storage out of the generic Knowledge model:

- `hot_cache/` — evictable Redis Hot Bug working set;
- `normalization/` — Hot Bug and durable canonical source normalization;
- `promotion/` — explicit hot/source state → durable Evidence/Knowledge promotion;
- `structured/` — GitHub `Repo / Issue / PullRequest / Commit / Release` mapping and graph relations;
- `documents/` — managed document identity, revision, parser output, chunks, and InsightCandidate state;
- `retrieval/` — PostgreSQL lexical/dense index build/read contracts for managed chunks;
- `incident/` — Redis signal/candidate correlation plus durable Incident revisions/timeline/source links after promotion; each source stream arrives with one primary role/path, while promotion and later material updates change Incident state rather than mutating the source definition;
- `assets/` — provider-neutral time-bounded `AssetObservation` normalization;
- `projections/` — materialized current views over durable state.

## Incident lifecycle boundary

Incident signal input follows the single-valued `source_role` / `retention_mode` contract from `packages.sources`. An `incident_signal` stream creates short-lived signal/candidate state; promotion fixes supporting evidence into durable `SecurityIncident` state. Later material signals append revision/timeline/source-link/evidence records, while exact duplicate input remains replay. Forensic/authority/primary documents on `durable_managed` enter through Managed Content + EvidenceIngress before Incident enrichment consumes them.

`source_family` and `upstream_source` are retained so republication does not inflate independent corroboration. Incident persistence never upgrades secondary media authority merely because a signal is promoted.

## Managed document lifecycle

A managed document keeps provider/source revision identity separately from parsed/indexed state. Parsers support the media types explicitly registered by the collection runtime. A new parser or media type must be wired in both the parser layer and runtime ownership tests; recognizing a MIME type in a source definition without a parser owner is invalid.

Document indexing produces lexical state first. Dense embedding and semantic extraction are optional runtime continuations when model configuration exists; lack of model credentials does not invalidate the lexical document path.

## Current projections

`projections/CurrentProjectionService` owns rebuildable read models including current vulnerability, affected versions, fix status, repository security state, and incident state. Projection rows carry upstream revision information. They are caches/read models, not evidence authority.

## Artifact storage

`storage/artifacts.py` defines the `ArtifactStore` boundary. The configured S3-compatible implementation uses content-addressed writes and is verified with a real S3-compatible integration test. PostgreSQL stores artifact metadata and URI, not arbitrary large body bytes.

## Dependency boundary

Allowed package dependencies: `shared`, `sources`, `intelligence`.

This module does not own provider scheduling, LLM selection, Agent policy, or evaluation. It must not import `monitoring`, `enrichment`, `investigation`, `evaluation`, or `apps`.

## Verification

```bash
uv run pytest packages/intelligence -q
make integration-core
make integration-object-store
```

For changes to evidence or canonical state, prefer a real PostgreSQL integration case when SQLite cannot enforce the same FK/locking/query behavior.
