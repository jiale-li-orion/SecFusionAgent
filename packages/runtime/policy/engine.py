from __future__ import annotations

import json
from fnmatch import fnmatchcase
from hashlib import sha256

from pydantic import BaseModel, Field

from packages.runtime.policy.contracts import (
    Authorization,
    PolicyDecision,
    PolicyDecisionPoint,
    PolicyObligation,
    PolicyRequest,
    combine_deny_overrides,
)


class RuntimePolicyRule(BaseModel):
    policy_id: str
    policy_revision: str
    decision_points: list[PolicyDecisionPoint]
    principal_patterns: list[str] = Field(default_factory=lambda: ["*"])
    action_patterns: list[str] = Field(default_factory=lambda: ["*"])
    resource_patterns: list[str] = Field(default_factory=lambda: ["*"])
    authorization: Authorization | None = None
    constraints: list[PolicyObligation] = Field(default_factory=list)
    obligations: list[PolicyObligation] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)

    def matches(self, request: PolicyRequest) -> bool:
        return (
            request.decision_point in self.decision_points
            and _matches_any(request.principal, self.principal_patterns)
            and _matches_any(request.action, self.action_patterns)
            and _matches_any(request.resource, self.resource_patterns)
        )


class StaticPolicyEngine:
    def __init__(self, *, policy_revision: str, rules: list[RuntimePolicyRule]) -> None:
        if not policy_revision.strip():
            raise ValueError("policy_revision cannot be empty")
        self.policy_revision = policy_revision
        self._rules = tuple(rules)
        for rule in self._rules:
            if rule.policy_revision != policy_revision:
                raise ValueError("policy rule revision does not match engine revision")

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        matched = [rule for rule in self._rules if rule.matches(request)]
        authorization_decisions = [
            PolicyDecision(
                authorization=rule.authorization,
                matched_policy_ids=[rule.policy_id],
                determining_policy_ids=[rule.policy_id],
                policy_revision=self.policy_revision,
            )
            for rule in matched
            if rule.authorization is not None
        ]
        combined = combine_deny_overrides(
            authorization_decisions,
            policy_revision=self.policy_revision,
        )
        combined.matched_policy_ids = sorted({rule.policy_id for rule in matched})
        if combined.authorization is Authorization.PERMIT:
            combined.constraints = [item for rule in matched for item in rule.constraints]
            combined.obligations = [item for rule in matched for item in rule.obligations]
            combined.advice = [item for rule in matched for item in rule.advice]
        return combined

    def decision_ref(self, request: PolicyRequest, decision: PolicyDecision) -> str:
        digest = sha256(
            json.dumps(
                {
                    "request": request.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        return f"policy-decision:{self.policy_revision}:{digest[:32]}"


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for pattern in patterns)
