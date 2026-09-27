from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.replay import (
    ReplayCheckpointCapture,
    ReplayCheckpointService,
    ReplayLoopTopology,
    ReplayRuntimeBinding,
)
from packages.runtime.budget import BudgetGovernor
from packages.runtime.execution.service import ExecutionRunService
from packages.task_runtime.storage.service import get_task_run


class ReplayCaptureRuntime:
    """Bind investigation checkpoint refs to immutable runtime control-plane state."""

    def __init__(
        self,
        *,
        checkpoint_service: ReplayCheckpointService | None = None,
        execution_service: ExecutionRunService | None = None,
        budget_governor: BudgetGovernor | None = None,
    ) -> None:
        self._checkpoints = checkpoint_service or ReplayCheckpointService()
        self._execution = execution_service or ExecutionRunService()
        self._budget = budget_governor or BudgetGovernor()

    async def capture(
        self,
        session: AsyncSession,
        *,
        snapshot_id: str,
        trajectory_id: str,
        task_run_id: str,
        task_event_seq: int | None = None,
        skill_refs: list[str] | None = None,
        loop_topology: ReplayLoopTopology,
        context_handoff_mode: str = "reference",
    ) -> ReplayCheckpointCapture:
        run = await get_task_run(session, task_run_id)
        envelope = await self._execution.get(session, run.execution_envelope_ref)
        budget = await self._budget.snapshot(session, envelope.budget_ref)
        if envelope.task_run_id != run.run_id:
            raise ValueError("ExecutionEnvelope TaskRun mismatch during replay capture")
        if budget.account_id != envelope.budget_ref:
            raise ValueError("Budget snapshot does not match ExecutionEnvelope")
        runtime = ReplayRuntimeBinding(
            task_run_id=run.run_id,
            execution_envelope_ref=envelope.execution_id,
            execution_profile=envelope.execution_profile.value,
            policy_revision=envelope.policy_revision,
            capability_scope=list(envelope.capability_scope),
            identity_scope=list(envelope.identity_scope),
            network_policy=envelope.network_policy,
            side_effect_policy=envelope.side_effect_policy,
            sandbox_profile_revision=envelope.sandbox_profile_revision,
            budget_ref=envelope.budget_ref,
            budget_limits=_decimal_map(budget.limits),
            budget_reserved=_decimal_map(budget.reserved),
            budget_committed=_decimal_map(budget.committed),
        )
        return await self._checkpoints.capture(
            session,
            snapshot_id=snapshot_id,
            trajectory_id=trajectory_id,
            task_run_id=task_run_id,
            runtime=runtime,
            task_event_seq=task_event_seq,
            skill_refs=skill_refs,
            loop_topology=loop_topology,
            context_handoff_mode=context_handoff_mode,
        )


def _decimal_map(values: dict[str, Decimal]) -> dict[str, str]:
    return {key: format(value.normalize(), "f") for key, value in values.items()}
