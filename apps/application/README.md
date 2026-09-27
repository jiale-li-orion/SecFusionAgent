# `apps.application`

`apps.application` is the Product Application layer introduced by Technical Design 2A. It owns stable product use-case orchestration and public read models above TD1/TD2 domain runtime. It may compose multiple package owners, but it does not reimplement their invariants.

## Current slice

The first implemented slice is Investigation Product API composition:

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

## Boundaries

Application may depend on `apps` composition modules and TD1/TD2 package ports. No package may import `apps.application`. Product workflow ordering, sync/async choice, request/task trace linkage, pagination and future public idempotency belong here; Evidence/Knowledge, EvidenceNeed transitions, Task state transitions, Policy, Capability and Decision validation remain with their original owners.

The current Product Investigation command does not yet implement public `Idempotency-Key`, cancel/resume, ProductEvent/SSE or AskQuestion routing. Those are TD2A Slice C–E work and should extend these seams rather than re-enter route-level orchestration.

## Verification

```bash
uv run pytest apps/application/tests -q
uv run pytest apps/api/tests/test_product_investigations.py -q
uv run pytest apps/api/tests/test_product_edge.py -q
```
