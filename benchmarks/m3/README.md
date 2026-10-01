# M3 enrichment evidence

This directory stores the reviewed current projection of formal M3 evidence. Scoring remains owned by
the executable evaluators and durable Benchmark Runtime; files here make the selected provider world
and scorer output inspectable in code review.

`provider_snapshots/structured-20261001T151331Z.json` is the raw provider world frozen before the
current structured replay. `current-structured.json` scores canonical Knowledge against that frozen
world. Provider refreshes may update Knowledge before replay, but replay never re-fetches or edits the
gold snapshot. `current-csaf-vex.json` independently rebuilds Red Hat CSAF/VEX gold from persisted raw
EvidenceArtifact bytes and filters predictions to that source-specific evidence universe.

Point-in-time providers require explicit temporal handling. FIRST EPSS claims carry `score_date` and
are refreshed before replay when the frozen provider world advances. GitHub Advisory EPSS fields are
provider-current values; if GitHub is rate-limited after the world is frozen, the resulting mismatch
remains in the formal score instead of moving the gold denominator to chase the latest API response.

Current run IDs, aggregate TP/FP/FN and competition target status are presented by
`../competition/current.json` and its generated Markdown projection. This README documents ownership
and replay semantics only, so metric changes do not require hand-editing explanatory prose.
