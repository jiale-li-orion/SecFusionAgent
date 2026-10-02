from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, JsonValue, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from apps.task_admission import create_task_contract_service
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
from packages.reasoning.storage import DecisionResultStore
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.loader import load_runtime_policy
from packages.shared.config import Settings
from packages.task_runtime.admission import TaskAdmissionRequest, TaskIntentParser
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskIntent,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run, transition_task_run


class DecisionExecutionCoordinate(BaseModel):
    task_run_id: str
    execution_id: str
    budget_ref: str


async def open_case_decision_execution(
    session: AsyncSession,
    *,
    settings: Settings,
    state: InvestigationState,
    principal: str,
    request_id: str,
    surface: str,
    timeout_seconds: float | None = None,
) -> DecisionExecutionCoordinate:
    timeout = float(timeout_seconds or settings.model_timeout_seconds)
    policy = load_runtime_policy(settings.runtime_policy_path)
    intent = TaskIntentParser().parse(
        raw_request=state.goal,
        trigger_ref=f"{surface}:{request_id}",
        candidate_task_kind=TaskKind.LOOKUP,
        candidate_targets=list(state.targets),
        requested_output={"result_type": "DecisionResult"},
        requested_actions=["answer_question"],
    )
    admission = await create_task_contract_service(policy).admit(
        TaskAdmissionRequest(
            intent=intent,
            principal=principal,
            policy_revision=policy.policy_revision,
            binding_context={
                "question": state.goal,
                "target_object_ids": cast(JsonValue, list(state.targets)),
            },
        )
    )
    run_id = str(uuid4())
    execution_id = f"execution:{run_id}"
    budget_ref = f"budget:{run_id}"
    evidence_refs = sorted(
        {
            ref
            for group in (
                state.confirmed,
                state.tentative,
                state.conflicts,
                state.unknowns,
                state.hypotheses,
            )
            for item in group
            for ref in item.evidence_refs
            if ref.startswith("evidence:")
        }
    )
    manifest = ContextManifest(
        context_id=f"context:{run_id}",
        context_revision=1,
        task_contract_ref=(
            f"{admission.contract.task_contract_id}@{admission.contract.contract_revision}"
        ),
        role_ref="DecisionRole@1",
        case_ref=state.case_id,
        knowledge_revision=state.last_world_revision,
        investigation_state_ref=f"case:{state.case_id}@{state.case_revision}",
        evidence_refs=evidence_refs,
        object_refs=list(state.targets),
        policy_context_ref=f"policy-context:{policy.policy_revision}",
        capability_envelope_ref="capability:case-decision:local-read-v1",
        budget_ref=budget_ref,
    )
    await create_task_run(
        session,
        contract=admission.contract,
        manifest=manifest,
        role=canonical_roles()["DecisionRole"],
        execution_envelope_ref=execution_id,
        stream_name=settings.task_event_stream_name,
        case_id=state.case_id,
        run_id=run_id,
        producer=surface,
    )
    await BudgetGovernor().create_account(
        session,
        account_id=budget_ref,
        task_run_id=run_id,
        limits=BudgetLimits(
            quantities={
                "wall_seconds": Decimal(str(timeout)),
                "agent_turns": Decimal(1),
                "tool_calls": Decimal(0),
            }
        ),
    )
    await ExecutionRunService().create(
        session,
        ExecutionEnvelope(
            execution_id=execution_id,
            task_contract_id=admission.contract.task_contract_id,
            task_run_id=run_id,
            case_id=state.case_id,
            role_revision="DecisionRole@1",
            context_manifest_revision=1,
            execution_profile=ExecutionProfile.DIRECT,
            capability_scope=[],
            deadline_at=datetime.now(UTC) + timedelta(seconds=timeout),
            budget_ref=budget_ref,
            policy_revision=policy.policy_revision,
            identity_scope=["public"],
            network_policy="local-only",
            side_effect_policy="read-only",
            sandbox_profile_revision="none@1",
            trace_context={"request_id": request_id, "surface": surface},
        ),
    )
    await transition_task_run(
        session,
        run_id=run_id,
        target=TaskRunStatus.QUEUED,
        payload_ref=f"queue:{surface}",
        idempotency_key=f"{surface}-queued:{run_id}",
        stream_name=settings.task_event_stream_name,
        producer=surface,
    )
    await transition_task_run(
        session,
        run_id=run_id,
        target=TaskRunStatus.RUNNING,
        payload_ref="role:DecisionRole@1",
        idempotency_key=f"{surface}-running:{run_id}",
        stream_name=settings.task_event_stream_name,
        producer=surface,
    )
    await ExecutionRunService().start(session, execution_id)
    return DecisionExecutionCoordinate(
        task_run_id=run_id,
        execution_id=execution_id,
        budget_ref=budget_ref,
    )


async def finish_case_decision_execution(
    session: AsyncSession,
    *,
    settings: Settings,
    coordinate: DecisionExecutionCoordinate,
    result_ref: str,
    stop_reason: str,
    status: TaskRunStatus = TaskRunStatus.COMPLETED,
    surface: str,
) -> None:
    await ExecutionRunService().finish(
        session,
        coordinate.execution_id,
        status=("completed" if status is TaskRunStatus.COMPLETED else "failed"),
        stop_reason=stop_reason,
    )
    await transition_task_run(
        session,
        run_id=coordinate.task_run_id,
        target=status,
        payload_ref=result_ref,
        idempotency_key=f"{surface}-{status.value}:{coordinate.task_run_id}",
        stream_name=settings.task_event_stream_name,
        producer=surface,
        result_ref=result_ref if status is TaskRunStatus.COMPLETED else None,
        stop_reason=stop_reason,
    )


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
        result_store: DecisionResultStore | None = None,
    ) -> None:
        self._decision = decision_service or DecisionService()
        self._state = state_service or InvestigationStateService()
        self._results = result_store or DecisionResultStore()
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
        await self._results.persist(session, result)
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
        return await self.commit_proposal(
            session,
            state=state,
            proposal=proposal,
            citation_sources=citation_sources,
        )

    async def commit_proposal(
        self,
        session: AsyncSession,
        *,
        state: InvestigationState,
        proposal: DecisionDraft | ContinuationRequest,
        citation_sources: list[CitationSource],
    ) -> DecisionRuntimeOutcome:
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
