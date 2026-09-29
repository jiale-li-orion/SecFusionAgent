# M6 QA benchmark assets

`smoke-v1.json` is synthetic harness verification only. It proves the scorer/runtime wiring and must not be used as competition evidence.

`real-product-v1.candidate.json` is the first real Product QA candidate. Its gold is built from exact structured authority facts already materialized in canonical Knowledge, with the backing EvidenceRefs recorded in each case input. It is pinned to Knowledge revision `596` and uses `live_product_question`, so execution must pass through `AskQuestionUseCase → DecisionRole → TaskRun / Budget / Execution → RecordedModelProvider → validated DecisionResult`.

The candidate is intentionally narrow: direct NVD CVSS facts plus CISA KEV cross-source facts. It does not yet claim relation/applicability QA coverage because the current lightweight Product Question projection does not preserve relation qualifiers such as CSAF `state=fixed/not_affected` in a structured form. That projection must be fixed before relation QA enters the formal denominator.

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
