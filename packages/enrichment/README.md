# `packages.enrichment`

`packages.enrichment` is the implementation owner of M3 processing that creates additional security claims/relations from existing or newly acquired evidence. Technical Design 1 freezes enrichment authority, vocabulary boundaries, and the M3→M4 handoff; this module documents processor composition, provider querying, semantic extraction, and extension rules.

## Vulnerability enrichment runtime

`runtime/` implements the M3 `EnrichmentRole` adapter on the shared Task Runtime. `EnrichmentStateBuilder` materializes the twelve `enrichment-v1` dimensions as `resolved / conflict / unknown / missing`; `EnrichmentDimensionSpec` is an internal vocabulary-derived state specification, not a second M4 requirement protocol. Execution block/failure stays in `EnrichmentAttempt` rather than adding a fifth domain state.

`EnrichmentStatePlanner` selects from the closed operator registry according to missing dimensions and prior attempts. An operator declares dimensions it directly produces separately from dimensions it only enables, preventing a provider range/reference from being misreported as a resolved canonical fact. Deterministic graph-completion operators may additionally be marked supplemental: `graph.github_references` and `graph.osv_fix_boundary` can still run after `FIX_REMEDIATION` is already resolved when an exact graph prerequisite is present but the corresponding development/fix edge is missing. Supplemental execution never reclassifies the dimension as missing and does not enter the formal M3 denominator. Background `enrichment.requested` work and delegated child EnrichmentTask use the same `EnrichmentRole`, state builder, operator path, EvidenceIngress and Knowledge Writer.

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

`graph/` owns deterministic repository association and fix-boundary logic. `GitHubReferenceGraphService` is local-first: an exact GitHub reference first resolves existing canonical Issue/PR/Commit/Release identity and only falls back to provider acquisition on a miss, so previously indexed development objects are not refetched merely to add a vulnerability bridge. A development reference can be canonical repository graph state while remaining `benchmarked=False`; stronger relations such as `fixed-by` require the graph/evidence conditions implemented by the fix service.

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
| Version applicability | scoped `applicability-status` relation | GitHub Advisory ranges use `github_advisory_range`; OSV ecosystem/native records use `osv_range`; NVD CPE configuration trees write `nvd_cpe` assertions with full boolean/configuration context; CVE Record Format 5.x writes `cve5_version_rule` plus `cve5_default_status`; Red Hat CSAF/VEX now maps `known_affected / known_not_affected / fixed / under_investigation` into scoped canonical states while preserving exact CSAF product IDs, component/platform context, PURL/CPE helpers, and VEX justification flags |
| Fix/remediation | `fixed-version`, `fixed-by` | GitHub Advisory `first_patched_version` and OSV `ECOSYSTEM/SEMVER` fixed events write canonical `SoftwareVersion` + `fixed-version`; OSV GIT fixed hashes remain commit-level evidence for the existing fix-boundary path |
| Exploit state | `known_exploited`, `has-poc`, exploit maturity | CISA KEV writes `known_exploited`; NVD references explicitly tagged `Exploit` now materialize canonical `ExploitArtifact` + `has-poc` with exact reference evidence. Broader exploit-feed coverage remains future work |
| Exploit likelihood | EPSS probability/percentile at observed time | GitHub Advisory EPSS snapshots remain evidence-backed; dedicated FIRST EPSS is now an owned on-demand authority source and writes `epss_probability/percentile` with `source_semantics=first_epss` and `score_date`, preserving point-in-time identity |
| Advisory/reference | canonical advisory/document associations | GitHub Advisory writes canonical `Document` + `described-by`; NVD references explicitly tagged `Vendor Advisory` write canonical URL-addressed `Document` + `vendor-advisory`; Red Hat CSAF/VEX now also materializes the frozen VEX document itself as a vendor-native `vendor-advisory`, bound to the exact CVE locator. Broader vendor/source coverage remains incomplete |
| Asset exposure | `InternetAsset --asset-potentially-affected--> Vulnerability` | Shodan InternetDB explicit host-level `vulns[]` assertions materialize canonical evidence-backed edges. Shodan service observations now also support a deterministic `CPE → full NVD configuration → Vulnerability` join with service-level asset identity, numeric version bounds, AND/OR/negate + companion-CPE evaluation, and dual asset/NVD Evidence. The derived path is regression-tested but is not yet counted as a live-provider benchmark because the dev environment has no authorized Shodan/Censys/FOFA/ZoomEye credential |
| Research/paper | `discusses-vulnerability` | managed research documents now run a deterministic exact-CVE bridge over frozen parsed chunks; semantic extraction remains separate and is not used to create formal gold |
| Incident context | strong-anchor Incident↔Vulnerability bridge | Incident lifecycle exists; canonical benchmark bridge remains backlog |

Supporting edges such as `release-contains-commit`, `asset-runs-product`, and `asset-version`, and open-text `workaround / mitigation / attack_condition`, can remain canonical evidence-backed knowledge while `benchmarked=False`. `poc_available` is a derived convenience projection; formal PoC gold uses `Vulnerability --has-poc--> ExploitArtifact`.

The active M3 implementation backlog is therefore:

1. Product/Package/SoftwareVersion alias normalization beyond the current ecosystem+package+version identity;
2. broader CVE5 comparator semantics plus CSAF/VEX vendor breadth and a live `under_investigation` positive stratum;
3. advisory/document association coverage beyond GitHub Advisory, NVD explicit `Vendor Advisory` tags, and Red Hat CSAF/VEX documents;
4. broader PoC/ExploitArtifact source coverage beyond NVD explicit `Exploit` tags;
5. broaden the implemented AssetObservation → CPE Product/SoftwareVersion → NVD applicability join to authorized live asset snapshots and additional non-numeric/version-scheme comparators;
6. broader paper association beyond exact CVE anchors, with adjudicated semantic-relation gold;
7. Incident → Vulnerability strong-anchor benchmark bridge.

Processor-version refresh is expected to be replay-safe. The canonical writer and NVD durable normalizer reactivate an identical immutable claim/relation when a newer processor run supersedes the previous active source projection and then reproduces the same normalized tuple. This prevents mapper upgrades from accidentally making stable facts disappear.

The deterministic structured path is continuously checked against live provider gold rather than
fixtures alone. The current durable TD3 checkpoint is `m3-real-structured@6`: the same frozen
12-CVE case list now contains **210 formal facts / 210 TP / 0 FP / 0 FN** after adding six NVD
`Vendor Advisory` assertions and closing the evaluated provider universe. It is bound to deployment
`deployment:ae519f4d4d188800f566e669b6c16a25`, run
`1f49b686-7c57-4b6d-9f86-4ae82f91cc47`, and gold revision
`real-structured:7bd4d0be08d71f87e2a9d7c1462b7084f92b327b59a83f37c07734270d3fd944`.
Gold-bearing dimension counts are now:
severity 48, weakness 15, product/package 16, qualifier-aware version applicability 47,
fix/remediation 18, exploit likelihood 48, and advisory/reference **18**.

The main structured runner now also closes its **source universe** explicitly. Snapshot schema
`real-structured-provider-snapshot-v1` evaluates only NVD, GitHub Global Advisories, OSV, FIRST
EPSS, and CISA KEV. Canonical facts backed only by sources outside that frozen world remain in
Knowledge but are reported as `out_of_scope_prediction_count` instead of false positives. On the
210-fact replay, current Knowledge contained 25 such predictions (primarily CVE5 facts already
covered by their own source-specific suite); none entered TP/FP/FN. This prevents a newly connected
provider from making an older frozen suite appear less precise merely because that suite did not
freeze the new provider's world state.

Red Hat CSAF/VEX now has a separate source-specific applicability path and benchmark rather than
being flattened into generic vendor assertions. `redhat-csaf-vex` performs exact-CVE lookup against
the public Red Hat CSAF/VEX tree, persists the raw document as Evidence, and maps each
`product_status` member into a qualifier-scoped `applicability-status`. Production preserves the
full CSAF product ID, component/platform relationship, PURL/CPE identification helpers,
`known_affected / known_not_affected / fixed / under_investigation`, and `flags[].label` VEX
justifications. The evaluator independently reparses the persisted raw CSAF EvidenceArtifact and
filters predictions to Red Hat Evidence only; it does not reuse the production mapper.

The current advisory-expanded frozen stratum is revision 4 and deliberately combines three different VEX
shapes: `CVE-2026-67215` contributes **1 `affected` + 7 `not_affected`** assertions with two live
justification classes (`vulnerable_code_not_present` and `component_not_present`),
`CVE-2024-3094` contributes **26 `not_affected`** assertions, and `CVE-2025-32463` contributes
**33 `fixed` + 13 `not_affected`** assertions. The same three persisted VEX documents now also
contribute one formal `vendor-advisory` fact each, so the result is **83 formal facts / 83 TP /
0 FP / 0 FN**: 80 `version_applicability` plus 3 `advisory_reference`. Gold revision is
`csaf-vex:b8d7557895ad1676756180d52c605ad97ccb787c3be759ffc0e710033b6dfd5c` and provider-world
coordinate `provider-snapshot:cba7f1e65b1c5996b0137cfb9ddeb42a72876bff5a3fb38c34d9767bdaaee5bb`.
`under_investigation` is implemented in the contract and mapper but is still not claimed as live
positive coverage because this frozen stratum contains no such Red Hat status. The durable TD3
coordinates are suite `m3-redhat-csaf-vex@4`, run
`a373b1ea-f5fe-4f67-b6ff-aca8a321b36e`, deployment
`deployment:ae519f4d4d188800f566e669b6c16a25`, and source-specific CompetitionReport
`0154370d-59c7-454d-9396-e6f6830cd8b4` (digest
`66b70c6138e1197715d0b45d4c90643737d765f6570f5b6764a76650acc3fc80`). Earlier suite revisions
remain immutable historical checkpoints; revision 2 is the prior 80-fact applicability-only stratum.

The structured@6 and CSAF/VEX@4 runs are aggregated into current CompetitionReport
`ca75f185-32aa-4c65-b79c-85e69f29fceb` (digest
`656fd526ae4cae34fd2b3e888f45a084da17ad32fda31a5d4f36b61940721e1b`). Across the two explicit
M3 suites the report contains **293 TP / 0 FP / 0 FN** across 15 case-runs; advisory/reference now
contributes **21 TP** across the two provider worlds. Micro precision and recall are both `1.0` and
pass the `>=0.95` development targets. The 293 count is a multi-suite report aggregate, not one
merged 293-fact gold set; the structured and CSAF provider worlds remain
separately versioned.

A separate recent CISA KEV stratum exercises positive exploit-state coverage: 6 real KEV CVEs,
51 formal facts overall, `51 TP / 0 FP / 0 FN`, including `known_exploited` **6/6**. Keeping this
stratum separate prevents a GitHub-heavy sample from making exploit-state look covered when no
positive KEV case was actually present.

PoC is evaluated as a separate positive stratum rather than inferred from KEV or URL shape. The
`nvd-poc` discovery profile uses recent KEV only as a candidate pool, then includes a case **only**
when NVD itself tags a reference `Exploit`. On the first real two-case stratum
(`CVE-2026-67279`, `CVE-2026-7273`), production NVD v4 normalization materialized two canonical
`ExploitArtifact / has-poc` edges and the independent evaluator produced **20 TP / 0 FP / 0 FN**
over 20 formal facts. `exploit_state` scored **4/4**: `known_exploited` 2/2 and `has-poc` 2/2,
with zero missing or extra facts. The formal durable checkpoint is deployment
`deployment:13af2cf3837cd14f28027af83ae236e9`, suite `m3-nvd-poc@1`, run
`2fbcf7ac-ea98-47be-a204-2afa3441a4fa`.

OSV is also tested independently of GitHub/NVD gold. On the 12-CVE recent structured manifest,
9 cases had OSV records with strong GHSA aliases and ecosystem-native package data. After alias
resolution, the source-specific OSV benchmark contains **44 formal facts / 44 TP / 0 FP / 0 FN**:
product/package **11/11**, `osv_range` applicability **19/19**, and fixed/remediation **14/14**.
The three CVEs with no OSV record are reported unavailable and are not inserted into the OSV
denominator.

NVD CPE applicability is now evaluated without flattening configuration trees. On real
`CVE-2026-7273`, NVD exposes ten vulnerable firmware CPE branches, each paired through root `AND`
configuration with a non-vulnerable hardware companion and an exclusive upper version bound. NVD
v5 normalization materialized all ten as qualifier-rich `applicability-status` relations; the
independent evaluator scored **10/10 TP, 0 FP, 0 FN** for `version_applicability`. The whole case,
including severity/CWE/KEV/PoC/EPSS/advisory facts, scored **22 TP / 0 FP / 0 FN** after FIRST EPSS
was added.

FIRST EPSS is independently queryable and time-scoped rather than being inferred from GitHub.
For `CVE-2026-7273`, the live source returned probability `0.02501`, percentile `0.84081`, and
`score_date=2026-09-27`; both formal point-in-time facts scored **2/2** with evidence. Combined
`exploit_likelihood` for the case is **4/4** when the GitHub snapshot and FIRST point-in-time
assertions are kept as distinct source/time facts. `scripts/evaluate_first_epss.py` additionally
checks FIRST in isolation: on the same frozen 12-CVE structured stratum all 12 cases were evaluable,
producing **24 formal facts / 24 TP / 0 FP / 0 FN**. This source-specific runner ignores GitHub EPSS,
so a FIRST regression cannot be hidden by another provider carrying a numerically similar score.

The expanded 12-CVE result is persisted as formal TD3 benchmark evidence under deployment
`deployment:2e302ddbca7b1b3ef6bdc39fdc733f65`, suite `m3-real-structured@3`, run
`ffd7a7e3-8b14-4958-8304-fb5bc160fa51`, and gold revision
`real-structured:b1d05c8777ccfd4b02ce5f14c91056f4de826fdfa069af9fa4699081a0a48c6c`.
The corresponding CompetitionReport is `b6f24b2d-2123-45db-99fd-c156a7f6eaaa` and records
M3 precision/recall as 1.0 while leaving unsupported competition areas explicitly unevaluated.

CVE Record Format 5.x now has a separate source-specific applicability path instead of being
collapsed into the old `affected_products` display claim. Each `versions[]` rule becomes its own
qualifier-scoped `applicability-status`; `unaffected` maps to canonical `not_affected`, omitted
`defaultStatus` becomes an explicit inferred `unknown` fallback, and product identity prefers a
record-provided CPE before falling back to stable CVE5 package/vendor-product identity. The M3 state
conflict key was tightened at the same time: different version scopes on one target no longer count
as a conflict merely because their states differ; only incompatible states within the same scope do.

The first frozen CVE5 stratum deliberately mixes six shapes: exact affected versions
(`CVE-2024-3094`), a semver `<9.3.3` range (`CVE-2025-47828`), omitted default status,
multi-product records, explicit `unknown`, and a package-bearing default-affected record with eight
version rules. Gold is rebuilt independently from persisted raw CVE Program Evidence bytes rather
than from the production normalizer. The result is **38 formal facts / 38 TP / 0 FP / 0 FN**:
product/package **7/7** and version applicability **31/31**. Gold revision is
`cve5-applicability:a04299a83da1cf7ffcfc27f3a70043f3091605b42e7576879fbda9e8534399c9`;
the frozen provider snapshot is
`provider-snapshot:5a1ec3550991c39ad632e138ce973ae0edbee9576498ec68a004c324ef964934`.
This source-specific result is persisted in TD3 as deployment
`deployment:2a602ddc91ebae16bb8dda4991cf7a85`, suite `m3-cve5-applicability@1`, run
`0765bba7-b09d-43d9-9146-d8ea1d558bab`, and CompetitionReport
`af7f9661-54f9-48aa-a3c1-03a4dbf306c3` (digest
`53eac867cff992904209d8b9aeef4a1917777da274f90f0172308bed12b498cf`). The report records M3
precision/recall as 1.0 for this frozen CVE5 slice while leaving unrelated M1/M6/Agent areas
explicitly `not_evaluated`.

The structured evaluator now supports frozen provider-world replay. A live run may persist the raw
NVD/GHSA/OSV/FIRST/KEV-derived snapshot and its `provider-snapshot:<sha256>` coordinate; later code
revisions can score current canonical Knowledge against that exact snapshot without contacting live
providers. TD3 binds the snapshot digest to Suite/Case/Run world coordinates and records replay as
`FROZEN_REPLAY`. Historical reports created before raw snapshot persistence remain live/frozen-gold
checkpoints only; they are not backfilled with an invented world snapshot.

Asset exposure now has its first real positive smoke rather than a contract-only dimension. A
passive Shodan InternetDB lookup for the public security-test host at `44.238.29.244` returned one
explicit host-level vulnerability association, `CVE-2014-4078`. Production post-ingress preserved
the raw Evidence and materialized
`InternetAsset(internet-asset:ip:44.238.29.244) --asset-potentially-affected--> CVE-2014-4078`;
the independent InternetDB evaluator produced **1 formal fact / 1 TP / 0 FP / 0 FN**. This is a
positive-path smoke only, not evidence that arbitrary CPE/version observations can yet be joined to
vulnerability applicability. Asset observations without explicit `vulns[]` remain context-only.
The formal TD3 checkpoint is deployment `deployment:0ecfd8da773ffe47802c5f52e0a42ca0`, suite
`m3-asset-exposure@1`, run `1cac6fb2-bf62-4c72-9119-d2c2dee9b1af`, with CompetitionReport
`f9ff8ada-4b11-447a-a8e3-daddae2d384c` (digest
`b4f8c3db23d4707f28ea958d037a5449105d85a5519354fde0fa8b5aeae485fa`). The report passes the M3
precision/recall development targets for this asset-specific suite and leaves unrelated competition
areas explicitly `not_evaluated`.

The harder CPE-derived asset path is now implemented separately from that provider-explicit smoke.
For Shodan service observations, the join creates service-level `InternetAsset` identity plus
non-benchmarked `asset-runs-product` / `asset-version` support edges, then emits
`asset-potentially-affected` only when the asset CPE set satisfies the complete current NVD
`nvd_cpe` configuration tree. The regression fixture covers: affected `0.10.1` with the required
hardware companion, exclusive-bound `0.11.1` rejection, and rejection when the companion CPE is
missing. A positive derived relation carries Evidence from both the asset Observation and the NVD
applicability Observation. This path is deliberately **not** added to the live M3 denominator yet:
no authorized service-level asset provider credential is configured in the dev environment, so the
current evidence is deterministic regression rather than a claimed live accuracy result.

Research/paper enrichment now has a deterministic exact-anchor baseline. Managed research documents
are parsed and versioned first; a separate `research-exact-cve-bridge` then scans the frozen chunk
text for strict `CVE-YYYY-NNNN...` identifiers and writes
`ResearchWork --discusses-vulnerability--> Vulnerability` with Evidence locators bound to the first
matching chunk/page/character span. Repeated mentions are deduplicated, replay is idempotent, and a
new paper revision with no exact mention supersedes the old relation instead of leaving stale current
Knowledge. On arXiv `2504.17473v1` (XZ Utils supply-chain analysis), production PDF parsing found
exactly `CVE-2024-3094`; independent Atom title/summary gold found the same anchor, producing
**1 formal fact / 1 TP / 0 FP / 0 FN** in `research_paper`. This proves only exact identifier
association; open semantic claims such as attack/defense evaluation remain outside formal M3 gold.
The formal TD3 checkpoint is deployment `deployment:3b37e7acdfd8e9d6154fc33899c5b597`, suite
`m3-research-exact-cve@1`, run `bcfb869d-4f3f-4f06-8cf2-7d875c364837`, with CompetitionReport
`b8bc4b81-f24c-4a77-aa8f-e95179e687f4` (digest
`6a30dd968d8165f2d1cc285022f2526a6453d43c602ca7d22d706f716072d013`).

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
