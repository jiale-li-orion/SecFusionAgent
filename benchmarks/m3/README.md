# M3 enrichment evidence

This directory stores the reviewed current projection of formal M3 evidence. Scoring remains owned by
the executable evaluators and durable Benchmark Runtime; files here make the selected provider world
and scorer output inspectable in code review.

`provider_snapshots/structured-20261001T151331Z.json` is the raw provider world frozen before the
current structured replay. Structured replay is dual-frozen: provider bytes define gold, while the
prediction side resolves the latest `KnowledgeRevision` committed at or before the snapshot's
`fetched_at` and reads Objects/Claims/Relations as visible at that revision. Later ingestion therefore
cannot improve an older replay retroactively. `current-structured.json` records both
`provider_snapshot_revision` and `prediction_world_ref=knowledge-revision:<n>`.

`current-csaf-vex.json` independently rebuilds Red Hat CSAF/VEX gold from persisted raw
EvidenceArtifact bytes and filters predictions to that source-specific evidence universe. Its
prediction world is frozen at the maximum KnowledgeRevision caused by the exact persisted Red Hat
Observations selected for the cases, so later source refreshes cannot alter an older CSAF/VEX replay.

Point-in-time providers require explicit temporal handling. FIRST EPSS claims carry `score_date` and
are refreshed before replay when the frozen provider world advances. GitHub Advisory EPSS fields are
provider-current values; if GitHub is rate-limited after the world is frozen, the resulting mismatch
remains in the formal score instead of moving the gold denominator to chase the latest API response.

Current run IDs, aggregate TP/FP/FN and competition target status are presented by
`../competition/current.json` and its generated Markdown projection. This README documents ownership
and replay semantics only, so metric changes do not require hand-editing explanatory prose.
