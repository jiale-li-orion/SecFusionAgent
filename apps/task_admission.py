from __future__ import annotations

from packages.enrichment.runtime.admission import EnrichmentTaskContractCompiler
from packages.investigation.runtime.admission import InvestigationTaskContractCompiler
from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecisionPoint,
    PolicyRequest,
    obligations_satisfied,
)
from packages.runtime.policy.engine import StaticPolicyEngine
from packages.task_runtime.admission import (
    TaskAdmissionAuthorization,
    TaskContractService,
)
from packages.task_runtime.contracts.models import TaskContract, TaskIntent, TaskKind


class RuntimeTaskAdmissionAuthorizer:
    def __init__(
        self,
        policy: StaticPolicyEngine,
        *,
        fulfilled_obligation_kinds: set[str] | None = None,
    ) -> None:
        self._policy = policy
        self._fulfilled_obligation_kinds = set(fulfilled_obligation_kinds or set())

    async def authorize(
        self,
        *,
        intent_ref: str,
        intent: TaskIntent,
        candidate_contract: TaskContract,
    ) -> TaskAdmissionAuthorization:
        if self._policy.policy_revision != candidate_contract.policy_revision:
            return TaskAdmissionAuthorization(
                allowed=False,
                authorization=Authorization.INDETERMINATE.value,
                denial_reason="policy_revision_mismatch",
            )
        request = PolicyRequest(
            decision_point=PolicyDecisionPoint.TASK_ADMISSION,
            principal=candidate_contract.principal,
            action=f"admit_{candidate_contract.task_kind.value}",
            resource=f"task-kind:{candidate_contract.task_kind.value}",
            context={
                "intent_ref": intent_ref,
                "task_contract_id": candidate_contract.task_contract_id,
                "contract_revision": candidate_contract.contract_revision,
                "effect_ceiling": candidate_contract.effect_ceiling.value,
                "target_resources": list(candidate_contract.target_resources),
                "trigger_ref": intent.trigger_ref,
            },
        )
        decision = self._policy.evaluate(request)
        decision_ref = self._policy.decision_ref(request, decision)
        if decision.authorization is not Authorization.PERMIT:
            return TaskAdmissionAuthorization(
                allowed=False,
                authorization=decision.authorization.value,
                policy_decision_ref=decision_ref,
                denial_reason=f"policy_{decision.authorization.value}",
            )
        if not obligations_satisfied(
            decision,
            fulfilled_obligation_kinds=self._fulfilled_obligation_kinds,
        ):
            return TaskAdmissionAuthorization(
                allowed=False,
                authorization=decision.authorization.value,
                policy_decision_ref=decision_ref,
                denial_reason="policy_obligation_unsatisfied",
            )
        return TaskAdmissionAuthorization(
            allowed=True,
            authorization=decision.authorization.value,
            policy_decision_ref=decision_ref,
            fulfilled_obligations=sorted(self._fulfilled_obligation_kinds),
        )


def create_task_contract_service(policy: StaticPolicyEngine) -> TaskContractService:
    investigation_kinds = (
        TaskKind.VERIFY_VERSION_FIX,
        TaskKind.RESOLVE_CONFLICT,
        TaskKind.INVESTIGATE_RELATION,
        TaskKind.INVESTIGATE_INCIDENT,
        TaskKind.WATCH_INCIDENT,
        TaskKind.ASSESS_NORMATIVE_APPLICABILITY,
        TaskKind.OBSERVE_LIVE_ASSET,
    )
    return TaskContractService(
        [
            EnrichmentTaskContractCompiler(),
            *(InvestigationTaskContractCompiler(kind) for kind in investigation_kinds),
        ],
        authorizer=RuntimeTaskAdmissionAuthorizer(policy),
    )
