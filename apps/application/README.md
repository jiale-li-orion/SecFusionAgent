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

`commands/start_investigation.py` owns the product workflow order. `InvestigationTaskLauncher` is the reusable seam for creating a policy-admitted InvestigationRole Task on an existing Case; the Runtime Workbench now reuses this launcher instead of maintaining a parallel copy of admission/budget/execution wiring.

`queries/investigations.py` owns the Product read projection. It reads M4 state plus the latest Task/Execution coordinate and maps them into `InvestigationView`; Product clients do not receive `TaskContract`, `ContextManifest`, `PolicyDecision`, `BudgetAccount`, or raw TaskEvent schema. List queries use an opaque cursor and bounded page size.

`views/` contains stable Product DTO/read-model types. These are application contracts, not ORM models and not domain authority.

TD2A Slice C now adds the Product QA routing seam:

```text
POST /api/v1/questions
→ TaskIntent / shared Task admission
→ LOOKUP / RETRIEVE: DecisionRole + lightweight evidence context + M6
   → validated DecisionResult → immutable M6 result store → 200
   → ContinuationRequest → StartInvestigationUseCase → 202
→ VERIFY / INVESTIGATE / WATCH: StartInvestigationUseCase → 202
```

`commands/ask_question.py` does not infer a TaskKind with ad-hoc route logic. The caller supplies the normalized kind, shared task admission compiles the corresponding contract, and `DecisionRole` owns the read-only synchronous TaskRun. LOOKUP binds accepted M3 claims/relations back to stable EvidenceRefs before M6. Bounded RETRIEVE may add retrieved passages as tentative context; it does not promote a passage into a confirmed fact. M6 continuation is validated against the current lightweight state before it may open a durable Investigation.

Product Question sessions are Application-owned coordination, not a second reasoning state. `QuestionSessionStore` persists turn order, user input, carried canonical target IDs, world/context coordinates and stable `decision_ref` / `investigation_ref`; it does not copy Decision, Evidence or M4 state payloads. A follow-up may omit an explicit target when the previous turn carries exactly one durable object. The previous `ContextManifest.context_id` becomes the next turn's `parent_context_id`. Prior Decision content is re-read from the immutable M6 result store and sent to M6 only as `session_context` for co-reference and intent resolution; the planner instruction explicitly forbids treating that history as evidence or current truth. Current facts must still be reproduced from the new turn's current `InvestigationState` and pass the normal citation gate.

RETRIEVE follow-up reuse is now explicit and bounded. Each Product RETRIEVE writes a durable `RetrievalInvocation` and places its ref in `ContextManifest.retrieval_invocation_refs`. Before issuing lexical search, `AskQuestionUseCase` checks the same Product session for a prior invocation with the exact request digest: normalized query, Knowledge revision, lexical operator revision, result limit and source scope must all match. On a match, the prior ordered `document-chunk:*` refs are re-read from the information plane; only a complete exact ref replay is marked `reused` and allowed to skip lexical search. Any missing/stale ref falls back to a normal search. Different wording or a different world revision never reuses merely because it is semantically similar.

Every synchronous Question still creates TaskRun / Budget / Execution coordinates. Recorded model requests receive the real `task_run_id`, `execution_id` and `budget_ref`; the synthetic lightweight `question:*` state identity is deliberately not written into the durable Case foreign key. This preserves the TD3 live-latency/provenance chain without creating a fake Investigation Case.

Validated M6 results are persisted immutably by `DecisionResultStore`. M4 remains the owner of which decision is current for a durable Case; the result store only supplies stable DecisionResult identity, including DIRECT/RETRIEVE results that have no Case. `GET /api/v1/decisions/{decision_id}` reads this store and retains a compatibility read from historical M4 DecisionCommit events.

## Boundaries

Application may depend on `apps` composition modules and TD1/TD2 package ports. No package may import `apps.application`. Product workflow ordering, sync/async choice, request/task trace linkage, pagination and future public idempotency belong here; Evidence/Knowledge, EvidenceNeed transitions, Task state transitions, Policy, Capability and Decision validation remain with their original owners.

The current Product layer still does not implement public `Idempotency-Key`, cancel/resume or ProductEvent/SSE. Generic RETRIEVE continuation binds only canonical object identities returned by retrieval; chunk IDs and URLs never become Case identity. Multi-turn Product follow-up, session evaluation, durable retrieval invocation provenance and exact-query result reuse are implemented. Still open: semantic/non-identical-query reuse (intentionally deferred), independently durable failed retrieval attempts, and follow-up over an already-active durable Investigation. These later TD2A/TD3 slices should extend the current session/invocation refs rather than create a chat-only reasoning engine.

## Verification

```bash
uv run pytest apps/application/tests -q
uv run pytest apps/api/tests/test_product_investigations.py -q
uv run pytest apps/api/tests/test_product_questions.py -q
uv run pytest apps/api/tests/test_product_edge.py -q
make product-check
```
