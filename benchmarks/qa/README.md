# M6 QA benchmark assets

`smoke-v1.json` is synthetic harness verification only. It proves the scorer/runtime wiring and must not be used as competition evidence.

`real-product-v1.candidate.json` is the first real Product QA candidate. Its gold is built from exact structured authority facts already materialized in canonical Knowledge, with backing source IDs and EvidenceRefs bound through `gold_provenance`. It is pinned to Knowledge revision `606` and uses `live_product_question`, so execution must pass through `AskQuestionUseCase → DecisionRole → TaskRun / Budget / Execution → RecordedModelProvider → validated DecisionResult`.

The candidate currently contains 14 cases: direct NVD CVSS facts, NVD + CISA KEV cross-source facts, one dated FIRST EPSS temporal fact, one CVE Record Format 5.x version-range applicability fact, Red Hat CSAF/VEX `not_affected`/`fixed` applicability facts, one world-relative unknown/continuation case, and one real two-hop development graph case (`CVE → referenced PR → merged-as Commit`). Product Question facts use shared deterministic renderers: ordinary claims stay compact, source-specific claims retain their source identity, FIRST EPSS retains `source_semantics + score_date`, and relation facts retain semantic qualifiers (`state`, version/scope, CSAF status, compact component/platform context and justification) while dropping provenance-only fields and bulky NVD root snapshots. Structured gold may additionally declare `absence_checks`; preflight verifies that the requested canonical predicate is genuinely absent at the pinned Knowledge revision, so an old unknown case fails closed if later Knowledge fills the gap. Required relation paths are also reconstructed from the declared relation EvidenceRefs, so a multi-hop path cannot enter gold merely because it was handwritten in the manifest.

The file is real benchmark content but not yet a completed benchmark result. A formal run requires a configured model provider and the exact pinned Knowledge revision. `run_qa_benchmark.py` fails closed if current Knowledge or the actual Product `ContextManifest.knowledge_revision` differs from the manifest pin. Because Historical Knowledge Read is not yet available, later execution against a different Knowledge revision requires a new suite revision rather than pretending to replay revision 606.

Before spending model calls, validate the world pin and every structured gold EvidenceRef against the local database:

```bash
uv run python -m scripts.validate_qa_manifest \
  benchmarks/qa/real-product-v1.candidate.json
```

Run when the model provider is configured and the database is still at the pinned world:

```bash
uv run python scripts/run_qa_benchmark.py \
  benchmarks/qa/real-product-v1.candidate.json \
  --suite-revision 1 \
  --deployment-revision-id '<deployment-id>' \
  --output /tmp/m6-real-product-v1.json
```

`real-session-v1.candidate.json` is the first real `QASessionCase` candidate. It contains one two-turn Product session pinned to Knowledge revision `606`: turn 1 asks for the NVD CVSS score of `CVE-2026-7273`; turn 2 omits `cve_id/object_id` and asks for the dated FIRST EPSS probability, so correctness requires the Product session to carry the same canonical vulnerability target. Each turn has independent structured-authority gold and EvidenceRefs. Session evaluation reuses the normal per-turn QA scorer, then derives `m6.session_context_chain_correctness` from durable `ContextManifest.parent_context_id` links and `m6.session_target_carry_correctness` from durable session turn target keys.

Validate the two-turn gold without a model call:

```bash
uv run python -m scripts.validate_qa_manifest \
  benchmarks/qa/real-session-v1.candidate.json
```

Run it only with a configured model provider and the same pinned world:

```bash
uv run python scripts/run_qa_benchmark.py \
  benchmarks/qa/real-session-v1.candidate.json \
  --suite-revision 1 \
  --deployment-revision-id '<deployment-id>' \
  --output /tmp/m6-real-session-v1.json
```

This first session denominator measures turn correctness, durable context chaining and canonical target carry. For follow-up `RETRIEVE` turns, the evaluator also derives informational `m6.session_retrieval_overlap_rate` from `document-chunk:*` refs persisted in each turn's ContextManifest: it reports the fraction of the current turn's retrieved chunks that were already exposed by prior turns. This is a factual overlap baseline only. It does not claim a retrieval backend cache hit or prove that an external/vector search invocation was avoided; that requires invocation/cache provenance that the current Product retrieval seam does not yet persist.
