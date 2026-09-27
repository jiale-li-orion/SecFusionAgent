from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue, model_validator


class PolicyDecisionPoint(StrEnum):
    TASK_ADMISSION = "task_admission"
    TASK_DELEGATION = "task_delegation"
    CAPABILITY_VISIBILITY = "capability_visibility"
    CAPABILITY_INVOCATION = "capability_invocation"
    CREDENTIAL_ISSUANCE = "credential_issuance"
    NETWORK_EGRESS = "network_egress"
    SANDBOX_SELECTION = "sandbox_selection"
    SIDE_EFFECT_COMMIT = "side_effect_commit"
    OBSERVATION_PROMOTION = "observation_promotion"
    STATE_PATCH_COMMIT = "state_patch_commit"
    CHILD_EXECUTION = "child_execution"
    WATCH_RESUME = "watch_resume"


class Authorization(StrEnum):
    PERMIT = "permit"
    DENY = "deny"
    INDETERMINATE = "indeterminate"


class PolicyObligation(BaseModel):
    kind: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_kind(self) -> PolicyObligation:
        if not self.kind.strip():
            raise ValueError("PolicyObligation kind cannot be empty")
        return self


class PolicyRequest(BaseModel):
    decision_point: PolicyDecisionPoint
    principal: str
    action: str
    resource: str
    context: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_request(self) -> PolicyRequest:
        if not self.principal.strip() or not self.action.strip() or not self.resource.strip():
            raise ValueError("PolicyRequest principal/action/resource cannot be empty")
        if "task_contract_id" not in self.context or "task_run_id" not in self.context:
            raise ValueError("PolicyRequest context requires task_contract_id and task_run_id")
        return self


class PolicyDecision(BaseModel):
    authorization: Authorization
    constraints: list[PolicyObligation] = Field(default_factory=list)
    obligations: list[PolicyObligation] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)
    matched_policy_ids: list[str] = Field(default_factory=list)
    determining_policy_ids: list[str] = Field(default_factory=list)
    policy_revision: str
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_revision(self) -> PolicyDecision:
        if not self.policy_revision.strip():
            raise ValueError("PolicyDecision policy_revision cannot be empty")
        return self


def obligations_satisfied(
    decision: PolicyDecision,
    *,
    fulfilled_obligation_kinds: set[str],
) -> bool:
    if decision.authorization is not Authorization.PERMIT:
        return False
    required = {item.kind for item in decision.obligations}
    return required <= fulfilled_obligation_kinds


def combine_deny_overrides(
    decisions: list[PolicyDecision],
    *,
    policy_revision: str,
) -> PolicyDecision:
    """Combine PDP results with implicit deny and explicit deny precedence.

    This is the v1 authorization core described by the design cache: no permit
    means deny, and any explicit deny overrides permits. An indeterminate
    evaluation remains indeterminate when no deny exists so enforcement can
    fail closed without losing the evaluation failure signal.
    """

    matched = sorted({item for decision in decisions for item in decision.matched_policy_ids})
    denies = [item for item in decisions if item.authorization is Authorization.DENY]
    if denies:
        return PolicyDecision(
            authorization=Authorization.DENY,
            advice=[item for decision in decisions for item in decision.advice],
            matched_policy_ids=matched,
            determining_policy_ids=sorted(
                {item for decision in denies for item in decision.determining_policy_ids}
            ),
            policy_revision=policy_revision,
        )

    indeterminate = [
        item for item in decisions if item.authorization is Authorization.INDETERMINATE
    ]
    if indeterminate:
        return PolicyDecision(
            authorization=Authorization.INDETERMINATE,
            advice=[item for decision in decisions for item in decision.advice],
            matched_policy_ids=matched,
            determining_policy_ids=sorted(
                {item for decision in indeterminate for item in decision.determining_policy_ids}
            ),
            policy_revision=policy_revision,
        )

    permits = [item for item in decisions if item.authorization is Authorization.PERMIT]
    if permits:
        return PolicyDecision(
            authorization=Authorization.PERMIT,
            constraints=[item for decision in permits for item in decision.constraints],
            obligations=[item for decision in permits for item in decision.obligations],
            advice=[item for decision in decisions for item in decision.advice],
            matched_policy_ids=matched,
            determining_policy_ids=sorted(
                {item for decision in permits for item in decision.determining_policy_ids}
            ),
            policy_revision=policy_revision,
        )

    return PolicyDecision(
        authorization=Authorization.DENY,
        advice=["implicit_deny"],
        matched_policy_ids=matched,
        determining_policy_ids=[],
        policy_revision=policy_revision,
    )
