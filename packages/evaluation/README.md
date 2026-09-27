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
  --output /tmp/secfusion-real-enrichment-eval.json
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
`CWE+EPSS` cases. On the 2026-09-27 **12-CVE recent structured stratum**, the expanded formal slice
contains **150 gold facts** and produces **150 TP / 0 FP / 0 FN**. Gold-bearing dimension counts are:
severity 48, weakness 15, product/package 14, version applicability 22, fix/remediation 15,
exploit likelihood 24, and advisory/reference 12. The discovery manifest is written outside the
repo for live probing; a competition benchmark must freeze the chosen case list as a suite revision.

Because public NVD access is rate-limited, the discovery/evaluation utilities explicitly throttle
and retry NVD requests when no API key is configured. Provider transport failures are not counted as
M3 false negatives.

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

The next priority is assets and broader CVE/NVD/CSAF applicability, followed by paper/incident
benchmark bridges and broader advisory/PoC source coverage.
