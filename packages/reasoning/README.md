# `packages.reasoning`

`packages.reasoning` owns M6 Decision/QA contracts, model proposal normalization and validation. It consumes already-materialized M4 `InvestigationState`; it does not query Evidence/Knowledge storage directly, invoke external tools, or mutate Case state.

`DecisionService` finalizes typed fact/inference/recommendation conclusions against the exact Case revision. A fact conclusion must reproduce one confirmed M4 proposition exactly and cite evidence attached to that same state item; combining or paraphrasing state into a new proposition is an inference, not a fact. Inference conclusions may cite evidence present in M4 state and preserve intermediate `reasoning_relation_refs`. `CitationBinder` requires an explicit EvidenceRef→source/locator input from the caller; missing citation material fails rather than being synthesized.

`ModelDecisionPlanner` receives only the supplied M4 state plus caller-provided citation source metadata. It can propose a typed final decision or a typed continuation; Case identity/revision are always overwritten from the current M4 state rather than trusted from model output. `decision-model-v6-core` also makes answer minimality part of the model contract: emit only conclusions required by the user's question, do not repeat an already-supported FACT as an explanatory INFERENCE, and do not add adjacent facts merely because they are available in state. Final proposals still pass `DecisionService` before `apps.decision_runtime` calls the M4-owned `DecisionCommit` event gate.

Product questions and durable Investigation finalization opt into `decision-model-v7`, which asks the same DecisionRole to write a short research report as natural paragraphs after it has chosen the structured answer and conclusions. Paragraphs must use complete sentences in the question's language, explain source support in ordinary terms without internal state/payload vocabulary or citation counting, distinguish confirmed findings from inference and uncertainty, and cite only evidence already used by validated conclusions. `DecisionService` enforces that citation subset before persistence. Evaluation callers that do not request a report use `decision-model-v6-core` and retain structured field authority; older DecisionResults without report paragraphs remain readable. Sufficiency is evaluated against the whole user goal. Repository metadata cannot establish security or relationship coverage; empty conflict/unknown arrays do not establish absence. Reports lead with material coverage gaps and omit unrelated popularity/identity fields. These instructions guide model behavior; exact fact/citation validation remains enforced by DecisionService, not by prose.

For a targetless general how-to question, Product requests `decision-methodology-v1` with a final-only schema. This permits M6 to explain a verification procedure as uncited recommendations without pretending to have investigated a particular case. Product requires a prose answer and rejects fact/inference conclusions in this mode. A named target still uses the ordinary evidence gate.

`ModelDecisionPlanner` also accepts caller-supplied runtime coordinates for recording (`task_run_id`, `execution_id`, `budget_ref`, request owner). These coordinates affect provenance only; they do not enter decision semantics. Product DIRECT/RETRIEVE uses this seam so RecordedModelProvider can bind interactive M6 calls to the real TaskRun/Execution while leaving the synthetic lightweight question state out of the durable Case foreign key.

Validated decisions are additionally written to immutable `DecisionResultStore`. This does not replace M4 `current_decision`: M4 still decides which result is current for a durable Case. The M6 store gives every validated result a stable `decision_id` read identity, including synchronous Product decisions that intentionally have no durable Case.

Product multi-turn history is not M6 factual state. `ModelDecisionPlanner.session_context` may carry prior user input and immutable Decision refs/payloads for conversational co-reference, but the system instruction marks that history as non-evidence. FACT conclusions still have to exactly reproduce a proposition in the current confirmed InvestigationState and cite its current EvidenceRef; an old session answer cannot satisfy that invariant by itself.

When evidence is insufficient, M6 emits `ContinuationRequest`. The request contract is owned by the M4 receiving boundary under `packages.investigation.state.continuation`; M6 can validate and return it but cannot create `EvidenceNeed` itself. Control-plane strings are bounded before persistence: final `stop_reason` and continuation `purpose` are short machine-readable codes, while natural-language explanation belongs in conclusions or continuation `reason`. The runtime also defends the matching 128/256-character storage boundaries before SQL flush so a model cannot turn free-form prose into a database truncation failure. App composition first wraps the request as a `TaskIntent`, then `ContinuationGate` performs target/revision validation, deterministic semantic dedupe, and the actual EvidenceNeed write. This preserves the TD2 `ContinuationRequest → TaskIntent → M4` authority path without giving M6 storage authority.

## Design → implementation map

TD2 的 M6 pipeline 已经落成 `ModelDecisionPlanner → DecisionDraft | ContinuationRequest → DecisionService → M4-owned gate`。`decision.py` 持有 conclusion typing 与 evidence/reasoning validation；`citation.py` 只把既有 EvidenceRef 绑定到显式 source/locator；`model.py` 只是 structured proposal generator；`storage.py` 只持久化已经验证的 immutable DecisionResult。`apps.decision_runtime` 是最终 composition boundary：final 走 `DecisionCommit` 并登记 M6 result，continuation 走 M4 `ContinuationGate`。

Product AskQuestion 与正式评测调用同一条 M6 runtime/invariant。正式 Product QA 与 session/follow-up live benchmark 已经沿同一条 production path 闭环；后续 M6 工作集中在扩大 frozen denominator、回归新的模型/策略版本与补充更难的 Case-read/long-Investigation 内容，而不是再造一套 chat-only reasoning engine。

A finished Product investigation episode uses the final-only `InvestigationReportResponse` schema. The same M6 call selects relevant findings from the whole state and writes a report with uncovered goal dimensions in `unknowns`; a delivered report is not a declaration of evidence sufficiency. Ordinary question/reasoning calls retain typed continuation. This avoids replacing a useful report with a latest-three-facts fallback when the model discovers another gap.

## Runtime defaults and report reads

Automatic jobs require both `SECFUSION_BACKGROUND_LLM_ENABLED=true` and `SECFUSION_EDITORIAL_ENABLED=true`. The current local Compose configuration sets both false. This does not disable explicit operator generation or account-owned question/investigation reports; those actions may still spend model tokens. Existing public and private HTML reads are deterministic and free of model invocation.

Resume affects future eligible slots and model processing. It does not backfill skipped document revisions or historical editorial slots. Provider usage for every recorded generation/review/revision attempt remains distinct from monetary estimates.

## Public editorial reports and HTML

`editorial_prompt.py` owns the versioned `public-editorial-v5` profile, separate from ordinary research prose: event-based selection, attributed source claims, dates and numeric scope, short paragraphs, separate analysis, useful uncertainty and no runtime vocabulary. `BriefingGenerator` uses the same M6 validation over M4 tentative passages and then a second structured editorial review. Both support and editorial quality must pass; mechanical layout/length/vocabulary checks add publication issues. This is model critique, not an independent truth guarantee. Each stage has a bounded 300-second wall budget and recorded model requests.

`report_layout.py` permits only titles, named sections with exact paragraph coverage, and two styles. `report_html.py` escapes all model text, links only safe HTTP(S) sources, always retains unknowns/conflicts/assumptions, and renders responsive/print HTML with local fonts. Private and explicitly published reports share presentation, never access scope. Layout-free historical Decisions retain their original payload/hash when replayed.

`briefing_store.py` stores immutable publication coordinates and review outcomes. Application composition owns public source selection and revision/permission rechecks; HTTP reads never call the model. The operator CLI validates by default:

```bash
python -m scripts.generate_public_brief --topic 'Agent 安全' --document-id DOCUMENT_UUID
# Add --publish to generate, review and persist; inspect returned status.
# Add both --window-start and --window-end (timezone-aware ISO timestamps) for a period brief.
```

One to eight documents are allowed; selection is explicit. Equal source/policy inputs reuse the result; a rejected review is retained and not silently rerun. A revised prompt/policy creates a different identity. Automatic editorial is available through the worker but remains opt-in; the current local Compose defaults disable it. Public list/HTML revalidate current material before serving; changed revisions or rights hide stale reports without overwriting history. Full cross-module contract: Wiki `Information-Quality-and-Reports-2026-10`.

Automatic editorial jobs live in `editorial.py`: UTC slots, a durable outbox request,
atomic claim, 20-minute fenced lease and at most two attempts (five-minute retry delay).
A second delivery cannot claim a running/terminal job. Expired workers cannot publish.
`editorial_selection.py` groups recent eligible source titles by editorial topic and
prefers different upstream origins. It does not confirm events or infer corroboration.
The application freezes document identities, input digest and content fingerprints
before model calls. Previously attempted content is not selected again each slot.
No eligible new material is `skipped`; failed editorial review is `review_required`.

`public-editorial-v5` generates a separately cited `report_summary` before body paragraphs.
It leads with concrete news, numbers or change, with natural attribution; self-description,
clickbait and repetitive defensive scope statements are excluded. Critique explicitly
checks `summary_supported`; public publication requires a nonempty cited summary.
The feed reads this field, with a legacy excerpt fallback. Absent optional summaries
are omitted from old Decision identity/storage payloads, preserving immutable replay.

`public-briefing-v2` permits one corrective model pass after a rejected first review,
followed by full fresh review. It never loops until accepted or weakens citation rules.
At most four logical model calls run within the worker's overall budget; the rejected
review and prior decision coordinate are retained in `revision_history`. An operator
can revise a retained rejected draft under the new policy without rewriting its record.
