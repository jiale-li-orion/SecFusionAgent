from __future__ import annotations

from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from packages.investigation.state.continuation import (
    ContinuationGate,
    ContinuationRequest,
)
from packages.investigation.state.contracts import DecisionCommit, InvestigationState
from packages.investigation.state.service import (
    DecisionCommitResult,
    EvidenceNeedOpenResult,
    InvestigationStateService,
)
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionDraft, DecisionResult, DecisionService
from packages.reasoning.model import ModelDecisionPlanner
from packages.task_runtime.contracts.models import TaskIntent


class ContinuationIntentEnvelope(BaseModel):
    intent: TaskIntent
    request: ContinuationRequest


class DecisionRuntimeOutcome(BaseModel):
    decision: DecisionResult | None = None
    decision_commit: DecisionCommitResult | None = None
    continuation_intent: TaskIntent | None = None
    continuation: EvidenceNeedOpenResult | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> DecisionRuntimeOutcome:
        has_decision = self.decision is not None or self.decision_commit is not None
        if (self.decision is None) != (self.decision_commit is None):
            raise ValueError("decision and decision_commit must appear together")
        if has_decision == (self.continuation is not None):
            raise ValueError("DecisionRuntimeOutcome requires decision or continuation")
        if self.continuation is not None and self.continuation_intent is None:
            raise ValueError("continuation result requires TaskIntent")
        if has_decision and self.continuation_intent is not None:
            raise ValueError("decision outcome cannot carry continuation TaskIntent")
        return self


class DecisionRuntime:
    """Compose read-only M6 reasoning with M4-owned write gates."""

    def __init__(
        self,
        *,
        decision_service: DecisionService | None = None,
        state_service: InvestigationStateService | None = None,
    ) -> None:
        self._decision = decision_service or DecisionService()
        self._state = state_service or InvestigationStateService()
        self._continuation = ContinuationGate(self._state)

    async def finalize(
        self,
        session: AsyncSession,
        *,
        state: InvestigationState,
        draft: DecisionDraft,
        citation_sources: list[CitationSource],
    ) -> tuple[DecisionResult, DecisionCommitResult]:
        result = self._decision.decide(
            state,
            draft,
            citation_sources=citation_sources,
        )
        committed = await self._state.commit_decision(
            session,
            DecisionCommit(
                decision_id=result.decision_id,
                case_id=result.case_id,
                base_case_revision=result.case_revision,
                decision=result.model_dump(mode="json"),
            ),
        )
        return result, committed

    async def continue_investigation(
        self,
        session: AsyncSession,
        *,
        state: InvestigationState,
        request: ContinuationRequest,
    ) -> EvidenceNeedOpenResult:
        validated = self._decision.request_continuation(state, request)
        envelope = self.continuation_intent(validated)
        return await self.accept_continuation_intent(session, envelope)

    def continuation_intent(self, request: ContinuationRequest) -> ContinuationIntentEnvelope:
        return ContinuationIntentEnvelope(
            intent=TaskIntent(
                trigger_ref=request.request_id,
                parsed_identifiers=[request.case_id, *request.target_objects],
                candidate_targets=list(request.target_objects),
                requested_output={
                    "continuation_request": request.model_dump(mode="json"),
                },
                requested_actions=["open_evidence_need"],
            ),
            request=request,
        )

    async def accept_continuation_intent(
        self,
        session: AsyncSession,
        envelope: ContinuationIntentEnvelope,
    ) -> EvidenceNeedOpenResult:
        request = envelope.request
        intent = envelope.intent
        if intent.trigger_ref != request.request_id:
            raise ValueError("Continuation TaskIntent trigger_ref mismatch")
        if intent.candidate_targets != request.target_objects:
            raise ValueError("Continuation TaskIntent target mismatch")
        encoded = intent.requested_output.get("continuation_request")
        if encoded != request.model_dump(mode="json"):
            raise ValueError("Continuation TaskIntent payload mismatch")
        if intent.requested_actions != ["open_evidence_need"]:
            raise ValueError("Continuation TaskIntent action mismatch")
        return await self._continuation.accept(session, request)

    async def execute(
        self,
        session: AsyncSession,
        *,
        state: InvestigationState,
        planner: ModelDecisionPlanner,
        citation_sources: list[CitationSource],
    ) -> DecisionRuntimeOutcome:
        proposal = await planner.plan(state, citation_sources=citation_sources)
        if isinstance(proposal, DecisionDraft):
            decision, committed = await self.finalize(
                session,
                state=state,
                draft=proposal,
                citation_sources=citation_sources,
            )
            return DecisionRuntimeOutcome(
                decision=decision,
                decision_commit=committed,
            )
        validated = self._decision.request_continuation(state, proposal)
        envelope = self.continuation_intent(validated)
        continuation = await self.accept_continuation_intent(session, envelope)
        return DecisionRuntimeOutcome(
            continuation_intent=envelope.intent,
            continuation=continuation,
        )
