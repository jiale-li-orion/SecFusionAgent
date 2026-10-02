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

ModelAttempt #1..N
  provider / adapter revision / actual model
  provider request id when available
  started / finished / latency
  success or classified failure
  response schema digest
  provider-exact usage when returned
  cache usage when exact
  response-format fallback metadata
```

The logical `ModelRequest` is committed before remote dispatch. Every recorder-level provider attempt is inserted before its provider call and finished in a separate short transaction. Transient transport/HTTP failures therefore remain visible as failed attempt ordinals even when a later retry succeeds; a retry never overwrites the original attempt. One compatibility boundary remains explicit: response-format negotiation currently lives inside `OpenAICompatibleProvider`, so a `json_schema` rejection followed by adapter-local `json_object` fallback is one recorded `ModelAttempt` whose latency covers both HTTP exchanges and whose usage comes from the successful response. Formal physical-HTTP accounting should either freeze a known provider dialect before dispatch or promote that negotiation above the recorder; the current runtime does not pretend the fallback is two persisted attempts.

`ModelRetryPolicy` is configured by `SECFUSION_MODEL_MAX_ATTEMPTS`, `SECFUSION_MODEL_RETRY_BASE_SECONDS`, and `SECFUSION_MODEL_RETRY_MAX_SECONDS`. The default policy retries only failures explicitly classified as transient: network/HTTP transport errors, 408, 429, and selected 5xx responses. `Retry-After` is honored within the configured delay ceiling. Authentication failures, malformed JSON, response-schema violations and ordinary 4xx responses are terminal because replaying the same request cannot repair them. The retry policy is part of `DeploymentRevision` configuration identity, so a latency/quality run cannot silently compare two deployments with different retry behavior.

Interactive M6 adds `model_wall_seconds` to request metadata. `RecordedModelProvider` converts that value into one monotonic logical deadline shared by every physical attempt and retry sleep. An individual HTTP timeout can therefore never silently turn a five-second Product budget into several five-second retries. Deadline exhaustion is persisted as a failed attempt with `timeout_before_response`; retry scheduling is suppressed when the remaining wall budget cannot cover the next backoff. This avoids the more dangerous alternative of cancelling the provider outside the recorder and leaving an attempt permanently in `started` state.

`OpenAICompatibleProvider` exposes `ProviderModelResult` metadata while preserving the legacy `generate_structured()` API. It reports provider request identity, actual model, exact token/cache fields when present, and whether `json_schema` fell back to `json_object`. A 400/422 structured-output fallback does not weaken the response contract: the adapter injects the same Pydantic JSON Schema into the system instruction before retrying in `json_object` mode, and the returned object still passes local schema validation. Missing usage is `unavailable`, never zero. The provider probe also supports OpenAI-compatible `GET /models`: an explicit `SECFUSION_MODEL_NAME` always wins; without it, automatic selection is accepted only when discovery leaves exactly one plausible chat model. Multi-model endpoints fail closed and print candidates rather than choosing a model nondeterministically.

Generation controls are explicit runtime configuration rather than hidden provider defaults. `SECFUSION_MODEL_MAX_TOKENS`, `SECFUSION_MODEL_TEMPERATURE`, and `SECFUSION_MODEL_REASONING_EFFORT` are forwarded to compatible chat endpoints and are part of `DeploymentRevision.configuration_digest` together with timeout/retry policy. A benchmark that changes any of these values is therefore a different deployment coordinate even when the model name is unchanged. Provider-specific semantics still apply; for example, a provider may accept a compatibility field while making it ineffective in a particular reasoning mode.

`PromptAssemblyRecordService` persists M5 PromptAssembly identity and fragment manifest: source refs/revisions, trust/cache classes, content hashes, order, assembly hash and cache hints. Fragment content is deliberately not copied into SQL. `request_artifact_ref` is currently nullable; full redacted request persistence is opt-in and remains an R1 follow-up.

## Ownership boundaries

This package owns physical-attempt retry recording for an already chosen logical model request. It does not alter the prompt, switch to a different model, change Task completion, mutate Knowledge/InvestigationState, select semantic fallback behavior, or promote a Skill. Provider/model selection remains configuration/runtime composition; response-format fallback remains inside the OpenAI-compatible adapter and is recorded in response metadata.

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
make model-provider-probe
make integration-core
```

For a live provider, the minimum common configuration is:

```bash
export SECFUSION_MODEL_BASE_URL='https://provider.example/v1'
export SECFUSION_MODEL_API_KEY='...'
export SECFUSION_MODEL_NAME='chat-model'
export SECFUSION_MODEL_MAX_TOKENS=4096
export SECFUSION_MODEL_REASONING_EFFORT=low
export SECFUSION_MODEL_TEMPERATURE=0
make model-provider-probe
```

If `/models` exposes several chat models, also set `SECFUSION_MODEL_NAME`. A successful probe checks authentication, model resolution, `/chat/completions`, structured JSON output, schema validation, actual-model identity and provider metadata before any formal QA run spends its denominator.

After the probe succeeds, `make qa-live` is the formal measurement entry point. The model name (explicit or uniquely discovered), endpoint digest, timeout and retry policy are included in `DeploymentRevision`; the API key is never persisted in that identity.
