from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field, JsonValue

from packages.investigation.state.continuation import ContinuationRequest
from packages.investigation.state.contracts import EvidenceNeedContract, InvestigationState
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionConclusion, DecisionDraft
from packages.shared.model_provider import ModelProvider, StructuredModelRequest


class DecisionModelActionKind(StrEnum):
    FINAL = "final"
    CONTINUE = "continue"


class FinalDecisionProposal(BaseModel):
    kind: Literal[DecisionModelActionKind.FINAL] = DecisionModelActionKind.FINAL
    conclusions: list[DecisionConclusion] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    answer_payload: dict[str, JsonValue] = Field(default_factory=dict)
    stop_reason: str


class ContinuationProposal(BaseModel):
    kind: Literal[DecisionModelActionKind.CONTINUE] = DecisionModelActionKind.CONTINUE
    proposition_or_question: str
    purpose: str
    target_objects: list[str] = Field(default_factory=list)
    evidence_contract: EvidenceNeedContract = Field(default_factory=EvidenceNeedContract)
    preferred_source_roles: list[str] = Field(default_factory=list)
    freshness_requirement: dict[str, JsonValue] = Field(default_factory=dict)
    priority: int = Field(default=50, ge=0, le=100)
    reason: str


DecisionModelAction = Annotated[
    FinalDecisionProposal | ContinuationProposal,
    Field(discriminator="kind"),
]


class DecisionPlannerResponse(BaseModel):
    action: DecisionModelAction


class ModelDecisionPlanner:
    PROMPT_REVISION = "decision-model-v1"

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    async def plan(
        self,
        state: InvestigationState,
        *,
        citation_sources: list[CitationSource],
        runtime_metadata: dict[str, JsonValue] | None = None,
    ) -> DecisionDraft | ContinuationRequest:
        metadata: dict[str, JsonValue] = {
            "model_purpose": "m6.decision",
            "prompt_revision": self.PROMPT_REVISION,
            "request_owner_ref": f"case:{state.case_id}",
            "planner": self.PROMPT_REVISION,
            "model_provider": f"{self._provider.name}@{self._provider.version}",
            "case_id": state.case_id,
            "case_revision": state.case_revision,
        }
        if runtime_metadata:
            metadata.update(runtime_metadata)
        request = StructuredModelRequest(
            system_instruction=(
                "You are the M6 Decision Runtime. Read only the supplied M4 InvestigationState. "
                "Do not invent tools, EvidenceNeed IDs, Case revisions, or evidence. "
                "Facts may cite only evidence_refs already present in confirmed state. "
                "For a fact conclusion, copy the statement exactly from one confirmed "
                "InvestigationState proposition and cite evidence_refs from that same item. "
                "Inferences must preserve "
                "their support. If the current state cannot support a defensible answer, return a "
                "continuation proposal describing the evidence gap instead of guessing."
            ),
            data={
                "investigation_state": cast(JsonValue, state.model_dump(mode="json")),
                "citation_sources": cast(
                    JsonValue,
                    [item.model_dump(mode="json") for item in citation_sources],
                ),
            },
            metadata=metadata,
        )
        response = await self._provider.generate_structured(request, DecisionPlannerResponse)
        action = response.action
        if isinstance(action, FinalDecisionProposal):
            return DecisionDraft(
                case_id=state.case_id,
                case_revision=state.case_revision,
                conclusions=action.conclusions,
                conflicts=action.conflicts,
                unknowns=action.unknowns,
                assumptions=action.assumptions,
                answer_payload=action.answer_payload,
                stop_reason=action.stop_reason,
                model_prompt_revision=self.PROMPT_REVISION,
            )
        return ContinuationRequest(
            request_id=_continuation_request_id(state, action),
            case_id=state.case_id,
            base_case_revision=state.case_revision,
            proposition_or_question=action.proposition_or_question,
            purpose=action.purpose,
            target_objects=action.target_objects,
            evidence_contract=action.evidence_contract,
            preferred_source_roles=action.preferred_source_roles,
            freshness_requirement=action.freshness_requirement,
            priority=action.priority,
            reason=action.reason,
        )


def _continuation_request_id(
    state: InvestigationState,
    proposal: ContinuationProposal,
) -> str:
    payload = {
        "case_id": state.case_id,
        "case_revision": state.case_revision,
        "proposal": proposal.model_dump(mode="json"),
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return f"continuation:{digest[:32]}"
