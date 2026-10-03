# M6 QA benchmark assets

<!-- BEGIN GENERATED QA STATUS -->
## Current M6 formal evidence (generated)

Deployment `deployment:0e16e1b574d5b6383434e7fc80f64cc4`, Knowledge head `knowledge-revision:2053`, resolved model `deepseek-flash`.

| Metric | Current result |
| --- | ---: |
| Answer accuracy | 100.000% |
| Groundedness | 100.000% |
| Citation correctness | 100.000% |
| Multi-hop correctness | 100.000% |
| Interactive latency | 4.032s |

Product run `82a5e288-6d09-40f1-bd80-d4171fc9b629` / `m6-real-product-qa@12`; session run `99da1f9b-441b-465c-a962-76549a7741c7` / `m6-real-product-qa-session@10`. `make benchmark-query METRIC=m6.answer_accuracy` drills into durable per-case observations.
<!-- END GENERATED QA STATUS -->

`current-product-preflight.json` and `current-session-preflight.json` are machine-readable no-model preflight results. `current-preflight.md` is generated from those JSON files; run `make qa-preflight` to refresh all three and `make qa-preflight-doc-check` to verify the Markdown projection without model calls. These artifacts report gold-provenance validity, pinned/current Knowledge coordinates, live-world readiness and model-provider configuration. They are preflight evidence only and never substitute for M6 accuracy/latency metrics in CompetitionReport.

`smoke-v1.json` is synthetic harness verification only. It proves the scorer/runtime wiring and must not be used as competition evidence.

`real-product-v1.candidate.json` and `real-session-v1.candidate.json` are reviewed gold templates. Their checked-in `knowledge_revision` remains the historical provenance coordinate used by no-model preflight, while a formal live batch rebases an in-memory copy to the current Knowledge head and reruns every structured-authority EvidenceRef/fact/path/absence check before it can spend model calls. The generated frozen manifests are written only after a successful batch. Product execution still passes through `AskQuestionUseCase → DecisionRole → TaskRun / Budget / Execution → RecordedModelProvider → validated DecisionResult`.

The candidate currently contains 14 cases: direct NVD CVSS facts, NVD + CISA KEV cross-source facts, one dated FIRST EPSS temporal fact, one CVE Record Format 5.x version-range applicability fact, Red Hat CSAF/VEX `not_affected`/`fixed` applicability facts, one world-relative unknown/continuation case, and one real two-hop development graph case (`CVE → referenced PR → merged-as Commit`). Product Question facts use shared deterministic renderers: ordinary claims stay compact, source-specific claims retain their source identity, FIRST EPSS retains `source_semantics + score_date`, and relation facts retain semantic qualifiers (`state`, version/scope, CSAF status, compact component/platform context and justification) while dropping provenance-only fields and bulky NVD root snapshots. Structured gold may additionally declare `absence_checks`; preflight verifies that the requested canonical predicate is genuinely absent at the pinned Knowledge revision, so an old unknown case fails closed if later Knowledge fills the gap. Required relation paths are also reconstructed from the declared relation EvidenceRefs, so a multi-hop path cannot enter gold merely because it was handwritten in the manifest.

The templates are real benchmark content but are not completed benchmark results. `run_qa_benchmark.py` still fails closed if current Knowledge or the actual Product `ContextManifest.knowledge_revision` differs from the manifest pin. No-model preflight validates historical provenance at the checked-in pin. `make qa-live` handles the live side safely: it first probes the provider, then temporarily stops scheduler/collection/general workers, reads one stable Knowledge head, rebases both templates, validates gold again at that head, freezes one DeploymentRevision, allocates the next suite revisions, executes product + session denominators, and finally restores the data plane even when an exception occurs. The short quiesce prevents background M1–M3 commits from invalidating the live-world pin mid-run while normal operation remains continuously collecting outside the measurement window.

Refresh the historical/no-model preflight at any time:

```bash
uv run python -m scripts.validate_qa_manifest \
  benchmarks/qa/real-product-v1.candidate.json
```

Validate both reviewed templates against the live Knowledge head without changing either source manifest or calling a model:

```bash
make qa-live-preflight
```

Before formal scoring, configure an OpenAI-compatible endpoint. If `/models` exposes exactly one chat model, Base URL + API key are enough; otherwise provide `SECFUSION_MODEL_NAME` explicitly. Probe first:

```bash
export SECFUSION_MODEL_BASE_URL='https://provider.example/v1'
export SECFUSION_MODEL_API_KEY='...'
make model-provider-probe
```

Then run the complete formal competition batch:

```bash
make qa-live
```

`make qa-live` is intentionally larger than a QA-only loop. Once Product + session QA succeed, the same frozen DeploymentRevision is reused to rerun the fixed M1 window, frozen structured M3 replay, frozen CSAF/VEX replay and controlled fault-recovery suite. Only after all runs complete does the batch persist a new `benchmarks/competition/current-run-set.json`, CompetitionReport, QA/M1/M3/fault `current*.json` files and generated README projections. This prevents a high QA score from being combined with M1/M3 numbers produced by a different code/model configuration. Suite revisions are allocated from durable `benchmark_suites`; no revision number or DeploymentRevision id is typed by hand.

QA-specific successful output is written to `current-live-batch.json`, `current-product-manifest.json`, `current-session-manifest.json`, `current-product.json`, and `current-session.json`. The data-plane writers are restored in `finally` after success or failure.

`real-session-v1.candidate.json` contains two two-turn Product sessions. The first asks for NVD CVSS and then a dated FIRST EPSS fact with no repeated target, exercising canonical target carry. The second sends the exact same `RETRIEVE` question twice: turn 1 binds `CVE-2026-7273`, turn 2 omits `cve_id/object_id`, so a live run exercises the exact-request `executed → reused` path while preserving the same factual NVD gold. All four turns have independent structured-authority gold and EvidenceRefs. Session evaluation reuses the normal per-turn QA scorer, then derives context-chain, target-carry and retrieval diagnostics from durable Product/runtime provenance.

Validate all four structured-authority turns without a model call:

```bash
uv run python -m scripts.validate_qa_manifest \
  benchmarks/qa/real-session-v1.candidate.json
```

This first session denominator measures turn correctness, durable context chaining and canonical target carry. Follow-up `RETRIEVE` turns now expose three separate retrieval diagnostics. `m6.session_retrieval_overlap_rate` reports how many current `document-chunk:*` refs were already exposed by prior turns. `m6.session_retrieval_invocation_coverage` checks whether the expected retrieval turn has exactly one durable `RetrievalInvocation`. `m6.session_retrieval_reuse_rate` reads that invocation's `executed/reused` disposition, so exact Product-level reuse is measured from operational provenance instead of inferred from chunk overlap. The current reuse policy is intentionally strict: only the same Product session + exact request digest + same Knowledge revision/operator/limit/source scope may reuse prior ordered chunk refs; any stale/missing chunk ref falls back to a fresh lexical search.

`session-overlap-diagnostic-v1.json` is a separate live-external evaluation-infrastructure denominator pinned at Knowledge revision 1731. It exists because the reviewed reuse candidate can legitimately execute/reuse an empty retrieval result, in which case chunk-overlap has no denominator and must remain `not_evaluated` even though invocation coverage/reuse are measurable. The diagnostic uses the same CVE target and structured-authority CVSS gold but a deliberately minimal `CVSS score` retrieval query that has non-empty lexical results. `session-overlap-diagnostic-current.json` records BenchmarkRun `a395c200-7eb1-439d-99b9-532f5e748377`: both turns score 1.0 on QA, the first invocation executes a non-empty result set, the second reuses it, and overlap / invocation coverage / reuse are all 1.0. This diagnostic closes the metric implementation/provenance gap; it does not replace the reviewed natural-language session denominator.
