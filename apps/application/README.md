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

Every synchronous Question still creates TaskRun / Budget / Execution coordinates. Recorded model requests receive the real `task_run_id`, `execution_id` and `budget_ref`; the synthetic lightweight `question:*` state identity is deliberately not written into the durable Case foreign key. This preserves the TD3 live-latency/provenance chain without creating a fake Investigation Case.

Validated M6 results are persisted immutably by `DecisionResultStore`. M4 remains the owner of which decision is current for a durable Case; the result store only supplies stable DecisionResult identity, including DIRECT/RETRIEVE results that have no Case. `GET /api/v1/decisions/{decision_id}` reads this store and retains a compatibility read from historical M4 DecisionCommit events.

## Boundaries

Application may depend on `apps` composition modules and TD1/TD2 package ports. No package may import `apps.application`. Product workflow ordering, sync/async choice, request/task trace linkage, pagination and future public idempotency belong here; Evidence/Knowledge, EvidenceNeed transitions, Task state transitions, Policy, Capability and Decision validation remain with their original owners.

The current Product layer still does not implement public `Idempotency-Key`, cancel/resume or ProductEvent/SSE. Generic RETRIEVE can answer synchronously without a bound target, but a ContinuationRequest cannot yet open a durable Investigation until target resolution has produced a stable object identity. Multi-turn/session QA also remains open. These are later TD2A lifecycle/session slices and should extend the current seams rather than re-enter route-level orchestration.

## Verification

```bash
uv run pytest apps/application/tests -q
uv run pytest apps/api/tests/test_product_investigations.py -q
uv run pytest apps/api/tests/test_product_questions.py -q
uv run pytest apps/api/tests/test_product_edge.py -q
make product-check
```
