# Long-Investigation Benchmark

`current-readiness.json` is the machine-readable readiness scan for the live Product Investigation corpus and `current-readiness.md` is its generated projection. `make investigation-readiness` refreshes both. This readiness artifact reports model-provider launch readiness and whether any already-created Product Case can still satisfy the prospective freeze rule; it never creates Cases and never promotes an old Case into the formal denominator.

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
- exact Agent runtime diagnostics such as per-episode timeout rate and Agent wall-clock span;
- when the manifest includes prospectively frozen `AgentRuntimeGold`, only the semantic M5 metrics
  whose denominator is present in that gold/trace (for example trajectory conformance, state target /
  version / EvidenceRef attachment, stop correctness, and unnecessary continuation).

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
- the denominator is frozen more than **300 seconds after Case creation**;
- a final decision already existed at or before `frozen_at`;
- a deadline is not after the freeze;
- one Product Case is duplicated inside the same denominator.

That rule prevents retrospective cherry-picking based on either a known final outcome or visible
intermediate progress. Formal v1 Cases must therefore be added to the manifest immediately after
launch; the five-minute freeze-lag bound is protocol-owned and is not a manifest knob.

Agent semantic gold follows the same rule. Expected targets, admissible version-support relations,
required/forbidden events, stop behavior and continuation expectations must be written into the
manifest before the Agent outcome. If the gold builder is later found incomplete, the historical run
remains immutable evidence of that evaluator failure; the correction is validated on a newly created
prospective Case instead of editing the old manifest after seeing model output.

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

The first real prospective infrastructure denominator is now committed as
`infra-prospective-20261002.json`. It was frozen 0.132 seconds after Product Case creation, before
the InvestigationRole outcome was known, and is deliberately tagged
`infra-prospective-probe / not-competition-score`.

`current-infra-prospective.json` remains the historical failure/recovery probe. Evaluator revisions
kept its original frozen manifest unchanged while progressively exposing the runtime trace. For the
CVE-2026-48746 fix-version case the durable result is:

- final M6 decision present;
- `time_to_first_status = 0.010692s`;
- `time_to_final_decision = 941.410856s`;
- four InvestigationRole episodes: three failed, zero timed out, one completed;
- Agent wall span from first episode creation to final terminal episode = `881.554909s`;
- zero open EvidenceNeeds at measurement;
- frozen 300-second deadline missed, so `agent.task_success = 0` even though eventual final-decision completion is `1`.

The three failed episodes are preserved as evaluation evidence rather than hidden. The first exposed
a `PromptAssemblyRecord.task_contract_id` storage-width bug; the next two exposed model→M4 state
integration constraints before the fourth episode produced an accepted deterministic Evidence-backed
StatePatch. This probe therefore demonstrates the measurement substrate and failure-chain visibility,
but it is not promoted into the competition score.

The current clean infrastructure baseline is
`current-harness-fixed-prospective.json`, generated by
`scripts/run_prospective_investigation_probe.py`. It launches a real Product Investigation through
`StartInvestigationUseCase`, freezes the denominator before outcome, executes the production
InvestigationRole, then invokes the real M6 Decision owner and finally audits the resulting
BenchmarkRun with the same trace/Evidence closure checker used elsewhere. The latest clean run is
`m6-long-investigation-harness-fixed-20261003@2` / BenchmarkRun
`21249f0f-80e5-4d53-a191-c8ca16e1ecd4`:

- freeze lag remained inside the five-minute prospective rule;
- `time_to_first_status = 0.008871s`;
- one InvestigationRole episode completed in `10.948533s` with no failed or timed-out episode;
- final M6 DecisionCommit arrived at `12.237316s` from Case creation;
- the 300-second deadline was met, so `agent.task_success = 1`;
- M5 planner and M6 decision model requests both persisted request/response RuntimeArtifacts;
- benchmark trace audit resolved 2 TaskRuns, 2 ExecutionRuns, 2 ModelRequests/Attempts,
  1 PromptAssemblyRecord, 4 RuntimeArtifacts, 1 Decision and the supporting Evidence chain with
  `closure=true`.

This clean baseline supersedes the 941-second recovery probe as the current infrastructure behavior;
the older run remains immutable evidence of the failure/recovery path. Future competition-facing
denominators should be launched with the same prospective harness after deployment/model/policy
coordinates are frozen, never by reclassifying these infrastructure probes as competition scores.

The prospective harness can additionally freeze a manually declared `--expected-fixed-version`.
Before the model runs, it resolves the current Knowledge world into a **typed version-support gold**:

- canonical `fixed-version` edges whose target is the expected version;
- package/applicability relations whose `first_patched_version` equals the expected version;
- affected/applicability ranges with a strict upper bound `< expected_version`;
- active same-target Claims that explicitly state the vulnerability is fixed/patched in the expected
  version.

The frozen relation and claim refs become the admissible support set for M5 state-integration
scoring. At measurement time the evaluator consumes only that frozen set; it never expands gold from
the Agent's eventual reasoning output or from a newer Knowledge world. A version-scoped assertion is
evaluable only when the Agent actually emits a reasoning relation. If it writes a direct
Evidence-backed fact with `reasoning_relation=null`, `agent.wrong_version_attachment_rate` remains
`NOT_EVALUATED` rather than being recorded as a vacuous zero.

`agent.wrong_version_attachment_rate` is currently MetricDefinition revision 2 because the earlier
relation-only denominator was proven incomplete by real prospective runs. Historical revision-1
observations remain immutable evaluator-evolution evidence; they do not satisfy current-revision
readiness. The files named `agent-semantics-*` preserve those prospective evaluator experiments and
must not be cherry-picked into competition scoring. `current-harness-fixed-prospective.json` remains
the clean Long-Investigation infrastructure baseline; the semantic probes are tagged
`not-competition-score` and exist to validate the measurement contract itself.
