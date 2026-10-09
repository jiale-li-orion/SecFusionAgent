# `packages.runtime.retrieval`

`packages.runtime.retrieval` owns durable operational provenance for retrieval calls. It does not implement lexical/dense ranking and it does not grant factual authority to retrieved content. Physical retrieval remains in `packages.intelligence.retrieval`; this module records which request coordinate ran, which chunk refs it produced, and whether a later Product turn executed retrieval again or replayed an earlier result set.

## Durable contract

`RetrievalInvocation` records:

- Product request/session/turn identity;
- operator + operator revision;
- query digest and full request digest;
- pinned Knowledge revision;
- result limit and source scope;
- ordered `document-chunk:*` result refs;
- disposition: `executed`, `reused`, or `failed`;
- `reuse_of_invocation_id` when replaying a prior result set;
- start/finish timestamps.

The request digest is derived from the deterministic retrieval coordinate, not from model output. The lexical coordinate is `postgres-simple-tsquery-v1`. Product question fallback for joined Latin names uses a separate `compact_name` coordinate at `ascii-name-whitespace-fold-v1`; it executes only after the original question misses and matches a bounded extracted name. Changing either operator's query semantics/ranking/index interpretation requires a new revision so a prior invocation cannot be silently reused under different semantics.

## Exact reuse policy

The first reuse policy is deliberately narrow. A Product follow-up may reuse prior retrieval results only when all request coordinates match exactly:

```text
same Product session
same normalized query digest
same Knowledge revision
same operator + operator revision
same limit
same source scope
```

The prior ordered chunk refs are then re-read through `LexicalRetrievalOperator.by_chunk_refs`. Reuse is accepted only when every persisted ref still resolves to the exact `DocumentRevision`; otherwise the Product path executes lexical search again and records a new `executed` invocation. Semantic-similarity reuse is intentionally absent because it would change retrieval meaning and could inject stale or irrelevant passages into a follow-up.

`ContextManifest.retrieval_invocation_refs` links Task/Context provenance to these records. QuestionSession does not copy retrieval payloads and Knowledge does not store cache state.

## Failed attempt boundary

Successful Product RETRIEVE calls and exact reuses are durable once the synchronous Question runtime coordinate is committed. If physical lexical search or exact-ref replay fails before Context/TaskRun creation, Application rolls back the provisional command transaction and records a `failed` invocation in a short transaction. The failure row retains the request coordinate, prospective session/turn coordinate, timing and exception class without raw query text or an empty Product session. Failed invocations cannot satisfy future exact reuse. Migration `20261009_0033` adds `failure_class` to the existing durable table. If the database itself is unavailable, attempt persistence may also fail; the original retrieval failure remains the returned error.

## Verification

```bash
uv run pytest apps/application/tests/test_ask_question.py -q
uv run pytest packages/runtime -q
make product-check
make evaluation-check
```
