# `packages.reasoning`

`packages.reasoning` owns M6 Decision/QA contracts, model proposal normalization and validation. It consumes already-materialized M4 `InvestigationState`; it does not query Evidence/Knowledge storage directly, invoke external tools, or mutate Case state.

`DecisionService` finalizes typed fact/inference/recommendation conclusions against the exact Case revision. Fact conclusions may cite only evidence already attached to confirmed M4 state. Inference conclusions may cite evidence present in M4 state and preserve intermediate `reasoning_relation_refs`. `CitationBinder` requires an explicit EvidenceRef→source/locator input from the caller; missing citation material fails rather than being synthesized.

`ModelDecisionPlanner` receives only the supplied M4 state plus caller-provided citation source metadata. It can propose a typed final decision or a typed continuation; Case identity/revision are always overwritten from the current M4 state rather than trusted from model output. Final proposals still pass `DecisionService` before `apps.decision_runtime` calls the M4-owned `DecisionCommit` event gate.

When evidence is insufficient, M6 emits `ContinuationRequest`. The request contract is owned by the M4 receiving boundary under `packages.investigation.state.continuation`; M6 can validate and return it but cannot create `EvidenceNeed` itself. App composition first wraps the request as a `TaskIntent`, then `ContinuationGate` performs target/revision validation, deterministic semantic dedupe, and the actual EvidenceNeed write. This preserves the TD2 `ContinuationRequest → TaskIntent → M4` authority path without giving M6 storage authority.

## Design → implementation map

TD2 的 M6 pipeline 已经落成 `ModelDecisionPlanner → DecisionDraft | ContinuationRequest → DecisionService → M4-owned gate`。`decision.py` 持有 conclusion typing 与 evidence/reasoning validation；`citation.py` 只把既有 EvidenceRef 绑定到显式 source/locator；`model.py` 只是 structured proposal generator。`apps.decision_runtime` 是最终 composition boundary：final 走 `DecisionCommit`，continuation 走 M4 `ContinuationGate`。

Runtime Workbench 暴露的 M6 测试入口调用的就是这条 runtime：citation metadata 从持久化 EvidenceLink/Observation 解析，然后执行 `DecisionRuntime`。目前比赛层还缺的是 conversational/session facade 和固定 M6 QA benchmark，而不是另一套 chat-only reasoning engine。
