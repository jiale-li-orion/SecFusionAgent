# `apps.application`

`apps.application` is the Product Application layer introduced by Technical Design 2A. It owns stable product use-case orchestration and public read models above TD1/TD2 domain runtime. It may compose multiple package owners, but it does not reimplement their invariants.

## Current slices

Investigation Product API composition remains the durable async path:

```text
HTTP Product Route
→ StartInvestigationUseCase
→ target resolution
→ CaseService / InvestigationStateService
→ TaskIntent / shared Task admission
→ ContextManifest / Budget / ExecutionEnvelope / TaskRun
→ queue transition
→ InvestigationQueries
→ InvestigationView
```

`commands/start_investigation.py` owns the product workflow order. `InvestigationTaskLauncher` is the reusable seam for creating a policy-admitted InvestigationRole Task on an existing Case; the Runtime Workbench now reuses this launcher instead of maintaining a parallel copy of admission/budget/execution wiring. `ContinueInvestigationUseCase` composes the same owners for Product session follow-up: it reuses an existing `active/waiting` Case, opens a new EvidenceNeed at the current Case revision, launches a fresh InvestigationRole episode and keeps the Case identity stable.

`queries/investigations.py` owns the Product read projection. It reads M4 state plus the latest Task/Execution coordinate and maps them into `InvestigationView`; Product clients do not receive `TaskContract`, `ContextManifest`, `PolicyDecision`, `BudgetAccount`, or raw TaskEvent schema. List queries use an opaque cursor and bounded page size.

`views/` contains stable Product DTO/read-model types. These are application contracts, not ORM models and not domain authority.

TD2A Slice C now adds the Product QA routing seam:

```text
POST /api/v1/questions
→ TaskIntent / shared Task admission
→ LOOKUP / RETRIEVE: DecisionRole + lightweight evidence context + M6
   → session active-Case read: DecisionRole + live M4 InvestigationState + M6
   → validated DecisionResult → immutable M6 result store → 200
   → ContinuationRequest → StartInvestigationUseCase → 202
→ VERIFY / INVESTIGATE / WATCH: StartInvestigationUseCase → 202
```

`commands/ask_question.py` does not infer a TaskKind with ad-hoc route logic. The caller supplies the normalized kind, shared task admission compiles the corresponding contract, and `DecisionRole` owns the read-only synchronous TaskRun. LOOKUP binds accepted M3 claims/relations back to stable EvidenceRefs before M6. Bounded RETRIEVE may add retrieved passages as tentative context; it does not promote a passage into a confirmed fact. M6 continuation is validated against the current lightweight state before it may open a durable Investigation.

Product Question sessions are Application-owned coordination, not a second reasoning state. `QuestionSessionStore` persists turn order, user input, carried canonical target IDs, world/context coordinates and stable `decision_ref` / `investigation_ref`; it does not copy Decision, Evidence or M4 state payloads. A follow-up may omit an explicit target when the previous turn carries exactly one durable object. The previous `ContextManifest.context_id` becomes the next turn's `parent_context_id`. Prior Decision content is re-read from the immutable M6 result store and sent to M6 only as `session_context` for co-reference and intent resolution; the planner instruction explicitly forbids treating that history as evidence or current truth. Current facts must still be reproduced from the new turn's current `InvestigationState` and pass the normal citation gate.

Investigation-class follow-up now binds to the most recent durable `investigation_ref` in the Product session when that Case is still `active/waiting`. The user does not rebind `cve_id/object_id` on that path: the Case owns its target set. Product checks for a non-terminal InvestigationRole TaskRun before mutating M4; if one exists, the follow-up fails with a lifecycle conflict and does not create an orphan EvidenceNeed. Once the prior episode is terminal, the next follow-up appends a new EvidenceNeed and launches the next TaskRun on the same Case. Resolved/cancelled/closed Cases are not silently reopened; normal target carry may create a new Case instead.

Read-only LOOKUP/RETRIEVE can now explicitly read that live Case as well. The Case-read profile is selected only when the Product session has an `active/waiting` investigation, the new question omits `cve_id/object_id`, and the TaskKind is LOOKUP/RETRIEVE. Product materializes the durable M4 `InvestigationState` into an ephemeral DecisionRole input, preserves the real `case_ref` and `investigation_state_ref` in ContextManifest, binds TaskRun/ModelRequest to the real Case, and changes only the ephemeral `goal` to the current user question. A Case-read DecisionResult is immutable Product output; it does not commit `M4.current_decision`. M4 StatePatch evidence IDs remain durable owner-local IDs; the Product projection canonicalizes them to `evidence:<id>` only in the read context so the normal M6 citation gate can resolve them without rewriting M4 state.

Case-read RETRIEVE additionally requires the M4 state's `last_world_revision` to equal the current Knowledge revision. Product refuses to mix fresh retrieval passages with a stale InvestigationState; the Investigation episode must refresh/rebase first. Explicit `cve_id/object_id` on a LOOKUP/RETRIEVE bypasses Case-read and starts a normal lightweight Question profile, so an old session Case cannot silently hijack an explicitly rebound read.

RETRIEVE follow-up reuse is now explicit and bounded. Each Product RETRIEVE writes a durable `RetrievalInvocation` and places its ref in `ContextManifest.retrieval_invocation_refs`. Before issuing lexical search, `AskQuestionUseCase` checks the same Product session for a prior invocation with the exact request digest: normalized query, Knowledge revision, lexical operator revision, result limit and source scope must all match. On a match, the prior ordered `document-chunk:*` refs are re-read from the information plane; only a complete exact ref replay is marked `reused` and allowed to skip lexical search. Any missing/stale ref falls back to a normal search. Different wording or a different world revision never reuses merely because it is semantically similar.

Every synchronous Question still creates TaskRun / Budget / Execution coordinates. Ordinary lightweight questions keep the synthetic `question:*` state out of the durable Case foreign key. Explicit session Case-read questions instead bind the DecisionRole TaskRun, ContextManifest and recorded ModelRequest to the real M4 Case. This preserves the TD3 live-latency/provenance chain without creating a fake Case and makes read activity discoverable from the real Case timeline.

Validated M6 results are persisted immutably by `DecisionResultStore`. M4 remains the owner of which decision is current for a durable Case; the result store only supplies stable DecisionResult identity, including DIRECT/RETRIEVE results that have no Case. `GET /api/v1/decisions/{decision_id}` reads this store and retains a compatibility read from historical M4 DecisionCommit events.

## Boundaries

Application may depend on `apps` composition modules and TD1/TD2 package ports. No package may import `apps.application`. Product workflow ordering, sync/async choice, request/task trace linkage, pagination and future public idempotency belong here; Evidence/Knowledge, EvidenceNeed transitions, Task state transitions, Policy, Capability and Decision validation remain with their original owners.

The current Product layer still does not implement public `Idempotency-Key`, cancel/resume or ProductEvent/SSE. Generic RETRIEVE continuation binds only canonical object identities returned by retrieval; chunk IDs and URLs never become Case identity. Multi-turn Product follow-up, serialized Investigation-class follow-up on the same durable Case, explicit live-M4 Case-read, session evaluation, durable retrieval invocation provenance and exact-query result reuse are implemented. Still open: semantic/non-identical-query reuse (intentionally deferred), independently durable failed retrieval attempts, a frozen evaluation denominator for live Case-read sessions, and long-running Investigation completion measurement. These later TD2A/TD3 slices should extend the current session/Case/invocation refs rather than create a chat-only reasoning engine.

## Verification

```bash
uv run pytest apps/application/tests -q
uv run pytest apps/api/tests/test_product_investigations.py -q
uv run pytest apps/api/tests/test_product_questions.py -q
uv run pytest apps/api/tests/test_product_edge.py -q
make product-check
```
