# `packages.evaluation`

`packages.evaluation` owns executable evaluation contracts across two layers: TD1's M1–M3 source/enrichment metrics, and TD2's M7 replay/regression and Skill promotion gate. Requirements define the competition-facing outcomes; TD1/TD2 define the frozen runtime semantics; this package turns both into concrete denominators, replay coordinates, pass/fail rules and durable validation results.

## Competition reporting profile

Requirements remain the authority for competition targets. The executable evaluation layer uses the finals target as the stricter development profile: enrichment micro precision and recall both target `>=95%`. The preliminary-round report can reuse the same fixed benchmark and report the required accuracy/precision view without maintaining a second enrichment ontology.

The scoring threshold does not redefine the data contract. Formal enrichment P/R is always calculated over the versioned, benchmarked closed set; open semantic discoveries and non-benchmarked support edges do not enter the denominator merely to improve coverage.

## Source category coverage

`PRODUCT_SOURCE_CATEGORY_ORDER` freezes the eight product categories in product order:

```text
vulnerability / development / academic / vendor /
independent / normative / assets / incidents
```

`source_coverage_report` derives support from `config/source-inventory.json`. A category counts only when inventory ownership is `owned` and backed by a fixed/grouped executable owner. Provider reachability and dynamic resolution do not inflate category coverage.

Website catalog conformance is tested against the same category order.

## Source delivery coverage

`SourceDeliveryKey` defines the fixed-window source event identity:

```text
source_id
external_object_id
external_revision OR content_hash
```

At least one revision discriminator is required. `source_delivery_coverage` separately reports expected, accepted expected, missed, and unexpected keys. Unexpected observations do not increase the coverage numerator.

## Monitoring latency

`MonitoringLatencySample` measures `published_at -> M2 available_at/committed_at`. Samples without reliable publication time remain in `evaluable_coverage` but are excluded from numeric latency aggregation.

The helper reports p50, p95, max, and the rate within six hours. These are diagnostics; the competition text defines the six-hour threshold but does not define one aggregate statistic as the official gate.

## M2 diagnostic metrics

M2 correctness is reported separately from formal M3 enrichment P/R:

- `parser_field_accuracy` — extracted value + locator correctness on fixed source revisions;
- `replay_suppression_accuracy` — replay does not create duplicate factual versions;
- `entity_resolution_precision / recall` — same-object decisions on a gold identity-pair set;
- `evidence_correctness` — accepted claim/relation evidence resolves and actually supports the assertion;
- `conflict_preservation` — competing source assertions remain represented instead of becoming last-write-wins.

These metrics diagnose why enrichment failed; they are not added to the official P/R numerator/denominator.

## Enrichment gold identity

`EnrichmentFactKey` is a closed-set benchmark fact, not a generic Knowledge record. It contains:

```text
root_object_key + root_object_type
vocabulary_revision
dimension
kind = claim | relation
predicate_or_relation_type
normalized value or target id
target_object_type when relevant
qualifier keys + normalized qualifier
temporal scope
```

Construction validates the fact against `enrichment-v1`: the term must be canonical and `benchmarked=True`, dimension must match, subject/target shape must match, required qualifiers must be present, and vocabulary revision must be supported.

This prevents fixture authors from creating gold that the runtime vocabulary itself considers invalid.

Benchmark dimension membership is evidence-conditional. A dimension enters a case gold set when the frozen world/source snapshot contains adjudicable evidence for that dimension; the closed set does not imply every vulnerability must have every one of the twelve dimensions. Missing source evidence therefore does not create an artificial FN, while a system miss on evidence that exists in the frozen snapshot does.

## Evidence-aware scoring

`EnrichmentPrediction` wraps a fact with evidence references and `evidence_correct`. A tuple match without valid evidence is not a TP. If the fact has only invalid-evidence predictions, it contributes FP and the corresponding gold remains FN. A valid duplicate dominates invalid duplicates for the same fact.

The scorer returns micro precision/recall and per-dimension scores plus dimension-macro P/R. Empty prediction with non-empty gold reports zero precision/recall instead of a false perfect precision.

Canonical Knowledge can contain non-benchmarked information. Open text, repository support edges, intermediate asset edges, and exploratory semantic relations stay available to the product while remaining outside the formal closed-set scorer.

## Gold source policy

Gold prefers evidence that can be adjudicated independently of the model under test:

- structured authority records: CVE Record, NVD, OSV, GHSA, CSAF/VEX, CISA KEV, FIRST EPSS;
- repository relations: fixed repository snapshot plus commit/release ancestry;
- asset relations: fixed `AssetObservation` plus product/version/applicability gold;
- paper exact association: fixed paper revision and exact identifier/text evidence;
- open semantic research relations: human dual annotation/adjudication before they can become official gold. LLM-as-judge alone does not create formal gold.

## Benchmark strata and snapshot identity

The fixed suite must include at least:

- structured-only CVE enrichment;
- multi-source conflict on severity/version assertions;
- CVE 5.x version ranges;
- OSV SEMVER/ECOSYSTEM and GIT fixed ranges;
- release containment for fixed commits;
- NVD CPE AND/OR configurations;
- CSAF/VEX `not_affected` / `under_investigation`;
- KEV exploited vs non-KEV cases;
- EPSS point-in-time score;
- PoC present without known exploitation and known exploitation without public PoC;
- time-bounded asset observation + affected-version matching;
- paper exact association and semantic-relation cases;
- Incident strong-anchor association;
- alias/entity ambiguity and wrong-version traps.

A benchmark case freezes `world_snapshot`, source availability, source revisions, vocabulary revision, and evaluator revision. Historical evaluation must not silently consume later provider updates, patches, or postmortems.

For the main structured M3 runner, the world snapshot is now an executable artifact rather than a
documentation convention. `scripts/evaluate_real_enrichment.py --snapshot-output ...` writes the
raw NVD / GitHub Advisory / OSV / FIRST EPSS / KEV-derived provider inputs used to build gold, under
schema `real-structured-provider-snapshot-v1`. The canonical JSON bytes are hashed into a
`provider-snapshot:<sha256>` coordinate. A later run can use `--snapshot-input ...`; the requested
CVE set and snapshot schema must match exactly or evaluation fails closed. Reports record
`provider_snapshot_revision` and `gold_source_mode`, and TD3 registration binds that coordinate to
`BenchmarkSuite.default_world_snapshot_ref`, each `BenchmarkCase.world_snapshot_ref`, and the
`BenchmarkRun.world_snapshot_ref`. Snapshot replay is registered as `FROZEN_REPLAY` rather than
`LIVE_EXTERNAL`.

This contract starts with snapshots explicitly frozen after the feature landed. The earlier
204-fact, PoC, and NVD-CPE reports contain frozen gold facts but did not retain the raw multi-provider
snapshot, so they are **not** retroactively relabeled as frozen-world replay runs.

## Deterministic baseline comparison

The baseline used to measure Agent/semantic gain contains no LLM planner or free semantic relation generation. It performs exact identifier normalization, structured provider lookup, fixed schema projection, product/package identity mapping, source-specific applicability evaluation, repository graph closure, KEV/EPSS exact joins, asset observation joins, exact paper association, EvidenceRef binding, conflict preservation, and unknown-on-miss behavior.

Agent/semantic improvements are measured as additional canonical recall/gap resolution under the same gold and evidence rules, with latency/cost reported separately rather than by changing the denominator.

## M7 replay comparison

`m7_replay.py` compares a baseline and one explicit candidate intervention against the same durable `ReplayCheckpoint`. A replay case pins Task/Context/Trajectory/world/runtime coordinates and expected protocol/domain outcome; an observation is rejected if its case id, variant id or freeze hash drifts from the frozen coordinate.

Candidate variants must declare exactly one intervention. The current replay contract covers loop topology, context handoff, policy revision, sandbox profile, Skill ref and Capability Registry revision. `M7ReplayService` separates protocol failure from quality metrics, then applies explicit metric direction/tolerance rules. A candidate is not considered acceptable merely because the final answer improved if protocol conformance regressed.

`packages.investigation.replay` owns checkpoint capture, historical M4 reconstruction and fail-closed world preparation; this package owns comparison/scoring. True historical Agent re-execution remains blocked when the pinned M1–M3 Knowledge revision is no longer readable through a versioned Knowledge path. The evaluator must not substitute the latest projection.

## Experience → Skill promotion

`skill_promotion.py` is the promotion authority for Experience-derived Skill patches. `SkillPatchCandidate` construction remains under `packages.investigation.experience`; M7 decides whether a candidate may become active.

Promotion requires a fixed replay suite containing support, counterexample and regression cases. The gate verifies that the candidate-declared `support_refs` and `counterexample_refs` are actually represented by suite `source_ref`s, so a patch cannot claim validation on unrelated easy cases. Replay results and validation refs are durable; failed regression blocks activation instead of silently leaving a candidate in online selection.

## Design → implementation map

TD1 的 M1/M3 评测由 `m1_m3.py` 实现：source category、fixed-window delivery、latency 与 evidence-aware enrichment P/R 都有稳定 identity/denominator。TD2 的 M7 评测由 `m7_replay.py` 接 durable ReplayCheckpoint，要求 baseline/candidate 在同一 freeze hash 上比较；`skill_promotion.py` 再把 support/counterexample/regression replay 变成 Skill promotion gate。评测层可以读取 frozen runtime artifact，但不参与在线 Task、Policy 或 Knowledge write。

比赛目标和内部 protocol gate 也保持分离：评委关心监测延迟、富化 P/R、问答准确/多跳和 Agent 自动化；M7 额外检查 Context/Policy/Sandbox/Skill 等实现变更是否破坏协议。内部 replay 通过不能代替比赛 QA 指标。

## Current scope and competition gap

Executable coverage now includes source-category coverage, source delivery/latency, evidence-aware enrichment P/R, frozen replay comparison, Skill promotion regression, and an evaluation-neutral M6 QA scorer. `QAGold + QAPrediction -> QAScore` separates answer accuracy from groundedness, citation correctness/completeness, multi-hop path correctness, unknown/conflict handling, completion semantics and interactive latency. `scripts/run_qa_benchmark.py` can execute a frozen fixture through the same durable Benchmark Runtime; the bundled `benchmarks/qa/smoke-v1.json` is explicitly synthetic harness verification and is not competition evidence.

The remaining competition-critical M6 gap is no longer the scorer substrate. It is the real product benchmark: fixed human/adjudicated questions and world snapshots, Product/Decision -> `QAPrediction` adapters, multi-turn/session cases, and measured live interactive/investigation latency. Security/adversarial and fault-injection cases are specified by Requirements/TD2/TD3 but still need frozen real suites and product/runtime adapters.

## TD3 Benchmark Runtime

`packages.evaluation.benchmark` owns the durable evaluation substrate introduced by TD3:

```text
DeploymentRevision
BenchmarkCase@revision
BenchmarkSuite@revision
BenchmarkRun
BenchmarkCaseRun
MetricObservation@metric-definition-revision
```

Suite and case revisions are immutable. A `BenchmarkRun` binds one frozen suite/gold revision to one `DeploymentRevision`; a run cannot finish while a case is still active. Metric observations can only be appended to running case runs and must match a registered metric definition's direction/unit. The first observation of a metric revision persists an immutable `MetricDefinition` row containing denominator, aggregation, missing-value policy, direction, unit and a definition digest. Formula changes therefore require a new metric definition revision instead of silently rewriting history.

`CompetitionReportService` only aggregates an explicit list of completed runs from the same deployment revision. It does not search for whichever run is newest and does not mix deployments implicitly. Aggregation reads the durable metric-definition revisions referenced by the observations; a report fails if those definitions are missing or if one metric name mixes revisions. M3 global micro precision/recall are re-derived from summed TP/FP/FN rather than averaging per-case ratios. `generate_and_persist()` stores a durable `CompetitionReport` payload, deterministic content digest, run set and metric-definition refs; repeated exports of the same logical report are idempotent.

Competition target checks are deliberately narrow and factual: source-category count `>=7`, enrichment precision/recall `>=0.95`, QA accuracy `>=0.95`, and interactive QA latency `<=5s`. Missing metrics are `not_evaluated`, never zero-filled. Monitoring latency still reports p50/p95/max/`<=6h` rate because Requirements freeze those statistics, but the competition text does not define one aggregate latency pass formula, so the report does not invent one.

`RegressionGate` compares two explicit reports under version-compatible metric definitions and supports hard floor/ceiling, maximum regression and minimum improvement rules. It fails closed when a required metric is missing or its definition revision changed.

## Reproducible execution entry points

```bash
# Unit/architecture gate for the evaluation substrate
make evaluation-check

# Formal batch: freeze one deployment coordinate, then pin every module run to it.
uv run python scripts/freeze_deployment_revision.py \
  --output /tmp/deployment.json
# Read deployment_revision_id from the JSON below as <deployment-id>.

# M1: fixed-window monitoring benchmark. Only scheduled acquisition enters latency.
# published_at -> earliest Knowledge committed_at is the measured latency.
uv run python scripts/run_m1_benchmark.py \
  --window-start 2026-09-27T00:00:00Z \
  --window-end 2026-09-28T00:00:00Z \
  --suite-revision 2 \
  --deployment-revision-id '<deployment-id>' \
  --output /tmp/m1-benchmark.json

# M3: freeze a real structured-provider report, then register it explicitly.
uv run python scripts/evaluate_real_enrichment.py \
  CVE-2025-47828 CVE-2024-13980 CVE-2024-13981 \
  CVE-2024-13984 CVE-2024-13985 CVE-2026-48746 \
  --output /tmp/m3-real.json
uv run python scripts/register_real_enrichment_benchmark.py \
  /tmp/m3-real.json --suite-revision 1 \
  --deployment-revision-id '<deployment-id>'

# M6 harness smoke only; the bundled fixture is synthetic.
uv run python scripts/run_qa_benchmark.py \
  benchmarks/qa/smoke-v1.json \
  --deployment-revision-id '<deployment-id>' \
  --output /tmp/m6-smoke.json

# Export only explicitly selected runs from one DeploymentRevision.
uv run python scripts/export_competition_report.py \
  --deployment-revision-id '<deployment-id>' \
  --run-id '<m1-run-id>' --run-id '<m3-run-id>' \
  --json-output /tmp/competition-report.json \
  --markdown-output /tmp/competition-report.md
```

`capture_current_deployment_revision` reads the actual Alembic revision, source inventory hash, vocabulary revision, runtime policy revision, seed Skill registry digest and non-secret model/config coordinate. A dirty worktree is labeled `HEAD+dirty.<digest>` instead of pretending to be the clean Git commit. For a formal benchmark batch, `freeze_deployment_revision.py` must be run once and its ID pinned into every module runner. Per-run auto-capture remains available for local smoke only; it is intentionally not the release workflow because a concurrently edited dirty worktree can change between two otherwise adjacent runs.

## Dependency boundary

Allowed dependencies follow the architecture gate: `shared`, `sources`, `intelligence`, `investigation`, `task_runtime`, `runtime`, `evaluation`.

Evaluation must not become an online decision owner. It may consume frozen runtime/investigation contracts and durable replay artifacts, but M1/M3/M5 execution decisions remain in their owning modules.

## Verification

```bash
uv run pytest packages/evaluation -q
```

## Live structured enrichment probe

`scripts/evaluate_real_enrichment.py` is a small real-data benchmark runner for checking the
current canonical M3 output against fresh structured provider records. It deliberately does not
reuse production mappers to construct gold. The current v1 probe fetches NVD, GitHub Advisory,
OSV, and CISA KEV records, then constructs gold independently from production mappers. The current
formal slice covers canonical severity, weakness/CWE, package, qualifier-aware version
applicability, fixed-version, positive KEV state, EPSS likelihood, and GitHub advisory/document
association facts whose identity/semantics are stable enough for non-circular comparison.

Example:

```bash
uv run python scripts/discover_real_enrichment_cases.py \
  --count 12 --output /tmp/secfusion-m3-stratum.json

uv run python scripts/evaluate_real_enrichment.py \
  CVE-2025-47828 CVE-2024-13980 CVE-2024-13981 \
  CVE-2024-13984 CVE-2024-13985 CVE-2026-48746 \
  --snapshot-output /tmp/secfusion-provider-snapshot.json \
  --output /tmp/secfusion-real-enrichment-eval.json

# Re-score a later deployment against exactly the same provider world:
uv run python scripts/evaluate_real_enrichment.py \
  --snapshot-input /tmp/secfusion-provider-snapshot.json \
  --output /tmp/secfusion-real-enrichment-replay.json
```

The output still reports structured diagnostics for source fields and future denominator expansion.
This separation matters: a high score on the implemented structured slice must not be presented as
competition-wide enrichment precision/recall.

After the 2026-09-27 deterministic refresh and second denominator expansion (`cvss_version`,
canonical CWE relations, GitHub `fixed-version`, EPSS, qualifier-aware GitHub advisory ranges,
and GHSA `described-by`), the six-case real-data probe now contains **57 formal gold facts** and
produces **57 TP / 0 FP / 0 FN** (`micro precision = 1.0`, `micro recall = 1.0`) on that frozen
structured slice. Version-applicability facts compare package identity plus
`state/source_semantics/version_range`; they are not reduced to an unscoped boolean edge. This is
an implementation checkpoint, not a claim that all twelve `enrichment-v1` dimensions are complete.

A second reproducible live stratum is selected independently from the latest 100 GitHub Global
Advisories (`updated desc`, CVE-bearing, not withdrawn), prioritizing `range+fix`, `range-only`, and
`CWE+EPSS` cases. The durable 2026-09-27 TD3 checkpoint contains **204 gold facts / 204 TP / 0 FP /
0 FN**. A later live snapshot on the same 12-CVE case list adds six NVD references explicitly tagged
`Vendor Advisory`, taking the slice to **210 gold facts / 210 TP / 0 FP / 0 FN**; replay against the
frozen raw provider snapshot reproduces the same score and the same gold revision. Gold-bearing
dimension counts are now severity 48, weakness 15, product/package 16, version applicability 47,
fix/remediation 18, exploit likelihood 48, and advisory/reference **18**.

The mixed structured runner evaluates a closed provider world, not every canonical fact currently
present in the database. Snapshot schema `real-structured-provider-snapshot-v1` owns five source IDs:
`nvd-cves-2`, `github-global-advisories`, `osv-vulnerabilities`, `first-epss`, and `cisa-kev`.
Predictions with Evidence only from another provider are retained in Knowledge but counted as
`out_of_scope_prediction_count`, not FP. This rule was added after CVE5 enrichment correctly wrote
new product/applicability facts into the same CVEs: without source scoping, 15 of those valid facts
appeared as false positives and dropped apparent precision to `0.9333`; with the suite's source
universe enforced, the same frozen 210-fact snapshot scores **210/0/0** while reporting **25**
out-of-scope current predictions separately. CVE5 remains measured by its own frozen source-specific
suite until a future snapshot schema explicitly includes CVE Program raw records.

The main evaluator independently follows OSV CVE→GHSA strong aliases when the CVE conversion record
does not carry package identity. This mirrors the source semantics but does not reuse the production
OSV mapper. Before that evaluator fix, 24 valid OSV-native Knowledge facts appeared as false
positives; after adding the missing gold records, the same database state moved from `180 TP / 24 FP
/ 0 FN` to **204 TP / 0 FP / 0 FN**. This is an evaluator correction, not a production precision
improvement, and is recorded as such so benchmark changes cannot be mistaken for model/system gain.

NVD advisory/reference coverage is also structured rather than URL-heuristic. Production only
materializes `Vulnerability --vendor-advisory--> Document` when NVD itself tags a reference exactly
`Vendor Advisory`; the independent gold builder applies the same provider-level criterion without
reusing the production mapper. Document identity is URL-content-addressed and the relation keeps the
exact NVD reference locator. On the latest 12-CVE snapshot this contributes six additional formal
facts, taking `advisory_reference` from 12/12 GitHub `described-by` facts to **18/18** mixed-source
facts with zero FP/FN.

Because public NVD access is rate-limited, the discovery/evaluation utilities explicitly throttle
and retry NVD requests when no API key is configured. Provider transport failures are not counted as
M3 false negatives. GitHub/NVD/other live-provider rate limits affect acquisition of a **new** gold
snapshot, but no longer block regression scoring once a provider snapshot has been frozen.

The discovery tool also exposes a `kev-recent` profile. On the 2026-09-27 six-case recent CISA KEV
stratum (ordered by `dateAdded desc`), production refresh returned one KEV record for every case and
the independent evaluator produced **51 TP / 0 FP / 0 FN** over 51 formal facts. In particular,
`exploit_state` was exercised by six positive `known_exploited` facts and scored **6/6**. This
stratum is intentionally separate from the GitHub-structured sample so positive exploit-state
coverage is visible rather than diluted by a set with no KEV members.

PoC coverage has its own `nvd-poc` profile. Candidate discovery starts from recent KEV entries only
to improve hit rate, but inclusion is determined independently by NVD structured data:
`references[].tags` must contain the exact `Exploit` tag. Production normalization preserves the
reference index and maps the URL to a stable canonical `ExploitArtifact`, while formal gold is built
independently from the same NVD structured assertion rather than reusing the production mapper.
On the initial two-case positive stratum (`CVE-2026-67279`, `CVE-2026-7273`), the evaluator produced
**20 TP / 0 FP / 0 FN** over 20 facts; `exploit_state` was **4/4**, consisting of
`known_exploited` 2/2 and `has-poc` 2/2. There were no missing or extra formal facts. This result is
also persisted in TD3 Benchmark Runtime under deployment
`deployment:13af2cf3837cd14f28027af83ae236e9`, suite `m3-nvd-poc@1`, benchmark run
`2fbcf7ac-ea98-47be-a204-2afa3441a4fa`.

Example discovery:

```bash
uv run python scripts/discover_real_enrichment_cases.py \
  --profile nvd-poc --count 4 \
  --output /tmp/m3-nvd-poc.json
```

OSV applicability is evaluated with a separate source-specific diagnostic so GitHub assertions do
not mask OSV failures. A CVE conversion record with no package does not create an empty "success":
the benchmark independently follows strong GHSA aliases and requires package-bearing native OSV
records. On the same 12-CVE recent manifest, 9 cases were OSV-evaluable and produced **44 formal
facts / 44 TP / 0 FP / 0 FN**: product/package 11, `osv_range` applicability 19, and
fixed/remediation 14. Three OSV-unavailable cases are explicit non-denominator cases. A zero-fact
OSV selection fails closed rather than inheriting the scorer's mathematical `0/0 -> 1.0` default.

NVD CPE applicability is scored as qualifier-aware structured gold, not as a flattened affected
version list. The fact identity includes canonical Product target plus `state=affected`,
`source_semantics=nvd_cpe`, full CPE criteria, version bounds, and a configuration snapshot that
retains root/node `AND/OR/negate` and companion matches. On `CVE-2026-7273`, ten real NVD CPE
branches produced **10 TP / 0 FP / 0 FN** in `version_applicability`; no tree information was
dropped to obtain the score.

FIRST EPSS is now a separate formal point-in-time source. Its gold and prediction keys include
`source_semantics=first_epss`, `score_date`, and `temporal_scope=score_date`, preventing one day's
score from overwriting or being compared as if it were another day's fact. A live
`CVE-2026-7273` refresh returned probability `0.02501`, percentile `0.84081`, date `2026-09-27`;
the dedicated FIRST facts scored **2/2**. The same case currently contains **22 formal facts** and
scores **22 TP / 0 FP / 0 FN** overall, including NVD CPE applicability 10/10.

Asset exposure has a separate formal suite rather than being folded into CVE-only enrichment. The
Shodan InternetDB positive case `44.238.29.244 -> CVE-2014-4078` produced **1 TP / 0 FP / 0 FN**
with provider-bound Evidence. It is persisted under deployment
`deployment:0ecfd8da773ffe47802c5f52e0a42ca0`, suite `m3-asset-exposure@1`, run
`1cac6fb2-bf62-4c72-9119-d2c2dee9b1af`, and CompetitionReport
`f9ff8ada-4b11-447a-a8e3-daddae2d384c`. The suite intentionally proves only explicit host-level
provider assertions; CPE/version-derived asset applicability remains a separate backlog item.

Research/paper exact association is evaluated independently from semantic extraction. Production
reads the frozen arXiv PDF revision through the managed-document parser and exact-CVE bridge; gold is
constructed from the separately fetched arXiv Atom title/summary for that same versioned paper ID.
On `2504.17473v1`, both views contain only `CVE-2024-3094`, yielding **1 TP / 0 FP / 0 FN** for
`research_paper`. A paper revision mismatch fails closed, and a zero-gold selection is rejected
rather than inheriting a vacuous score. Open semantic research relations still require human
annotation/adjudication before they can enter an official benchmark denominator. The formal run is
deployment `deployment:3b37e7acdfd8e9d6154fc33899c5b597`, suite `m3-research-exact-cve@1`, run
`bcfb869d-4f3f-4f06-8cf2-7d875c364837`, CompetitionReport
`b8bc4b81-f24c-4a77-aa8f-e95179e687f4`.

FIRST can also be evaluated independently of the mixed structured suite:

```bash
uv run python scripts/evaluate_first_epss.py \
  CVE-2026-7273 \
  --output /tmp/m3-first-epss.json
```

On the frozen 12-CVE structured stratum, the current source-specific FIRST run has 12/12 evaluable
cases and **24 formal facts / 24 TP / 0 FP / 0 FN**, with no missing or extra facts. This runner
intentionally ignores GitHub EPSS so source-specific failures cannot be hidden by a second provider
carrying a numerically similar score.

CVE Record Format 5.x applicability now has its own frozen source-specific benchmark. Production
normalization preserves per-rule scope (`version`, `versionType`, `lessThan`,
`lessThanOrEqual`, `changes`) and a separate `defaultStatus` fallback instead of flattening a record
to one affected boolean. The evaluator independently reparses persisted raw CVE Program
EvidenceArtifact bytes, so mapper code is not reused for gold. On six deliberately mixed records the
suite contains **38 formal facts / 38 TP / 0 FP / 0 FN**: product/package **7/7** and qualifier-aware
version applicability **31/31**. The gold revision is
`cve5-applicability:a04299a83da1cf7ffcfc27f3a70043f3091605b42e7576879fbda9e8534399c9`
and the exact provider-world coordinate is
`provider-snapshot:5a1ec3550991c39ad632e138ce973ae0edbee9576498ec68a004c324ef964934`.
This benchmark also exercises explicit `not_affected` and `unknown` fallback semantics rather than
counting only positive affected ranges.
The durable TD3 coordinates are deployment `deployment:2a602ddc91ebae16bb8dda4991cf7a85`, suite
`m3-cve5-applicability@1`, run `0765bba7-b09d-43d9-9146-d8ea1d558bab`, and CompetitionReport
`af7f9661-54f9-48aa-a3c1-03a4dbf306c3` with digest
`53eac867cff992904209d8b9aeef4a1917777da274f90f0172308bed12b498cf`. The report passes the M3
precision/recall development targets for this suite; source coverage, QA and Agent metrics remain
explicitly unevaluated rather than being filled with synthetic zeros.

The next live structured priority is CSAF/VEX applicability. The CPE/version-derived asset join
itself is implemented and regression-tested against positive, wrong-version, and missing-companion
cases, but remains outside the live denominator until an authorized service-level asset snapshot can
be frozen and independently scored.

Asset exposure also has a separate source-specific positive smoke. `scripts/evaluate_asset_exposure.py`
constructs gold directly from Shodan InternetDB's explicit host-level `vulns[]` response and scores
only active canonical `asset-potentially-affected` relations backed by `shodan-internetdb-assets`
Evidence. On the public security-test host `44.238.29.244`, InternetDB currently reports
`CVE-2014-4078`; the production path and independent evaluator agree on **1 gold fact / 1 TP / 0 FP
/ 0 FN**. The canonical asset identity is host-level (`internet-asset:ip:<ip>`) because InternetDB
returns vulnerability association at host scope even though service observations are emitted per
port. This benchmark deliberately does not infer affectedness from CPE alone.

The asset result expands formal dimensional coverage but is intentionally small. A harder
deterministic join now exists for Shodan service observations:
`AssetObservation → CPE Product/SoftwareVersion → full NVD CPE configuration → Vulnerability`.
Its regression includes a true affected case, an exclusive-bound wrong-version case, and a
missing-companion case; only the true case produces `asset-potentially-affected`, and the relation
is backed by both asset and NVD Evidence. Because the current dev environment has no authorized
service-level asset feed, those regression cases are **not** promoted into the live formal
denominator. The InternetDB 1/1 suite therefore remains the only formal live asset checkpoint and
must not be described as general asset affectedness accuracy.

### Formal TD3 checkpoint — 2026-09-27

The 204-fact structured result is also persisted in the TD3 Benchmark Runtime rather than existing
only as a local JSON probe:

- Deployment: `deployment:2e302ddbca7b1b3ef6bdc39fdc733f65`
- Git coordinate: `a9241081cb05b1ec8c6eefbf55380885e42f7656`
- M3 suite: `m3-real-structured@3`
- M3 run: `ffd7a7e3-8b14-4958-8304-fb5bc160fa51`
- Gold revision: `real-structured:b1d05c8777ccfd4b02ce5f14c91056f4de826fdfa069af9fa4699081a0a48c6c`
- M1 suite/run on the same deployment: `m1-monitoring-window@4` / `410ed858-b0a2-4442-8689-136957ef129c`
- CompetitionReport: `b6f24b2d-2123-45db-99fd-c156a7f6eaaa`
- Report digest: `59bd696f64c26a5e338cf95a25a61bcd08c82d0e80b498bb1b4ce0edd2160aa7`
- Frozen M3 JSON digest: `sha256:7bd3fda088be6e659f47f7d5502944421ec073fe2b0c570b95a39ad3bef7ad56`

The report passes the current source-category target (8 observed, threshold 7) and the M3
precision/recall development targets (both 1.0, threshold 0.95). M1 monitoring latency remains
`not_evaluated` because the selected fixed window contains no eligible `scheduled` samples; M6 QA,
Agent runtime, and fault/recovery remain explicitly unevaluated rather than receiving inferred or
zero-filled scores.
