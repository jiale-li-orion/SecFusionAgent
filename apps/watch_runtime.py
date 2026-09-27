from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.runtime.watch import (
    WatchWakeAdmission,
    WatchWakeDisposition,
)
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecisionPoint,
    PolicyRequest,
    obligations_satisfied,
)
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import ContextManifest, ExecutionProfile, TaskContract


class RuntimeWatchWakeAdmission:
    """Compose WATCH policy, budget, and execution controls outside Investigation domain."""

    def __init__(
        self,
        policy_engine: StaticPolicyEngine,
        *,
        budget_governor: BudgetGovernor | None = None,
        execution_service: ExecutionRunService | None = None,
        episode_timeout_seconds: int = 300,
        fulfilled_obligation_kinds: set[str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if episode_timeout_seconds <= 0:
            raise ValueError("episode_timeout_seconds must be positive")
        self._policy = policy_engine
        self._budget = budget_governor or BudgetGovernor(now=now)
        self._execution = execution_service or ExecutionRunService(now=now)
        self._episode_timeout_seconds = episode_timeout_seconds
        self._fulfilled_obligation_kinds = set(fulfilled_obligation_kinds or set())
        self._now = now or (lambda: datetime.now(UTC))

    async def admit(
        self,
        session: AsyncSession,
        *,
        contract: TaskContract,
        template_run_id: str,
        template_execution_envelope_ref: str,
        previous_context: ContextManifest,
        case_id: str,
        trigger_ref: str,
        run_id: str,
        world_revision: int,
    ) -> WatchWakeAdmission:
        if self._policy.policy_revision != contract.policy_revision:
            return WatchWakeAdmission(
                allowed=False,
                denial_reason=WatchWakeDisposition.POLICY_INDETERMINATE,
                policy_authorization=Authorization.INDETERMINATE.value,
            )

        request = PolicyRequest(
            decision_point=PolicyDecisionPoint.WATCH_RESUME,
            principal=contract.principal,
            action="resume_watch",
            resource=f"case:{case_id}",
            context={
                "task_contract_id": contract.task_contract_id,
                "task_run_id": run_id,
                "case_id": case_id,
                "template_run_id": template_run_id,
                "trigger_ref": trigger_ref,
                "world_revision": world_revision,
            },
        )
        decision = self._policy.evaluate(request)
        decision_ref = self._policy.decision_ref(request, decision)
        if decision.authorization is not Authorization.PERMIT:
            denial = (
                WatchWakeDisposition.POLICY_INDETERMINATE
                if decision.authorization is Authorization.INDETERMINATE
                else WatchWakeDisposition.POLICY_DENIED
            )
            return WatchWakeAdmission(
                allowed=False,
                denial_reason=denial,
                policy_decision_ref=decision_ref,
                policy_authorization=decision.authorization.value,
            )
        if not obligations_satisfied(
            decision,
            fulfilled_obligation_kinds=self._fulfilled_obligation_kinds,
        ):
            return WatchWakeAdmission(
                allowed=False,
                denial_reason=WatchWakeDisposition.POLICY_OBLIGATION_UNSATISFIED,
                policy_decision_ref=decision_ref,
                policy_authorization=decision.authorization.value,
            )

        template_budget = await self._budget.snapshot(session, previous_context.budget_ref)
        template_execution = await self._execution.get(
            session,
            template_execution_envelope_ref,
        )
        budget_ref = f"budget:{run_id}"
        execution_ref = f"execution:{run_id}"
        capability_ref = f"capability:watch:{run_id}"
        await self._budget.create_account(
            session,
            account_id=budget_ref,
            task_run_id=run_id,
            limits=BudgetLimits(quantities=dict(template_budget.limits)),
        )
        await self._execution.create(
            session,
            ExecutionEnvelope(
                execution_id=execution_ref,
                task_contract_id=contract.task_contract_id,
                task_run_id=run_id,
                case_id=case_id,
                role_revision=previous_context.role_ref,
                context_manifest_revision=1,
                execution_profile=ExecutionProfile.WATCH,
                capability_scope=list(template_execution.capability_scope),
                deadline_at=self._now() + timedelta(seconds=self._episode_timeout_seconds),
                budget_ref=budget_ref,
                policy_revision=contract.policy_revision,
                identity_scope=list(template_execution.identity_scope),
                network_policy=template_execution.network_policy,
                side_effect_policy=template_execution.side_effect_policy,
                sandbox_profile_revision=template_execution.sandbox_profile_revision,
                trace_context={
                    **template_execution.trace_context,
                    "watch_trigger_ref": trigger_ref,
                    "watch_previous_run_id": template_run_id,
                    "watch_policy_decision_ref": decision_ref,
                },
            ),
        )
        return WatchWakeAdmission(
            allowed=True,
            policy_decision_ref=decision_ref,
            policy_authorization=decision.authorization.value,
            budget_ref=budget_ref,
            execution_envelope_ref=execution_ref,
            capability_envelope_ref=capability_ref,
        )
