# M6 QA benchmark assets

`smoke-v1.json` is synthetic harness verification only. It proves the scorer/runtime wiring and must not be used as competition evidence.

`real-product-v1.candidate.json` is the first real Product QA candidate. Its gold is built from exact structured authority facts already materialized in canonical Knowledge, with backing source IDs and EvidenceRefs bound through `gold_provenance`. It is pinned to Knowledge revision `596` and uses `live_product_question`, so execution must pass through `AskQuestionUseCase → DecisionRole → TaskRun / Budget / Execution → RecordedModelProvider → validated DecisionResult`.

The candidate currently contains 12 cases: direct NVD CVSS facts, NVD + CISA KEV cross-source facts, one dated FIRST EPSS temporal fact, one CVE Record Format 5.x version-range applicability fact, and Red Hat CSAF/VEX `not_affected`/`fixed` applicability facts. Product Question facts use shared deterministic renderers: ordinary claims stay compact, FIRST EPSS retains `source_semantics + score_date`, and relation facts retain semantic qualifiers (`state`, version/scope, CSAF status, compact component/platform context and justification) while dropping provenance-only fields and bulky NVD root snapshots. The same renderers are used by structured-gold preflight, preventing Product context and benchmark fact strings from drifting independently.

The file is real benchmark content but not yet a completed benchmark result. A formal run requires a configured model provider and the exact pinned Knowledge revision. `run_qa_benchmark.py` fails closed if current Knowledge or the actual Product `ContextManifest.knowledge_revision` differs from the manifest pin. Because Historical Knowledge Read is not yet available, later execution against a different Knowledge revision requires a new suite revision rather than pretending to replay revision 596.

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
