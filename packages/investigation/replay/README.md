# `packages.investigation.replay`

This package owns the M7 investigation replay contract. A checkpoint is a reference-preserving manifest over an existing `InvestigationSnapshot`, TaskRun/TaskContract/ContextManifest, durable TaskEvent sequence, Trajectory ordinal and an injected runtime-control binding. It does not copy Evidence/Knowledge content and it does not execute Policy/Sandbox itself.

Checkpoint capture is persisted as a typed `replay_checkpoint` TrajectoryEvent while the source trajectory is running. Repeated capture of the same Snapshot/TaskEvent/Trajectory point is idempotent. `ReplayCheckpointService.prepare()` reconstructs the pinned M4 `InvestigationState` from append-only CaseStateEvents without mutating the current materialized state. The current M1–M3 Knowledge read model is still a latest projection; if its current revision differs from the checkpoint's pinned world revision, replay raises `ReplayWorldUnavailable` instead of silently exposing future facts to the historical run.

`ReplayIntervention` is deliberately single-variable. Supported interventions include single-loop vs delegated multi-loop topology, reference-vs-summary context handoff, policy revision, sandbox profile, Skill ref and Capability Registry revision. `apply_replay_intervention` changes only that field in a derived replay environment. `evaluate_replay_protocol` provides deterministic protocol acceptance before model-quality scoring; `packages.evaluation.m7_replay` then compares baseline/candidate metrics under the same frozen checkpoint. True historical Agent re-execution remains blocked until M1–M3 exposes a versioned historical read path.

## Concrete implementation

`contracts.py` 定义 frozen replay coordinate、runtime binding、intervention/environment、expectation 与 protocol result。`ReplayCheckpointService.capture()` 校验 Snapshot/TaskRun/Context/TaskEvent/Trajectory/runtime-control 引用并把 checkpoint 作为幂等的 `replay_checkpoint` TrajectoryEvent 持久化；`prepare()` 调用 `InvestigationStateService.get_state_at_revision()` 重建历史 M4，然后检查 pinned Knowledge revision 是否仍可精确读取。revision 漂移直接抛 `ReplayWorldUnavailable`，不会偷偷替换成 latest projection。

`packages.evaluation.m7_replay` 持有 baseline/candidate comparison 和 metric tolerance；`packages.evaluation.skill_promotion` 消费 replay 结果决定 Skill 是否可晋级。这里持有 reproducible coordinate，不持有 benchmark policy，也不直接修改 Skill status。
