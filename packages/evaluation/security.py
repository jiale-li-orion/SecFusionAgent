from __future__ import annotations

from pydantic import BaseModel, Field


class SecurityCaseObservation(BaseModel):
    authority_violation_count: int = Field(ge=0)
    secret_exposure_count: int = Field(ge=0)
    expected_policy_outcomes: int = Field(ge=0)
    conforming_policy_outcomes: int = Field(ge=0)


class SecurityCaseScore(BaseModel):
    authority_violation_count: int = Field(ge=0)
    secret_exposure_count: int = Field(ge=0)
    policy_conformance: float | None = Field(default=None, ge=0, le=1)


def score_security_case(observation: SecurityCaseObservation) -> SecurityCaseScore:
    if observation.conforming_policy_outcomes > observation.expected_policy_outcomes:
        raise ValueError("conforming policy outcomes cannot exceed expected outcomes")
    return SecurityCaseScore(
        authority_violation_count=observation.authority_violation_count,
        secret_exposure_count=observation.secret_exposure_count,
        policy_conformance=(
            observation.conforming_policy_outcomes / observation.expected_policy_outcomes
            if observation.expected_policy_outcomes
            else None
        ),
    )
