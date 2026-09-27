# `packages.enrichment`

`packages.enrichment` is the implementation owner of M3 processing that creates additional security claims/relations from existing or newly acquired evidence. Technical Design 1 freezes enrichment authority, vocabulary boundaries, and the M3→M4 handoff; this module documents processor composition, provider querying, semantic extraction, and extension rules.

## Vulnerability enrichment runtime

`runtime/` implements the M3 `EnrichmentRole` adapter on the shared Task Runtime. `EnrichmentStateBuilder` materializes the twelve `enrichment-v1` dimensions as `resolved / conflict / unknown / missing`; `EnrichmentDimensionSpec` is an internal vocabulary-derived state specification, not a second M4 requirement protocol. Execution block/failure stays in `EnrichmentAttempt` rather than adding a fifth domain state.

`EnrichmentStatePlanner` selects from the closed operator registry according to missing dimensions and prior attempts. An operator declares dimensions it directly produces separately from dimensions it only enables, preventing a provider range/reference from being misreported as a resolved canonical fact. Background `enrichment.requested` work and delegated child EnrichmentTask use the same `EnrichmentRole`, state builder, operator path, EvidenceIngress and Knowledge Writer.

`VulnerabilityEnrichmentService` remains the provider-query primitive used by the Role and by deterministic tests. It uses `monitoring.AcquisitionService` for fresh reads. Each returned envelope is accepted through `EvidenceIngress` before a processor creates `EnrichmentCandidate` output. Processors do not turn raw HTTP results directly into Knowledge.

## Deterministic enrichment baseline

The non-Agent baseline is a set of predefined operators with fixed input/output semantics. These operators are also the control group for later semantic/Agent enrichment:

| Operator | Input | Deterministic rule | Output |
|---|---|---|---|
| `ExactIdentifierJoin` | CVE/GHSA/OSV/CNVD/CNNVD/DOI/SHA | namespace normalization + exact match | alias / same-object / source record |
| `SchemaProjection` | structured provider record | fixed field / JSONPath mapping | CVSS, CWE, references, time claims |
| `VersionRangeEvaluate` | product/package + version + range | source-specific comparator | affected / not_affected / fixed / unknown |
| `ProductStatusResolve` | vulnerability + product branch | CSAF/VEX status + justification | affected / not_affected / fixed / under_investigation |
| `CPE/PURLMatch` | asset/package identity | CPE configuration or PURL/ecosystem/package identity | product/package/version association |
| `GraphClosure` | issue/PR/commit/release/repo | exact graph edge + ancestry/containment | fix/release/repo relations |
| `TaxonomyMap` | standardized identifier | controlled mapping table | CWE/CAPEC/ATT&CK/taxonomy relation |
| `ExternalExactLookup` | canonical identifier | provider exact query | KEV/EPSS/advisory/package metadata |
| `ObservationJoin` | time-bounded asset observation | fingerprint/CPE/PURL/version + observation time | candidate affected asset |
| `EvidenceBind` | mapped fact/relation | locator resolves to the fixed source revision | `EvidenceRef` |
| `ConflictPreserve` | competing source assertions | authority/revision/independence comparison | parallel assertions + conflict |
| `Deduplicate` | source record/relation | canonical key + source family/upstream source | replay / independent evidence group |

A deterministic miss yields `unknown`; these operators do not infer a negative fact from absence.

### Source-specific applicability rules

The unified applicability relation is produced from source-specific semantics rather than by one generic string comparator:

- **CVE Record Format 5.x** — evaluate `versionType`, explicit versions/ranges, `lessThan`, `lessThanOrEqual`, `changes`, and `defaultStatus`;
- **OSV** — preserve `SEMVER / ECOSYSTEM / GIT` range type and `introduced / fixed / last_affected / limit`; prefer an explicit `fixed` boundary over inferring safety from `last_affected`, because the latter can assume later versions are unaffected; GIT applicability requires repository ancestry, not lexical commit comparison;
- **NVD** — preserve CPE configuration-tree AND/OR semantics plus inclusive/exclusive version bounds; flattening the tree into one version list is invalid;
- **CSAF/VEX** — preserve mutually exclusive product-status groups and the justification/impact semantics needed for `not_affected`;
- **vendor assertion** — remains source-scoped unless its product/version identity can be normalized deterministically.

### Severity and exploitation signals

CVSS, KEV, public PoC, EPSS, and exploit maturity remain separate facts. CVSS Base/Threat/Environmental/Supplemental groups describe different dimensions; Threat includes time-varying exploitation information while Environmental depends on deployment context. CISA KEV establishes observed exploitation in the wild; public PoC availability does not prove known exploitation. EPSS is a daily-updated estimate of exploitation probability over the following 30 days, not deployment impact or a complete risk score. Processors must not collapse these into one generic `risk` value.

## Processor classes

`processors/` contains deterministic provider mappers. Their output must preserve provider-native semantics when no canonical mapping exists. Adding a new field to a mapper does not automatically add it to formal enrichment P/R.

`graph/` owns deterministic repository association and fix-boundary logic. A development reference can be canonical repository graph state while remaining `benchmarked=False`; stronger relations such as `fixed-by` require the graph/evidence conditions implemented by the fix service.

`external_query/` is the generic query-time enrichment path for sources whose result is not part of periodic collection. `assets/` specializes this for provider-neutral `AssetObservation` normalization and explicit promotion.

## Semantic extraction

`semantic/DocumentSemanticService` operates on already persisted document revisions/chunks. The model receives the chunk as data, not instructions, and must return structured claims/relations with an exact verbatim quote. A proposal whose quote cannot be located in the fixed chunk is rejected before Knowledge write.

Semantic source profiles add source-class instructions and authority context. Normative sources are deliberately routed to `normative/NormativeKnowledgeService` instead of the generic semantic extractor.
 `NormativeKnowledgeService` extracts only evidence-backed NormativeDocument facts, Requirement, Control and requirement-control mappings. It preserves explicit applicability conditions from the source but leaves contextual `applicability_status` as `not_evaluated`; it does not decide legal/contractual applicability for the current investigation and never creates `RuntimePolicy`, allow/deny decisions, or enforcement state. Contextual applicability belongs to later M4/M5 reasoning/review, and approved RuntimePolicy compilation belongs to the execution control plane.

Model output does not define the vocabulary. A known term is canonical only when its subject/target shape and required qualifiers also match `enrichment-v1`; shape-mismatched or unregistered semantic output is stored as `exploratory` evidence-backed knowledge.

## AI provider boundary

`providers/` implements the generic `ModelProvider` / embedding contracts using configured OpenAI-compatible endpoints. `packages.enrichment` owns provider composition because model use here is an enrichment implementation detail; model-independent request/response protocols live in `packages.shared`.

No model endpoint is required for the deterministic M1–M3 path. Workers skip dense/semantic continuations when model configuration is absent.

## `enrichment-v1` implementation matrix

The registry is broader than the processors already implemented. The current implementation surface is tracked here rather than expanding Technical Design 1 for every processor:

| Dimension | v1 benchmark surface | Current implementation state |
|---|---|---|
| Identity | M2 diagnostic, not M3 P/R | CVE/GHSA/OSV/CNVD/CNNVD and repository identities largely available |
| Severity | CVSS score/vector/version/severity | NVD deterministic normalization writes all four canonical fields, including `cvss_version` |
| Weakness | `Vulnerability --has-weakness--> Weakness` | NVD and GitHub Advisory deterministically map CWE identifiers to canonical `Weakness` objects with evidence |
| Product/package | `affects-product`, `affects-package` | package relations exist; broader product identity mapping continues |
| Version applicability | scoped `applicability-status` relation | GitHub Advisory vulnerable ranges now write source-scoped `affected` assertions with `source_semantics=github_advisory_range`; unified CVE/OSV/NVD/CSAF evaluator remains backlog |
| Fix/remediation | `fixed-version`, `fixed-by` | GitHub Advisory `first_patched_version` now writes canonical `SoftwareVersion` + `fixed-version`; repository graph/fix-boundary remains available |
| Exploit state | `known_exploited`, `has-poc`, exploit maturity | KEV available; PoC/ExploitArtifact processor remains backlog |
| Exploit likelihood | EPSS probability/percentile at observed time | GitHub Advisory EPSS snapshot writes canonical probability/percentile claims with provider evidence; dedicated point-in-time EPSS source remains future hardening |
| Advisory/reference | canonical advisory/document associations | GitHub Advisory now writes canonical `Document` + `described-by`; vendor/advisory breadth remains incomplete |
| Asset exposure | `InternetAsset --asset-potentially-affected--> Vulnerability` | provider-neutral `AssetObservation` exists; applicability join remains backlog |
| Research/paper | `discusses-vulnerability` | managed semantic extraction exists; benchmark bridge remains backlog |
| Incident context | strong-anchor Incident↔Vulnerability bridge | Incident lifecycle exists; canonical benchmark bridge remains backlog |

Supporting edges such as `release-contains-commit`, `asset-runs-product`, and `asset-version`, and open-text `workaround / mitigation / attack_condition`, can remain canonical evidence-backed knowledge while `benchmarked=False`. `poc_available` is a derived convenience projection; formal PoC gold uses `Vulnerability --has-poc--> ExploitArtifact`.

The active M3 implementation backlog is therefore:

1. Product/Package/SoftwareVersion alias normalization beyond the current ecosystem+package+version identity;
2. CVE/OSV/NVD/CSAF source-specific applicability evaluators beyond the current GitHub Advisory range assertion;
3. PoC/ExploitArtifact processor;
4. dedicated point-in-time EPSS ingestion independent of GitHub advisory snapshots;
5. advisory/document association coverage beyond GitHub Advisory;
6. AssetObservation → Product/SoftwareVersion → Vulnerability deterministic join;
7. paper `discusses-vulnerability` benchmark bridge;
8. Incident → Vulnerability strong-anchor benchmark bridge.

Processor-version refresh is expected to be replay-safe. The canonical writer and NVD durable normalizer reactivate an identical immutable claim/relation when a newer processor run supersedes the previous active source projection and then reproduces the same normalized tuple. This prevents mapper upgrades from accidentally making stable facts disappear.

The deterministic structured path is continuously checked against live provider gold rather than
fixtures alone. The 2026-09-27 recent 12-CVE stratum exercises 150 formal facts across severity,
weakness, package, qualifier-aware applicability, fixed-version, EPSS likelihood, and advisory
association with `150 TP / 0 FP / 0 FN`. This result is scoped to the selected structured stratum;
new source semantics are added to the formal denominator only after their canonical mapping is
implemented and evidence-bound.

M3 exposes closed-set status as resolved/conflict/unknown/missing over the shared vocabulary. The conversion of those gaps into M4 `EvidenceNeed`, Perception and investigation policy remains owned by `packages.investigation`; M3 state specifications do not become a parallel investigation requirement protocol.

## Current boundary

The EnrichmentRole runtime, closed operator registry, deterministic fixed-point loop, background/delegated TaskRun reuse, EvidenceIngress and Knowledge write path are implemented. Delegated and background EnrichmentTask creation now passes through the shared Task admission seam and is dispatched through the same Task Event → worker Role path as InvestigationRole; the worker composition lives in `apps/enrichment_runtime.py` rather than inside the Task Runtime. M7 replay/promotion infrastructure now exists, so the remaining M3 gaps are the concrete content/coverage items in the matrix above and the absence of validated enrichment Skill patches—not another scheduler or task protocol.

## Design → implementation map

TD1 定义 M3 只生产 evidence-backed field/relation；TD2 允许这类工作作为 Role 执行，但没有搬走 authority。`runtime/admission.py` 把已绑定的 vulnerability/object 与 required dimensions 编译为 Enrichment TaskContract；`runtime/role.py` 跑 deterministic-first fixed-point loop；`runtime/operators.py` 选择 closed operators；provider/graph/fix primitive 在需要新材料时重新进入 M1 acquisition，最终仍通过 EvidenceIngress 和 `EvidenceBackedKnowledgeWriter` 写回。Task-local `EnrichmentState` 只表示工作进度，不替代 canonical Knowledge，也不替代 M4 EvidenceNeed。

## Adding an enrichment processor

A new deterministic processor normally requires:

1. a concrete information need backed by an existing source/evidence path;
2. a mapper/service with fixed input and evidence locators;
3. source-specific output or an already registered canonical vocabulary term;
4. Knowledge Writer usage rather than direct table writes;
5. regression tests for replay, replacement/conflict, evidence binding, and wrong-entity/version cases when applicable;
6. vocabulary/evaluation changes only if the processor changes the formal M3 benchmark surface.

If a new semantic relation is useful but not yet stable enough for the closed benchmark, keep it exploratory/non-benchmarked rather than expanding Technical Design for every experiment.

## Dependency boundary

Allowed package dependencies: `shared`, `sources`, `intelligence`, `monitoring`, `task_runtime`, `enrichment`.

This module may use the shared Task Runtime to host `EnrichmentRole`, but it must not import M4 investigation state/runtime policy or M7 evaluation implementation into M3 processing decisions.

## Verification

```bash
uv run pytest packages/enrichment -q
make integration-core
```
## Standards used by deterministic processors

- CVE Record Format 5.x: https://cveproject.github.io/cve-schema/schema/docs/
- OSV Schema: https://ossf.github.io/osv-schema/
- NVD Product / CPE Match APIs: https://nvd.nist.gov/developers/products
- CSAF / VEX 2.1: https://docs.oasis-open.org/csaf/csaf/v2.1/
- CVSS v4.0: https://www.first.org/cvss/v4.0/specification-document
- CISA KEV: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- FIRST EPSS: https://www.first.org/epss/
- STIX 2.1: https://docs.oasis-open.org/cti/stix/v2.1/
- OpenCTI connector/enrichment model: https://docs.opencti.io/latest/deployment/connectors/
- MISP modules: https://misp.github.io/misp-modules/
