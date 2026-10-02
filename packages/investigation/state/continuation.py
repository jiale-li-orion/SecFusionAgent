from __future__ import annotations

import json
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field, JsonValue, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.state.contracts import EvidenceNeedContract
from packages.investigation.state.service import EvidenceNeedOpenResult, InvestigationStateService


class ContinuationRequest(BaseModel):
    request_id: str
    case_id: str
    base_case_revision: int = Field(ge=0)
    proposition_or_question: str
    purpose: str = Field(min_length=1, max_length=128)
    target_objects: list[str] = Field(default_factory=list)
    evidence_contract: EvidenceNeedContract = Field(default_factory=EvidenceNeedContract)
    preferred_source_roles: list[str] = Field(default_factory=list)
    freshness_requirement: dict[str, JsonValue] = Field(default_factory=dict)
    priority: int = Field(default=50, ge=0, le=100)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_request(self) -> ContinuationRequest:
        for value, label in (
            (self.request_id, "request_id"),
            (self.case_id, "case_id"),
            (self.proposition_or_question, "proposition_or_question"),
            (self.purpose, "purpose"),
            (self.reason, "reason"),
        ):
            if not value.strip():
                raise ValueError(f"ContinuationRequest {label} cannot be empty")
        if len(set(self.target_objects)) != len(self.target_objects):
            raise ValueError("ContinuationRequest target_objects must be unique")
        return self


class ContinuationGate:
    """M4-owned validation/dedupe boundary for M6 evidence-gap requests."""

    def __init__(self, state_service: InvestigationStateService | None = None) -> None:
        self._state = state_service or InvestigationStateService()

    async def accept(
        self,
        session: AsyncSession,
        request: ContinuationRequest,
    ) -> EvidenceNeedOpenResult:
        state = await self._state.get_state(session, request.case_id)
        if not set(request.target_objects) <= set(state.targets):
            raise ValueError("ContinuationRequest target_objects escape Investigation Case")
        need_id = continuation_need_id(request)
        return await self._state.open_evidence_need(
            session,
            case_id=request.case_id,
            base_case_revision=request.base_case_revision,
            need_id=need_id,
            proposition_or_question=request.proposition_or_question,
            purpose=request.purpose,
            target_objects=request.target_objects,
            evidence_contract=request.evidence_contract,
            preferred_source_roles=request.preferred_source_roles,
            freshness_requirement={
                key: value for key, value in request.freshness_requirement.items()
            },
            priority=request.priority,
            writer="M4ContinuationGate",
            reason_code="m6_continuation",
        )


def continuation_need_id(request: ContinuationRequest) -> str:
    payload = {
        "case_id": request.case_id,
        "proposition_or_question": " ".join(request.proposition_or_question.split()),
        "purpose": request.purpose.strip(),
        "target_objects": sorted(request.target_objects),
        "evidence_contract": request.evidence_contract.model_dump(mode="json"),
        "preferred_source_roles": sorted(set(request.preferred_source_roles)),
        "freshness_requirement": request.freshness_requirement,
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"secfusion:continuation-need:{digest}"))
