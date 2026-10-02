# Lexical retrieval execution benchmark

Run `8fa4d0b8-06ef-4a69-9db2-e5855c406c9f` on `deployment:e2580a560cbf864df9a9548b93d15f78` / `knowledge-revision:1589`. This is a diagnostic M6 retrieval benchmark, not a direct competition target.

Required PostgreSQL expression index: `ix_document_chunks_fts_simple`.

| Query | Execution | Index used | Observed indexes |
| --- | ---: | ---: | --- |
| `CVE 2026` | 77.744 ms | yes | `ix_document_chunks_fts_simple`, `sources_pkey` |
| `vulnerability` | 100.376 ms | yes | `ix_document_chunks_fts_simple`, `sources_pkey` |
| `security` | 313.804 ms | yes | `ix_document_chunks_fts_simple` |
| `patch` | 32.690 ms | yes | `ix_document_chunks_fts_simple`, `documents_pkey`, `observations_pkey`, `sources_pkey` |

Index-plan coverage: **4/4**. Latency range: **32.690-313.804 ms**.

The runner uses the same `to_tsvector('simple', coalesce(text, ''))` predicate as `LexicalRetrievalOperator` and the migration-owned GIN expression index. A future query-expression drift therefore becomes a measurable `retrieval.lexical_index_used` regression instead of a hidden sequential scan.
