# `packages.investigation`

`packages.investigation` owns M4 investigation state and M5 InvestigationRole behavior. Technical Design 2 fixes the Case/TaskRun separation, `InvestigationState`, `EvidenceNeed`, Perception and StatePatch boundaries; this README records the current package-level implementation and verification surface.

## Case and state ownership

`cases/` owns durable Case creation/lifecycle and reuse metadata. A Case can span multiple TaskRuns; TaskRun terminal state is not used as Case lifecycle state. Product session follow-up now exercises this separation directly: after one InvestigationRole episode becomes terminal, a new EvidenceNeed and TaskRun may be attached to the same active/waiting Case without creating a second Case.

`state/` owns append-only Case state events, materialized `InvestigationState`, `EvidenceNeed`, and StatePatch validation. Investigation state references Evidence/Knowledge rather than copying raw source content into a second fact store. State changes are revisioned and must pass the state integration gate before the materialized view changes.

Product Case-read does not weaken that ownership. A session LOOKUP/RETRIEVE may project the current durable `InvestigationState` into a read-only DecisionRole context, but it cannot write the resulting Decision back as M4 current authority. Existing M4 StatePatch evidence handles may be stored as raw `EvidenceLink.evidence_link_id`; the Product read projection normalizes those handles to `evidence:<id>` for the M6 citation surface without changing the durable Case state. ContextManifest retains the exact `case_ref` and `investigation_state_ref`, so this projection remains attributable to one Case revision.

`PerceptionEvent` and `InvestigationSnapshot` are durable replay coordinates. Perception records request/physical plan/percept/evidence/observation refs, cost, timing and world revision. Rebuilding `InvestigationState` restores `last_world_revision / last_perception_at` from durable perception history instead of resetting them to the Case creation point.

`state/world_change.py` consumes KnowledgeChange notices through a deterministic relevance gate. A change only touches Cases whose targets or used evidence dependencies intersect changed object/claim/relation IDs. Relevant changes can invalidate a confirmed Case-local proposition, reopen its resolved EvidenceNeed and wake a waiting Case; unrelated changes do not invoke the Agent loop.

The M4 state surface separates confirmed/tentative/conflict/unknown/hypothesis/open-question/decision-variable state from execution failure. Provider/network/policy failures remain execution/runtime state unless they justify an explicit investigation unknown or blocked EvidenceNeed.

## Perception

`perception/` exposes the controlled read surface over the Evidence World. Query/retrieval candidates are assembled into typed Percept output with source/evidence references and world revision. Perception does not write canonical Knowledge directly and does not turn arbitrary tool/model output into durable facts.

External observations that may affect durable state must return through the Evidence/Knowledge or StatePatch gates defined by their owner package.

## Investigation Role

`runtime/` owns bounded InvestigationRole episodes for VERIFY/INVESTIGATE/WATCH tasks. The Role reads the pinned TaskContract, InvestigationState and Percept inputs, then emits typed state actions or delegated tasks. It may delegate M3 EnrichmentTask through the shared Task Runtime; child natural-language output is never accepted as fact authority.

After a Percept, the next ContextManifest revision retains its evidence handles. The planner also receives a bounded history of recent distinct Percepts, including their source excerpts: EvidenceRef metadata alone does not contain the retrieved passage text. Repeated A/B perceptions count as no progress rather than consuming the entire turn budget while forgetting the other source.
The source-document planner's `investigation-model-v2-source` guidance asks it to commit each supported subfinding as soon as it has a citable passage and to leave an unresolved comparison dimension open. That runtime guidance is included in the recorded PromptAssembly disclosure scope; a failed focused search should not restart the same inspection loop.
Model-proposed WAIT/STOP reasons are normalized to short machine-readable codes before they reach the 128-character TaskRun storage field. A prose reason falls back to a bounded code, so an otherwise valid Case with confirmed findings can proceed to normal finalization instead of failing on a storage-length error.

When a replayed delegation resolves to an already completed child, InvestigationRole now inspects current canonical evidence in the same episode and gives that Percept to its planner instead of waiting for a terminal child event that has already been consumed. A terminal failed/blocked child ends the parent episode with a clear blocked reason. This prevents a live Case from parking indefinitely on an already terminal EnrichmentRole run while preserving the usual event-driven wait for an active child.

Delegation identity is stable for one parent TaskRun, target CVE, and canonical dimension set. Context refreshes and planner iterations therefore reuse the same child run. Replay validates the child's fixed contract and authority coordinates while keeping its original Knowledge snapshot, even if parent and child context revisions advanced after creation. A later follow-up TaskRun can request fresh enrichment independently.

The M4 State Gate can reject a model-proposed patch, for example when an inferred reasoning relation attempts to set a confirmed finding. The bounded InvestigationRole loop now passes that exact rejection back to the planner as a correction Percept and counts it toward the no-progress limit. Repeated invalid patches still block the run; rejected claims never enter durable Case state.

The canonical `VerifyFixBoundary` acceptance path is composed from the production runtime boundaries rather than a test-only orchestrator: `TaskRun → Context/Skill/CapabilityView → ModelInvestigationPlanner → Perception → Capability/Policy/Budget → EphemeralObservation → promotion/EvidenceIngress → StatePatch Gate → EvidenceNeed resolution → Task completion`. A second acceptance path starts with no durable fix evidence, delegates `fix_remediation` to `EnrichmentRole`, waits, receives the child's `EnrichmentStateChanged` through the Task Event Redis consumer path, queues the parent through the deterministic dependency scheduler, refreshes to the child-updated Knowledge revision, resolves the new `fixed-version` relation back to a durable EvidenceRef through local Perception, and then completes the parent VERIFY task.

`runtime/context.py` is the Investigation-domain Context binding adapter. It resolves pinned object/relation/evidence refs and the exact pinned InvestigationState revision into `MaterializedFragment`s, then delegates ordering/trust/cache/hash semantics to `task_runtime.ContextMaterializer`. Because the current Knowledge read model is a current projection and object properties are not historical versions, online materialization fails closed when `ContextManifest.knowledge_revision` is behind the current world revision; the caller must refresh/rebase rather than accidentally expose future facts to an old context. Historical M7 replay requires a dedicated Snapshot/replay read path.

A runtime episode terminates on TaskContract completion, explicit block/wait, budget/deadline stop, or no-progress conditions. Application-level follow-up is serialized at the Case boundary: while an InvestigationRole TaskRun is `submitted/queued/running/waiting_*`, Product refuses to open another follow-up EvidenceNeed; after that episode is terminal, a new EvidenceNeed can seed a fresh TaskRun on the same Case. This prevents Product chat/session behavior from introducing concurrent Case writers. WATCH uses terminal short episodes rather than a permanently running model process: `waiting_for_world_update` completes the current TaskRun and parks the Case; a relevant world change activates the Case and `WatchWakeService` evaluates `WATCH_RESUME` policy before deriving a fresh queued WATCH TaskRun with a new Context, BudgetAccount and ExecutionEnvelope pinned to the new world revision. Trigger identity makes the derivation replay-idempotent.

Read-only Product Case-read is allowed while an InvestigationRole episode is active because it does not mutate M4. RETRIEVE Case-read is stricter than LOOKUP: its durable state world revision must match current Knowledge before fresh passages may be appended to the ephemeral read context. A stale Case must be refreshed by its Investigation runtime instead of letting Product combine state from one world with retrieval from another.

The worker-side Task Event scheduler now routes queued `InvestigationRole` episodes to a coarse-grained Celery task, and the generic Task Runtime executor atomically claims the run before invoking the Role. `WorldChangeService` still never invokes a model directly. The remaining active-investigation gap is physical capability composition: the production Investigation factory currently exposes the model, Context/Skill path, local Perception and delegation, while external/sandbox Perception remains unavailable until a production Capability catalog/binding/executor is configured.

Model composition is shared with M6 through `apps.model_runtime.create_recorded_model_provider`. Transient provider transport failures and malformed JSON returned in a successful provider response are retried as distinct durable `ModelAttempt` rows under one logical `ModelRequest`; auth and schema failures remain terminal. This keeps provider instability observable without letting retries mutate Task or evidence semantics. Before a live M5/M6 run, `make model-provider-probe` checks endpoint authentication and structured-output compatibility with the same OpenAI-compatible adapter used by production composition.

## Skills

`skills/` owns investigation procedural knowledge; Task Runtime only carries `skill_selection_refs`. Skill versions use the TD2 four-level disclosure model `manifest → procedure → step → provenance`. Resolver selection is deterministic over Task kind, EvidenceNeed pattern, object type, required inputs/capability classes and validation status. Physical provider/endpoint/CLI instructions are rejected at publish time because Capability Binding owns implementation choice.

The five TD2 seed skills are currently persisted as `candidate`. Default online resolution only considers `validated/active` versions, so seed presence does not imply replay/regression validation. Skill provenance is materialized as non-instruction, ephemeral model data; procedure/step guards influence planning but do not replace Policy/Capability/State Gate enforcement.

## Trajectory and experience

`trajectory/` records execution/state transitions and references to evidence/percepts/artifacts used during the investigation. Large tool/model output remains in ArtifactStore.

`experience/` stores reusable investigation patterns. Experience can guide planning but does not provide factual authority. `ExperienceCompressor` now extracts/merges `ExperiencePattern` and proposes immutable `SkillPatchCandidate` versions while preserving support and counterexample trajectory refs. It can only change procedural material such as guards, fallbacks, stop conditions and capability preferences; it cannot grant Evidence authority or bypass Policy.

The full control path is now implemented as `Trajectory/Experience → ExperiencePattern → SkillPatchCandidate → packages.evaluation replay suite → SkillPromotionGate → active SkillVersion`. Promotion authority deliberately lives in M7 rather than in the Skill store. Online learning is therefore not “write a successful trajectory into memory”; candidate procedures remain inactive until support/counterexample/regression replay passes.

`replay/` captures a durable reference-preserving checkpoint over Snapshot + Task/Context/Event/Trajectory/runtime-control coordinates and can reconstruct historical M4 state from append-only CaseStateEvents. It fails closed when the pinned Knowledge revision cannot be read exactly, preventing future-world leakage. M1–M3 versioned historical reads are the remaining blocker for true historical Agent re-execution.

## Design → implementation map

TD2 的 M4/M5 没有落成一个“万能 Agent service”。Case lifecycle 由 `cases/` 持有；事实缺口与 durable state write 由 `state/` 持有；read planning/execution 由 `perception/` 持有；bounded Agent loop、delegation、WAIT/WATCH 在 `runtime/`；程序性先验在 `skills/`；运行经验在 `trajectory/experience`；historical coordinate 在 `replay/`。这些 owner 通过 ID/revision/reference 连接，而不是通过共享可变 dict。

当前 production composition 位于 `apps/investigation_runtime.py`：Context/Skill/model/local Perception/delegation 已接入；external Capability catalog/binding/executor 尚未接入，因此真实 search/browser/repository/asset tool action 会 fail unavailable，而不是绕开 Policy 直接调用 provider。这是当前 M5 最主要的实现边界。
来源与文档类调查现在把最近四个不同的 Percept 连同可追溯 EvidenceRef 一起装配给规划器，并明确要求先把已找到的可引用局部发现写入 M4，再继续寻找比较维度的缺口。重复读取相同片段会触发 `no_progress` 终止。若终止时仍无已确认事实，Product M6 会提交零事实、零引用的自然语言证据边界说明，并让 Case 等待新材料；这不会把候选材料冒充已核验结论。

## Dependency boundary

Allowed dependencies are the public contracts from `shared`, `intelligence`, `enrichment`, `task_runtime`, and execution-control packages under `runtime` where the current implementation requires them. Provider-specific SDK objects do not cross into investigation state or Perception contracts.

The dependency gate permits the public intelligence retrieval contracts and the canonical `EnrichmentDimension` vocabulary used by `EnrichmentDelegationRequest`. A delegation therefore validates the same dimension names as M3 without duplicating its vocabulary; investigation still cannot import Knowledge storage or write services.

## Verification

```bash
uv run pytest packages/investigation -q
uv run pytest tests/test_verify_fix_boundary_e2e.py -q
SECFUSION_RUN_INTEGRATION=1 uv run pytest tests/integration/test_investigation_runtime.py -q
make integration-core
make model-provider-probe
```
