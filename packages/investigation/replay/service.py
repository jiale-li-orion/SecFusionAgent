from __future__ import annotations

import json
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from packages.intelligence.retrieval.validation import current_knowledge_revision
from packages.investigation.replay.contracts import (
    ReplayCheckpoint,
    ReplayCheckpointCapture,
    ReplayEnvironment,
    ReplayExpectation,
    ReplayIntervention,
    ReplayInterventionKind,
    ReplayLoopTopology,
    ReplayObservation,
    ReplayPreparedCoordinate,
    ReplayProtocolResult,
    ReplayRuntimeBinding,
)
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.state.snapshot import (
    InvestigationSnapshot,
    InvestigationSnapshotService,
)
from packages.investigation.storage.models import InvestigationTrajectoryModel
from packages.investigation.trajectory.service import TrajectoryService, list_events
from packages.task_runtime.contracts.models import TaskRun
from packages.task_runtime.storage.service import (
    get_task_context,
    get_task_contract_for_run,
    get_task_run,
    list_task_events,
)

CHECKPOINT_EVENT_TYPE = "replay_checkpoint"


class ReplayCheckpointService:
    def __init__(
        self,
        *,
        snapshot_service: InvestigationSnapshotService | None = None,
        trajectory_service: TrajectoryService | None = None,
        state_service: InvestigationStateService | None = None,
    ) -> None:
        self._snapshots = snapshot_service or InvestigationSnapshotService()
        self._trajectories = trajectory_service or TrajectoryService()
        self._state = state_service or InvestigationStateService()

    async def capture(
        self,
        session: AsyncSession,
        *,
        snapshot_id: str,
        trajectory_id: str,
        task_run_id: str,
        runtime: ReplayRuntimeBinding,
        task_event_seq: int | None = None,
        skill_refs: list[str] | None = None,
        loop_topology: ReplayLoopTopology,
        context_handoff_mode: str = "reference",
    ) -> ReplayCheckpointCapture:
        snapshot = await self._snapshots.get(session, snapshot_id)
        trajectory = await session.get(InvestigationTrajectoryModel, trajectory_id)
        if trajectory is None:
            raise LookupError(f"trajectory not found: {trajectory_id}")
        if trajectory.status != "running":
            raise ValueError("replay checkpoint capture requires a running trajectory")

        historical_state = await self._state.get_state_at_revision(
            session,
            snapshot.case_id,
            snapshot.case_revision,
        )
        if historical_state.case_revision != snapshot.case_revision:
            raise RuntimeError("replay snapshot historical state revision mismatch")

        run = await get_task_run(session, task_run_id)
        contract = await get_task_contract_for_run(session, task_run_id)
        context = await get_task_context(session, task_run_id)
        if run.case_id != snapshot.case_id or trajectory.case_id != snapshot.case_id:
            raise ValueError("replay checkpoint Case identity mismatch")
        expected_contract_ref = f"{contract.task_contract_id}@{contract.contract_revision}"
        if context.task_contract_ref != expected_contract_ref:
            raise ValueError("replay checkpoint TaskContract/Context mismatch")
        if runtime.task_run_id != task_run_id:
            raise ValueError("replay runtime binding TaskRun mismatch")
        if runtime.execution_envelope_ref != run.execution_envelope_ref:
            raise ValueError("replay runtime binding ExecutionEnvelope mismatch")
        if runtime.policy_revision != contract.policy_revision:
            raise ValueError("replay runtime policy revision mismatch")
        if (
            snapshot.knowledge_revision is not None
            and context.knowledge_revision is not None
            and snapshot.knowledge_revision != context.knowledge_revision
        ):
            raise ValueError("replay snapshot/world revision differs from Task Context")

        task_events = await list_task_events(session, task_run_id)
        if not task_events:
            raise ValueError("replay checkpoint requires durable TaskEvent history")
        selected_seq = task_event_seq or task_events[-1].seq
        selected_event = next((item for item in task_events if item.seq == selected_seq), None)
        if selected_event is None:
            raise ValueError(f"TaskEvent seq not found for replay checkpoint: {selected_seq}")
        if selected_event.base_context_revision > context.context_revision:
            raise ValueError("replay checkpoint TaskEvent references a future Context revision")

        trajectory_events = await list_events(session, trajectory_id)
        baseline_ordinal = max(
            (
                event.ordinal
                for event in trajectory_events
                if event.event_type != CHECKPOINT_EVENT_TYPE
            ),
            default=0,
        )
        checkpoint = _checkpoint(
            snapshot=snapshot,
            trajectory_id=trajectory_id,
            trajectory_ordinal=baseline_ordinal,
            run=run,
            contract_ref=expected_contract_ref,
            context_ref=run.context_manifest_ref,
            context_role_ref=context.role_ref,
            task_event_seq=selected_seq,
            runtime=runtime,
            skill_refs=sorted(set(skill_refs or context.skill_selection_refs)),
            loop_topology=loop_topology,
            context_handoff_mode=context_handoff_mode,
        )

        for event in trajectory_events:
            if event.event_type != CHECKPOINT_EVENT_TYPE:
                continue
            payload = event.payload.get("checkpoint")
            if not isinstance(payload, dict):
                continue
            stored = ReplayCheckpoint.model_validate(payload)
            if stored.checkpoint_id == checkpoint.checkpoint_id:
                return ReplayCheckpointCapture(
                    checkpoint=stored,
                    trajectory_event_id=event.event_id,
                    replay=True,
                )

        event = await self._trajectories.append_event(
            session,
            trajectory_id=trajectory_id,
            event_type=CHECKPOINT_EVENT_TYPE,
            payload={"checkpoint": checkpoint.model_dump(mode="json")},
        )
        return ReplayCheckpointCapture(
            checkpoint=checkpoint,
            trajectory_event_id=event.event_id,
        )

    async def get(
        self,
        session: AsyncSession,
        *,
        trajectory_id: str,
        checkpoint_id: str,
    ) -> ReplayCheckpoint:
        for event in await list_events(session, trajectory_id):
            if event.event_type != CHECKPOINT_EVENT_TYPE:
                continue
            payload = event.payload.get("checkpoint")
            if not isinstance(payload, dict):
                continue
            checkpoint = ReplayCheckpoint.model_validate(payload)
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        raise LookupError(f"replay checkpoint not found: {checkpoint_id}")

    async def prepare(
        self,
        session: AsyncSession,
        *,
        trajectory_id: str,
        checkpoint_id: str,
        intervention: ReplayIntervention | None = None,
    ) -> ReplayPreparedCoordinate:
        checkpoint = await self.get(
            session,
            trajectory_id=trajectory_id,
            checkpoint_id=checkpoint_id,
        )
        state = await self._state.get_state_at_revision(
            session,
            checkpoint.case_id,
            checkpoint.case_revision,
        )
        current_world = await current_knowledge_revision(session)
        if checkpoint.knowledge_revision is None:
            raise ReplayWorldUnavailable("replay checkpoint has no pinned knowledge revision")
        if current_world != checkpoint.knowledge_revision:
            raise ReplayWorldUnavailable(
                "historical Knowledge projection unavailable: "
                f"checkpoint={checkpoint.knowledge_revision}, current={current_world}"
            )
        return ReplayPreparedCoordinate(
            checkpoint=checkpoint,
            state=state,
            environment=apply_replay_intervention(checkpoint, intervention),
            world_revision=checkpoint.knowledge_revision,
        )


class ReplayWorldUnavailable(RuntimeError):
    """Raised when the current M1-M3 read model cannot reproduce a pinned world revision."""


def apply_replay_intervention(
    checkpoint: ReplayCheckpoint,
    intervention: ReplayIntervention | None,
) -> ReplayEnvironment:
    environment = ReplayEnvironment(
        checkpoint_id=checkpoint.checkpoint_id,
        context_manifest_ref=checkpoint.context_manifest_ref,
        context_handoff_mode=checkpoint.context_handoff_mode,
        policy_revision=checkpoint.runtime.policy_revision,
        sandbox_profile_revision=checkpoint.runtime.sandbox_profile_revision,
        capability_registry_revision=checkpoint.capability_registry_revision,
        skill_refs=list(checkpoint.skill_refs),
        budget_limits=dict(checkpoint.runtime.budget_limits),
        loop_topology=checkpoint.loop_topology,
        intervention=intervention,
    )
    if intervention is None:
        return environment
    if intervention.kind is ReplayInterventionKind.LOOP_TOPOLOGY:
        return environment.model_copy(
            update={"loop_topology": ReplayLoopTopology(intervention.replacement)}
        )
    if intervention.kind is ReplayInterventionKind.CONTEXT_HANDOFF:
        return environment.model_copy(update={"context_handoff_mode": intervention.replacement})
    if intervention.kind is ReplayInterventionKind.POLICY:
        return environment.model_copy(update={"policy_revision": intervention.replacement})
    if intervention.kind is ReplayInterventionKind.SANDBOX:
        return environment.model_copy(update={"sandbox_profile_revision": intervention.replacement})
    if intervention.kind is ReplayInterventionKind.SKILL:
        return environment.model_copy(update={"skill_refs": [intervention.replacement]})
    return environment.model_copy(update={"capability_registry_revision": intervention.replacement})


def evaluate_replay_protocol(
    expectation: ReplayExpectation,
    observation: ReplayObservation,
) -> ReplayProtocolResult:
    failures: list[str] = []
    if (
        expectation.expected_task_status is not None
        and observation.task_status != expectation.expected_task_status
    ):
        failures.append(
            "task_status_mismatch:"
            f"expected={expectation.expected_task_status}:actual={observation.task_status}"
        )
    event_types = set(observation.event_types)
    for required in expectation.required_event_types:
        if required not in event_types:
            failures.append(f"required_event_missing:{required}")
    for forbidden in expectation.forbidden_event_types:
        if forbidden in event_types:
            failures.append(f"forbidden_event_present:{forbidden}")
    if (
        expectation.expected_stop_reason is not None
        and observation.stop_reason != expectation.expected_stop_reason
    ):
        failures.append(
            "stop_reason_mismatch:"
            f"expected={expectation.expected_stop_reason}:actual={observation.stop_reason}"
        )
    if expectation.require_no_authority_violation and observation.authority_violations:
        failures.extend(f"authority_violation:{item}" for item in observation.authority_violations)
    return ReplayProtocolResult(passed=not failures, failures=failures)


def _checkpoint(
    *,
    snapshot: InvestigationSnapshot,
    trajectory_id: str,
    trajectory_ordinal: int,
    run: TaskRun,
    contract_ref: str,
    context_ref: str,
    context_role_ref: str,
    task_event_seq: int,
    runtime: ReplayRuntimeBinding,
    skill_refs: list[str],
    loop_topology: ReplayLoopTopology,
    context_handoff_mode: str,
) -> ReplayCheckpoint:
    payload: dict[str, object] = {
        "case_id": snapshot.case_id,
        "snapshot_id": snapshot.snapshot_id,
        "case_revision": snapshot.case_revision,
        "knowledge_revision": snapshot.knowledge_revision,
        "task_run_id": run.run_id,
        "task_contract_ref": contract_ref,
        "context_manifest_ref": context_ref,
        "task_event_seq": task_event_seq,
        "trajectory_id": trajectory_id,
        "trajectory_ordinal": trajectory_ordinal,
        "role_ref": context_role_ref,
        "runtime": runtime.model_dump(mode="json"),
        "capability_registry_revision": snapshot.capability_registry_revision,
        "model_revision": snapshot.model_revision,
        "prompt_assembly_revision": snapshot.prompt_assembly_revision,
        "skill_refs": skill_refs,
        "loop_topology": loop_topology.value,
        "source_availability_snapshot": snapshot.source_availability_snapshot,
        "context_handoff_mode": context_handoff_mode,
        "created_at": snapshot.created_at.isoformat(),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return ReplayCheckpoint(
        checkpoint_id=f"replay-checkpoint:{digest[:32]}",
        case_id=snapshot.case_id,
        snapshot_id=snapshot.snapshot_id,
        case_revision=snapshot.case_revision,
        knowledge_revision=snapshot.knowledge_revision,
        task_run_id=run.run_id,
        task_contract_ref=contract_ref,
        context_manifest_ref=context_ref,
        task_event_seq=task_event_seq,
        trajectory_id=trajectory_id,
        trajectory_ordinal=trajectory_ordinal,
        role_ref=context_role_ref,
        runtime=runtime,
        capability_registry_revision=snapshot.capability_registry_revision,
        model_revision=snapshot.model_revision,
        prompt_assembly_revision=snapshot.prompt_assembly_revision,
        skill_refs=skill_refs,
        loop_topology=loop_topology,
        source_availability_snapshot=dict(snapshot.source_availability_snapshot),
        context_handoff_mode=context_handoff_mode,
        created_at=snapshot.created_at,
    )
