# `packages.runtime.model`

TD3 model-execution measurement owner. This package records what happened around a logical model decision without taking over the online decision itself.

## Current implementation

`RecordedModelProvider` wraps an existing `ModelProvider`. For each structured generation call it persists:

```text
ModelRequest
  purpose / owner / prompt revision
  optional execution / task / case / processing-run / PromptAssembly coordinate
  request schema digest / normalized request digest
  requested model / budget ref

ModelAttempt #1
  provider / adapter revision / actual model
  provider request id when available
  started / finished / latency
  success or classified failure
  response schema digest
  provider-exact usage when returned
  cache usage when exact
  response-format fallback metadata
```

The request/attempt rows are committed before remote dispatch. The provider call runs outside the recorder database transaction. A second short transaction records success/failure. Failed attempts remain durable; a later success cannot overwrite them.

`OpenAICompatibleProvider` exposes `ProviderModelResult` metadata while preserving the legacy `generate_structured()` API. It reports provider request identity, actual model, exact token/cache fields when present, and whether `json_schema` fell back to `json_object`. Missing usage is `unavailable`, never zero.

`PromptAssemblyRecordService` persists M5 PromptAssembly identity and fragment manifest: source refs/revisions, trust/cache classes, content hashes, order, assembly hash and cache hints. Fragment content is deliberately not copied into SQL. `request_artifact_ref` is currently nullable; full redacted request persistence is opt-in and remains an R1 follow-up.

## Ownership boundaries

This package may observe model requests and persist execution facts. It does not choose retries, change Task completion, mutate Knowledge/InvestigationState, select a model fallback policy, or promote a Skill. Online owners retain those decisions.

Payload artifacts are privacy-sensitive. `RecordedModelProvider` only writes request/response RuntimeArtifacts when an artifact service is explicitly provided, an `execution_id` exists, and request metadata opts into `redacted_runtime_artifact`. The default online path records coordinate/digests/usage without copying prompt content.

Budget settlement is not yet complete. Exact provider usage is now available as a measurement source, but `BudgetGovernor` model-token/external-cost/retry settlement remains a TD3 Slice A follow-up.

## Current call-site coverage

- M3 document semantic extraction: `m3.semantic_extract`
- M3 normative extraction: `m3.normative_extract`
- M5 Investigation planner: `m5.investigation_plan`
- M6 Decision planner: `m6.decision`

M5 additionally persists `PromptAssemblyRecord`. M6 Workbench execution now uses staged read → remote model → guarded M4 write, so the remote call does not keep its read transaction open.

## Verification

```bash
uv run pytest packages/runtime/model/tests -q
uv run pytest packages/investigation/runtime/test_model_planner.py -q
make integration-core
```
