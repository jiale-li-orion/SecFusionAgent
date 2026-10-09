# `packages.intelligence.retrieval`

This package is the controlled M3→M4 read seam over Evidence/Knowledge/Document state. It owns deterministic read operators and candidate construction; it does not own Product sessions, runtime cache policy, Agent planning, or evaluation.

## Operators

The local read surface includes exact, structured, lexical, dense, graph and evidence retrieval. Every operator returns `RetrievedCandidate` with stable object/chunk/relation/evidence identity, revision/time coordinates, source metadata, locator and independent score channels. Retrieval score never upgrades a candidate into confirmed Knowledge.

`LexicalRetrievalOperator.search` uses PostgreSQL `simple` full-text search and returns current document-revision chunks ordered by lexical score then chunk identity. Compact-name and dense search use the same current-revision boundary, so a superseded parser result cannot outrank corrected article text. The query expression is deliberately identical to the migration-owned GIN expression index, `to_tsvector('simple', coalesce(text, ''))`; changing either side requires an execution-plan regression because PostgreSQL does not use an expression index for a semantically similar but structurally different expression. `by_chunk_refs` is the deterministic replay seam for already-selected chunks: it accepts ordered `document-chunk:<chunk_id>@<document_revision_id>` refs, resolves the exact DocumentRevision/Observation/Source rows, and returns candidates in the supplied order, including historical revisions. Missing/stale refs are not repaired or substituted inside this package; callers decide whether to fall back to a new search.

The replay seam exists so runtime/application code can reuse an already-measured retrieval result without duplicating SQL or reconstructing passage payloads from chat/session state. It is not itself a cache and does not decide whether reuse is allowed.

## Ownership boundary

`packages.runtime.retrieval` records operational invocation/reuse provenance. `apps.application` decides the Product workflow and exact-session reuse policy. `packages.evaluation` measures those durable records. This package remains below all three and depends only on the information plane.

## Verification

```bash
uv run pytest packages/intelligence -q
SECFUSION_RUN_INTEGRATION=1 uv run pytest tests/integration/test_core_infrastructure.py -q
```

`DocumentRetrievalOperator.for_object` reads bounded, ordinal-ordered chunks from each document's latest revision for an exact object ID. It preserves source text, revision and locators, and attaches only an existing object EvidenceLink from that revision's Observation. A current revision with no chunks yields no historical fallback. Investigation INSPECT uses this operator alongside structured projections; reading source text does not create Knowledge or bypass the StatePatch evidence gate.
