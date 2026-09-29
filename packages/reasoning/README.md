# `packages.reasoning`

`packages.reasoning` owns M6 Decision/QA contracts, model proposal normalization and validation. It consumes already-materialized M4 `InvestigationState`; it does not query Evidence/Knowledge storage directly, invoke external tools, or mutate Case state.

`DecisionService` finalizes typed fact/inference/recommendation conclusions against the exact Case revision. A fact conclusion must reproduce one confirmed M4 proposition exactly and cite evidence attached to that same state item; combining or paraphrasing state into a new proposition is an inference, not a fact. Inference conclusions may cite evidence present in M4 state and preserve intermediate `reasoning_relation_refs`. `CitationBinder` requires an explicit EvidenceRef→source/locator input from the caller; missing citation material fails rather than being synthesized.

`ModelDecisionPlanner` receives only the supplied M4 state plus caller-provided citation source metadata. It can propose a typed final decision or a typed continuation; Case identity/revision are always overwritten from the current M4 state rather than trusted from model output. Final proposals still pass `DecisionService` before `apps.decision_runtime` calls the M4-owned `DecisionCommit` event gate.

`ModelDecisionPlanner` also accepts caller-supplied runtime coordinates for recording (`task_run_id`, `execution_id`, `budget_ref`, request owner). These coordinates affect provenance only; they do not enter decision semantics. Product DIRECT/RETRIEVE uses this seam so RecordedModelProvider can bind interactive M6 calls to the real TaskRun/Execution while leaving the synthetic lightweight question state out of the durable Case foreign key.

Validated decisions are additionally written to immutable `DecisionResultStore`. This does not replace M4 `current_decision`: M4 still decides which result is current for a durable Case. The M6 store gives every validated result a stable `decision_id` read identity, including synchronous Product decisions that intentionally have no durable Case.

When evidence is insufficient, M6 emits `ContinuationRequest`. The request contract is owned by the M4 receiving boundary under `packages.investigation.state.continuation`; M6 can validate and return it but cannot create `EvidenceNeed` itself. App composition first wraps the request as a `TaskIntent`, then `ContinuationGate` performs target/revision validation, deterministic semantic dedupe, and the actual EvidenceNeed write. This preserves the TD2 `ContinuationRequest → TaskIntent → M4` authority path without giving M6 storage authority.

## Design → implementation map

TD2 的 M6 pipeline 已经落成 `ModelDecisionPlanner → DecisionDraft | ContinuationRequest → DecisionService → M4-owned gate`。`decision.py` 持有 conclusion typing 与 evidence/reasoning validation；`citation.py` 只把既有 EvidenceRef 绑定到显式 source/locator；`model.py` 只是 structured proposal generator；`storage.py` 只持久化已经验证的 immutable DecisionResult。`apps.decision_runtime` 是最终 composition boundary：final 走 `DecisionCommit` 并登记 M6 result，continuation 走 M4 `ContinuationGate`。

Runtime Workbench 与 Product AskQuestion 都调用这条 M6 runtime/invariant。当前剩余比赛层工作是 human-adjudicated real QA content、session/follow-up binding 与 live Product benchmark closure，而不是另一套 chat-only reasoning engine。
