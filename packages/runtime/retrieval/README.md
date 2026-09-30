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
- disposition: `executed` or `reused`;
- `reuse_of_invocation_id` when replaying a prior result set;
- start/finish timestamps.

The request digest is derived from the deterministic retrieval coordinate, not from model output. The current lexical coordinate is `postgres-simple-tsquery-v1`; changing query semantics/ranking/index interpretation requires a new operator revision so a previous invocation cannot be silently reused under different semantics.

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

## Current failure boundary

Successful Product RETRIEVE calls and exact reuses are durable once the synchronous Question runtime coordinate is committed. A retrieval failure that occurs before Context/TaskRun creation is not yet independently committed as a failed invocation; adding failed-attempt durability requires an independent short-transaction recorder similar to ModelAttempt and must not create an otherwise-empty Product session as a side effect.

## Verification

```bash
uv run pytest apps/application/tests/test_ask_question.py -q
uv run pytest packages/runtime -q
make product-check
make evaluation-check
```
