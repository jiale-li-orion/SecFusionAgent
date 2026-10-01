# Long-Investigation Benchmark

This directory owns the **prospectively frozen** denominator for Product Investigation completion. It is deliberately separate from interactive QA latency: `202 Accepted` only means the Product accepted a durable Investigation; it is not a final answer and is never used as `time_to_final_decision`.

## What is measured

`scripts/run_investigation_benchmark.py` reads an already-created durable Product Case and derives one `InvestigationCompletionTrace` from existing owners:

- `InvestigationCase.created_at` — start of the long Investigation clock;
- the latest M4 `DECISION_CHANGED` / `DecisionCommit` event — final-decision timestamp and stable decision ref;
- InvestigationRole `TaskRun`s — episode count and terminal/active episode diagnostics;
- `EvidenceNeed` state — unresolved need count at measurement time.

The runner records:

- `agent.task_success` — whether the frozen expected final-decision behavior was satisfied within the declared measurement deadline;
- `m6.investigation_final_decision_completion` — whether a durable final M6 decision exists, independent of deadline;
- `m6.investigation_time_to_final_decision_seconds` — Case creation → accepted M4 DecisionCommit event;
- `m6.investigation_role_episode_count` — number of InvestigationRole episodes attached to the same Case;
- `m6.investigation_open_need_count_at_measurement` — unresolved/blocked EvidenceNeeds when measured.

If a final decision arrives after the deadline, final-decision completion remains `1` and the actual TTFD is retained, while `agent.task_success` becomes `0`. This keeps eventual completion separate from bounded task success.

## Prospective freeze rule

Formal competition evidence must freeze the denominator **before the outcome is known**. A manifest therefore includes one top-level `frozen_at` and, for every Product Case, a `measurement_deadline`.

Example shape:

```json
{
  "suite_id": "m6-long-investigation-real",
  "purpose": "Prospectively frozen real Product Investigation cases",
  "evaluator_revision": "investigation-completion-v1",
  "frozen_at": "2026-10-01T16:00:00+08:00",
  "cases": [
    {
      "case_id": "investigation-real-001",
      "product_case_id": "<durable-case-id>",
      "expected_final_decision": true,
      "measurement_deadline": "2026-10-01T18:00:00+08:00",
      "tags": ["real", "competition-candidate"]
    }
  ]
}
```

The runner fails closed when:

- the Product Case was created after `frozen_at`;
- a final decision already existed at or before `frozen_at`;
- a deadline is not after the freeze;
- one Product Case is duplicated inside the same denominator.

That rule prevents retrospective cherry-picking of successful Cases.

## Preflight while Cases are still running

Before outcomes are available, validate that the denominator is legally frozen without producing a BenchmarkRun:

```bash
uv run python scripts/run_investigation_benchmark.py \
  /path/to/long-investigation-manifest.json \
  --suite-revision 1 \
  --preflight-only
```

An unfinished Case before its deadline is reported as `pending`. It is **not** converted into a zero score.

## Formal measurement

Once every Case either has a final decision or has passed its deadline:

```bash
uv run python scripts/run_investigation_benchmark.py \
  /path/to/long-investigation-manifest.json \
  --suite-revision 1 \
  --deployment-revision-id '<deployment-id>' \
  --output /tmp/m6-long-investigation.json
```

The runner registers immutable `BenchmarkCase` / `BenchmarkSuite` rows, records metric observations through TD3 `BenchmarkStore`, and finishes one `LIVE_CONTROLLED` BenchmarkRun. A benchmark case run being `PASSED` means measurement execution succeeded; Agent success/failure lives in `agent.task_success` and the other metrics rather than being conflated with evaluator runtime health.

## Current evidence boundary

No bundled real manifest is committed here yet. The local environment currently has no configured model provider, so creating a new real Agent Investigation denominator would produce infrastructure-shaped Cases rather than credible competition evidence. The first real manifest should be frozen immediately after real Cases are launched and before their final outcomes are visible.
