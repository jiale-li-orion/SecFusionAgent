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

`commands/start_investigation.py` owns the product workflow order. `InvestigationTaskLauncher` is the reusable seam for creating a policy-admitted InvestigationRole Task on an existing Case; Product and internal callers reuse this launcher instead of maintaining parallel admission/budget/execution wiring. `ContinueInvestigationUseCase` composes the same owners for Product session follow-up: it reuses an existing `active/waiting` Case, opens a new EvidenceNeed at the current Case revision, launches a fresh InvestigationRole episode and keeps the Case identity stable.

`queries/investigations.py` owns the Product read projection. It reads M4 state plus the latest Task/Execution coordinate and maps them into `InvestigationView`; Product clients do not receive `TaskContract`, `ContextManifest`, `PolicyDecision`, `BudgetAccount`, or raw TaskEvent schema. List queries use an opaque cursor and bounded page size.

`views/` contains stable Product DTO/read-model types. These are application contracts, not ORM models and not domain authority.

The current Product layer also owns account/session coordination (`authentication.py`), user interests and feedback (`intelligence_preferences.py`), evidence-based recommendations (`queries/recommendations.py`), idempotent selected-dimension enrichment admission (`commands/start_enrichment.py`), and source-driven WORLD formation/story reads (`queries/world_formation.py`, `queries/world_reader.py`). Recommendation ranking only uses explicit interests and accepted, cited Knowledge; it is not a trained personal model. The WORLD story reader has a bounded shared refresh so expensive reads do not fan out under concurrent requests. `queries/worker_probe.py` observes Celery replies and queues with timestamps; it does not infer uptime or own heartbeat persistence.

`queries/world.py` curates the front-page story candidates without deleting source material: obvious publisher landing-page titles such as `Blog` and `Download Now` stay in Evidence/Document storage but do not displace an article or advisory in WORLD/INTELLIGENCE. Category interleaving, source revision text and Evidence coordinates remain unchanged. When WORLD focuses the vulnerability direction, the Product client may read a genuine Hot vulnerability in its story pane, with the replaceable Hot versus durable Evidence boundary still visible.

`packages/intelligence/incident/relevance.py` applies a conservative reported-security-event screen to the broad Redis incident-signal pool for the public candidate watch read. The collection owner uses the same screen before correlating two broad news feeds, so ordinary market headlines no longer create new Incident candidates. This is selection, not a promotion decision or a replacement for incident correlation. The product shows candidate source coordinates separately from durable Incident dossiers.

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

The public chat submits a natural-language question without a `task_kind`. `question_intent.py` binds an unambiguous CVE identifier from the question, keeps open language on the RETRIEVE path, and uses an explicit target for LOOKUP. Explicit API task kinds remain available for controlled callers. Shared task admission compiles the resolved kind, and `DecisionRole` owns the read-only synchronous TaskRun. LOOKUP binds accepted M3 claims/relations back to stable EvidenceRefs before M6. Bounded RETRIEVE adds passages as tentative context without promoting them into confirmed facts. If M6 escalates a first-turn retrieval with tentative passages but no confirmed facts, the Investigation EvidenceNeed covers the user's whole question rather than only the first missing detail; provider-suggested source-role narrowing is dropped unless the caller explicitly required it. When retrieval exposes exactly one canonical target, an omitted continuation target binds to it. When no target or evidence exists, the Product returns a validated insufficient-evidence Decision instead of a lifecycle error.

Product Question sessions are Application-owned coordination, not a second reasoning state. `QuestionSessionStore` persists turn order, user input, carried canonical target IDs, world/context coordinates and stable `decision_ref` / `investigation_ref`; it does not copy Decision, Evidence or M4 state payloads. A follow-up may omit an explicit target when the previous turn carries exactly one durable object. The previous `ContextManifest.context_id` becomes the next turn's `parent_context_id`. Prior Decision content is re-read from the immutable M6 result store and sent to M6 only as `session_context` for co-reference and intent resolution; the planner instruction explicitly forbids treating that history as evidence or current truth. Current facts must still be reproduced from the new turn's current `InvestigationState` and pass the normal citation gate.

Session list and turn history reads use owner-checked keyset pagination. Conversation pages advance with an opaque cursor over update time/session ID; turn pages advance with `before_turn` and keep stable ascending display order after the client joins pages. Deep links can load older turns without relying on a fixed first page.

Investigation-class follow-up now binds to the most recent durable `investigation_ref` in the Product session when that Case is still `active/waiting`. The user does not rebind `cve_id/object_id` on that path: the Case owns its target set. Product checks for a non-terminal InvestigationRole TaskRun before mutating M4; if one exists, the follow-up fails with a lifecycle conflict and does not create an orphan EvidenceNeed. Once the prior episode is terminal, the next follow-up appends a new EvidenceNeed and launches the next TaskRun on the same Case. Resolved/cancelled/closed Cases are not silently reopened; normal target carry may create a new Case instead.

Read-only LOOKUP/RETRIEVE can now explicitly read that live Case as well. The Case-read profile is selected only when the Product session has an `active/waiting` investigation, the new question omits `cve_id/object_id`, and the TaskKind is LOOKUP/RETRIEVE. Product materializes the durable M4 `InvestigationState` into an ephemeral DecisionRole input, preserves the real `case_ref` and `investigation_state_ref` in ContextManifest, binds TaskRun/ModelRequest to the real Case, and changes only the ephemeral `goal` to the current user question. A Case-read DecisionResult is immutable Product output; it does not commit `M4.current_decision`. M4 StatePatch evidence IDs remain durable owner-local IDs; the Product projection canonicalizes them to `evidence:<id>` only in the read context so the normal M6 citation gate can resolve them without rewriting M4 state.

Case-read RETRIEVE additionally requires the M4 state's `last_world_revision` to equal the current Knowledge revision. Product refuses to mix fresh retrieval passages with a stale InvestigationState; the Investigation episode must refresh/rebase first. Explicit `cve_id/object_id` on a LOOKUP/RETRIEVE bypasses Case-read and starts a normal lightweight Question profile, so an old session Case cannot silently hijack an explicitly rebound read.

RETRIEVE query construction starts with the original question, then tries bounded stable identifiers and technical names if it finds no passage. A joined Latin name can be matched against source text with internal whitespace and punctuation folded, so `Huggingface` can find `Hugging Face`; this fallback is independently recorded as `compact_name`. Each physical query writes a durable `RetrievalInvocation` and places its ref in `ContextManifest.retrieval_invocation_refs`. Reuse requires the same Product session and exact request digest: query, Knowledge revision, operator revision, result limit and source scope. Prior ordered `document-chunk:*` refs are re-read; only a complete replay skips physical search. Different wording or world revision never reuses merely by semantic similarity.

For comparison, compound and cross-source questions submitted through the automatic chat route, the Product invokes the schema-constrained L2 `QueryIntent` planner. It records the planning model request under the Product request, compiles at most four search phrases into individually recorded physical retrievals, and persists the plan and model request reference in the DecisionRole ContextManifest. The owner-checked Task dossier includes that planning attempt beside the decision attempt; QUESTIONS displays the compiled phrases in its audit rail. A planner failure falls back to L0/L1 rather than discarding the user's question. Explicit benchmark/API task kinds keep their existing deterministic route.

Physical retrieval failures before TaskRun/Context creation now commit a separate `failed` RetrievalInvocation after rolling back the provisional Question command. They do not create a blank QuestionSession or TaskRun and cannot become reuse candidates.

Every synchronous Question still creates TaskRun / Budget / Execution coordinates. Ordinary lightweight questions keep the synthetic `question:*` state out of the durable Case foreign key. Explicit session Case-read questions instead bind the DecisionRole TaskRun, ContextManifest and recorded ModelRequest to the real M4 Case. This preserves the TD3 live-latency/provenance chain without creating a fake Case and makes read activity discoverable from the real Case timeline.

Validated M6 results are persisted immutably by `DecisionResultStore`. M4 remains the owner of which decision is current for a durable Case; the result store only supplies stable DecisionResult identity, including DIRECT/RETRIEVE results that have no Case. `GET /api/v1/decisions/{decision_id}` reads this store and retains a compatibility read from historical M4 DecisionCommit events.

The Product decision projection also exposes optional `report_paragraphs` attached to a validated DecisionResult. Both synchronous Product questions and durable Investigation finalization request this presentation text in their DecisionRole calls; each paragraph's evidence refs must be among the validated conclusion refs. The structured answer and conclusions remain the evaluation and authority fields. Older Decisions without report paragraphs retain their validated fields and citations.
If a direct model proposal fails the DecisionService evidence gate, the Question command records a bounded natural-language answer with no factual conclusions or citations and keeps the failed proposal out of the durable Decision. An InvestigationRole that stops for `no_progress` or `budget_exhausted` asks M6 for a partial final report using only confirmed M4 facts. With no confirmed facts, or when M6 proposes an invalid Decision, it commits a zero-claim boundary report and leaves its Case waiting for evidence. Both paths preserve the M4/M6 commit gate and allow the account session to continue.

## Boundaries

Public command replay is owned by `command_idempotency.py` and persisted in `product_command_records` (migration `20261009_0032`). An authenticated principal, operation and client `Idempotency-Key` identify one normalized request. Repeating it returns the same Question result or existing Case; changing the body with the same key returns `409 idempotency_conflict`. Question commands store the final Product response and do not rerun a model or append another turn on replay. The Case, session turn, task terminal transition and replay result commit together. A synchronous model call has an earlier durable TaskRun and a pending replay record; an interrupted pending command fails closed instead of launching a duplicate run. A failed model call marks its record failed, so a user retry needs a new key. Cancel requires an expected Case revision and compares it under the Case lock.

When a model proposes a Decision that fails the M6 evidence gate, the Question command records a completed boundary Decision with `evidence_validation_failed`, no conclusions, and no citations. It does not persist or display the rejected proposal as a validated Decision. The SSE route may show a clearly marked unvalidated draft while the provider is streaming; the durable boundary answer replaces it after validation.

Application may depend on `apps` composition modules and TD1/TD2 package ports. No package may import `apps.application`. Product workflow ordering, sync/async choice, request/task trace linkage, pagination and public idempotency belong here; Evidence/Knowledge, EvidenceNeed transitions, Task state transitions, Policy, Capability and Decision validation remain with their original owners.

The current Product layer implements ProductEvent/SSE and explicit Case cancellation. Selected-dimension enrichment requires an `Idempotency-Key`; a generic manual Case resume command remains open. Waiting-dependency wake stays runtime-owned and user continuation stays bound to the durable Case/session path. Generic RETRIEVE continuation binds only canonical object identities returned by retrieval; chunk IDs and URLs never become Case identity. Multi-turn Product follow-up, serialized Investigation-class follow-up on the same durable Case, explicit live-M4 Case-read, formal Product/session evaluation, durable retrieval invocation provenance, exact-query result reuse and prospective long-Investigation completion measurement are implemented. Still open: semantic/non-identical-query reuse (intentionally deferred) and a broader competition denominator for live Case-read/long-Investigation content. These later TD2A/TD3 slices should extend the current session/Case/invocation refs rather than create a chat-only reasoning engine.

## Verification

```bash
uv run pytest apps/application/tests -q
uv run pytest apps/api/tests/test_product_investigations.py -q
uv run pytest apps/api/tests/test_product_questions.py -q
uv run pytest apps/api/tests/test_product_edge.py -q
make product-check
```
