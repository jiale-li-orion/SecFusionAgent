# `packages.investigation`

`packages.investigation` owns M4 investigation state and M5 InvestigationRole behavior. Technical Design 2 fixes the Case/TaskRun separation, `InvestigationState`, `EvidenceNeed`, Perception and StatePatch boundaries; this README records the current package-level implementation and verification surface.

## Case and state ownership

`cases/` owns durable Case creation/lifecycle and reuse metadata. A Case can span multiple TaskRuns; TaskRun terminal state is not used as Case lifecycle state.

`state/` owns append-only Case state events, materialized `InvestigationState`, `EvidenceNeed`, and StatePatch validation. Investigation state references Evidence/Knowledge rather than copying raw source content into a second fact store. State changes are revisioned and must pass the state integration gate before the materialized view changes.

`PerceptionEvent` and `InvestigationSnapshot` are durable replay coordinates. Perception records request/physical plan/percept/evidence/observation refs, cost, timing and world revision. Rebuilding `InvestigationState` restores `last_world_revision / last_perception_at` from durable perception history instead of resetting them to the Case creation point.

`state/world_change.py` consumes KnowledgeChange notices through a deterministic relevance gate. A change only touches Cases whose targets or used evidence dependencies intersect changed object/claim/relation IDs. Relevant changes can invalidate a confirmed Case-local proposition, reopen its resolved EvidenceNeed and wake a waiting Case; unrelated changes do not invoke the Agent loop.

The M4 state surface separates confirmed/tentative/conflict/unknown/hypothesis/open-question/decision-variable state from execution failure. Provider/network/policy failures remain execution/runtime state unless they justify an explicit investigation unknown or blocked EvidenceNeed.

## Perception

`perception/` exposes the controlled read surface over the Evidence World. Query/retrieval candidates are assembled into typed Percept output with source/evidence references and world revision. Perception does not write canonical Knowledge directly and does not turn arbitrary tool/model output into durable facts.

External observations that may affect durable state must return through the Evidence/Knowledge or StatePatch gates defined by their owner package.

## Investigation Role

`runtime/` owns bounded InvestigationRole episodes for VERIFY/INVESTIGATE/WATCH tasks. The Role reads the pinned TaskContract, InvestigationState and Percept inputs, then emits typed state actions or delegated tasks. It may delegate M3 EnrichmentTask through the shared Task Runtime; child natural-language output is never accepted as fact authority.

The canonical `VerifyFixBoundary` acceptance path is composed from the production runtime boundaries rather than a test-only orchestrator: `TaskRun → Context/Skill/CapabilityView → ModelInvestigationPlanner → Perception → Capability/Policy/Budget → EphemeralObservation → promotion/EvidenceIngress → StatePatch Gate → EvidenceNeed resolution → Task completion`. A second acceptance path starts with no durable fix evidence, delegates `fix_remediation` to `EnrichmentRole`, waits, receives the child's `EnrichmentStateChanged` through the Task Event Redis consumer path, queues the parent through the deterministic dependency scheduler, refreshes to the child-updated Knowledge revision, resolves the new `fixed-version` relation back to a durable EvidenceRef through local Perception, and then completes the parent VERIFY task.

`runtime/context.py` is the Investigation-domain Context binding adapter. It resolves pinned object/relation/evidence refs and the exact pinned InvestigationState revision into `MaterializedFragment`s, then delegates ordering/trust/cache/hash semantics to `task_runtime.ContextMaterializer`. Because the current Knowledge read model is a current projection and object properties are not historical versions, online materialization fails closed when `ContextManifest.knowledge_revision` is behind the current world revision; the caller must refresh/rebase rather than accidentally expose future facts to an old context. Historical M7 replay requires a dedicated Snapshot/replay read path.

A runtime episode terminates on TaskContract completion, explicit block/wait, budget/deadline stop, or no-progress conditions. WATCH uses terminal short episodes rather than a permanently running model process: `waiting_for_world_update` completes the current TaskRun and parks the Case; a relevant world change activates the Case and `WatchWakeService` evaluates `WATCH_RESUME` policy before deriving a fresh queued WATCH TaskRun with a new Context, BudgetAccount and ExecutionEnvelope pinned to the new world revision. Trigger identity makes the derivation replay-idempotent.

The worker-side Task Event scheduler now routes queued `InvestigationRole` episodes to a coarse-grained Celery task, and the generic Task Runtime executor atomically claims the run before invoking the Role. `WorldChangeService` still never invokes a model directly. The remaining active-investigation gap is physical capability composition: the production Investigation factory currently exposes the model, Context/Skill path, local Perception and delegation, while external/sandbox Perception remains unavailable until a production Capability catalog/binding/executor is configured.

## Skills

`skills/` owns investigation procedural knowledge; Task Runtime only carries `skill_selection_refs`. Skill versions use the TD2 four-level disclosure model `manifest → procedure → step → provenance`. Resolver selection is deterministic over Task kind, EvidenceNeed pattern, object type, required inputs/capability classes and validation status. Physical provider/endpoint/CLI instructions are rejected at publish time because Capability Binding owns implementation choice.

The five TD2 seed skills are currently persisted as `candidate`. Default online resolution only considers `validated/active` versions, so seed presence does not imply replay/regression validation. Skill provenance is materialized as non-instruction, ephemeral model data; procedure/step guards influence planning but do not replace Policy/Capability/State Gate enforcement.

## Trajectory and experience

`trajectory/` records execution/state transitions and references to evidence/percepts/artifacts used during the investigation. Large tool/model output remains in ArtifactStore.

`experience/` stores reusable investigation patterns. Experience can guide planning but does not provide factual authority. Promotion into procedural Skill remains subject to TD2 replay/regression rules.

`ExperienceCompressor → SkillPatchCandidate → replay/regression → promotion` is still M7 work. Existing Experience/Trajectory/Snapshot storage is substrate, not evidence that adaptive Skill promotion already exists.

## Dependency boundary

Allowed dependencies are the public contracts from `shared`, `intelligence`, `enrichment`, `task_runtime`, and execution-control packages under `runtime` where the current implementation requires them. Provider-specific SDK objects do not cross into investigation state or Perception contracts.

## Verification

```bash
uv run pytest packages/investigation -q
uv run pytest tests/test_verify_fix_boundary_e2e.py -q
SECFUSION_RUN_INTEGRATION=1 uv run pytest tests/integration/test_investigation_runtime.py -q
make integration-core
```
