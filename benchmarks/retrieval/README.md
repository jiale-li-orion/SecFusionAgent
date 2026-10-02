# Retrieval execution benchmark

This directory owns diagnostic retrieval execution evidence used to explain and regress M6 QA latency. It is deliberately separate from the competition target checks: a fast index plan cannot substitute for QA accuracy, grounding, citation quality or the `<=5s` Product latency target.

The v1 runner executes fixed lexical queries against the real PostgreSQL document corpus with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. It records `retrieval.lexical_latency_ms` and `retrieval.lexical_index_used` as TD3 `MetricObservation` rows under a durable `BenchmarkRun`. The required physical plan uses `ix_document_chunks_fts_simple`, whose expression must remain identical to `LexicalRetrievalOperator.search`.

`current.json` is the machine-readable reviewed pointer and `current.md` is generated from it. The benchmark is useful for regression and diagnosis; relevance/recall remains a separate future denominator with explicit retrieval gold.
