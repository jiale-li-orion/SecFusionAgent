from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, Field, JsonValue, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.command_idempotency import (
    claim_command,
    command_digest,
    complete_command,
)
from apps.application.commands.start_investigation import (
    ContinueInvestigationCommand,
    ContinueInvestigationUseCase,
    StartInvestigationCommand,
    StartInvestigationUseCase,
)
from apps.application.errors import (
    DeadlineExceededError,
    DependencyUnavailableError,
    LifecycleConflictError,
    ResourceNotFoundError,
)
from apps.application.queries.decision_sources import decision_citation_sources
from apps.application.queries.investigations import decision_view
from apps.application.question_facts import render_claim_fact, render_relation_fact
from apps.application.question_sessions import QuestionSessionContext, QuestionSessionStore
from apps.application.views.questions import QuestionResultView
from apps.task_admission import create_task_contract_service
from packages.intelligence.knowledge.read import (
    EvidenceRef,
    KnowledgeObjectView,
    get_object_by_id,
    get_vulnerability_by_cve,
)
from packages.intelligence.retrieval.contracts import RetrievedCandidate
from packages.intelligence.retrieval.operators import LexicalRetrievalOperator
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel
from packages.investigation.state.contracts import InvestigationState, InvestigationStateItem
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.reasoning.citation import CitationSource
from packages.reasoning.decision import DecisionDraft, DecisionService
from packages.reasoning.model import ModelDecisionPlanner
from packages.reasoning.storage import DecisionResultStore
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.loader import load_runtime_policy
from packages.runtime.retrieval import (
    RetrievalDisposition,
    RetrievalInvocationService,
    RetrievalRequestCoordinate,
)
from packages.shared.model_provider import ModelProvider
from packages.task_runtime.admission import TaskAdmissionRequest, TaskIntentParser
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskKind,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.service import create_task_run, transition_task_run

_QUESTION_SECOND_HOP_RELATION_TYPES = frozenset(
    {
        "belongs-to-repo",
        "merged-as",
        "head-commit",
        "has-parent-commit",
        "release-contains-commit",
    }
)
_QUESTION_MAX_DEVELOPMENT_TARGETS = 4
_QUESTION_MAX_SECOND_HOP_RELATIONS = 16


class AskQuestionCommand(BaseModel):
    principal: str
    request_id: str
    trace_id: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = None
    question: str = Field(min_length=1)
    cve_id: str | None = None
    object_id: str | None = None
    task_kind: TaskKind = TaskKind.LOOKUP
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    interactive_timeout_seconds: int = Field(default=5, ge=1, le=30)
    retrieval_limit: int = Field(default=8, ge=1, le=20)
    allow_wait: bool = True
    investigation_timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)

    @model_validator(mode="after")
    def validate_target(self) -> AskQuestionCommand:
        if self.cve_id and self.object_id:
            raise ValueError("cve_id and object_id are mutually exclusive")
        if self.task_kind is TaskKind.LOOKUP and not (
            self.cve_id or self.object_id or self.session_id
        ):
            raise ValueError("lookup question requires cve_id, object_id, or session_id")
        if self.task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE} and not (
            self.cve_id or self.object_id or self.session_id
        ):
            raise ValueError("investigation question requires cve_id, object_id, or session_id")
        if self.task_kind is TaskKind.ENRICHMENT:
            raise ValueError("enrichment is not a Product QA route")
        return self


class _QuestionContext(BaseModel):
    state: InvestigationState
    citation_sources: list[CitationSource] = Field(default_factory=list)
    case_ref: str | None = None
    investigation_state_ref: str | None = None
    object_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    retrieval_invocation_refs: list[str] = Field(default_factory=list)


class AskQuestionUseCase:
    def __init__(
        self,
        *,
        policy_path: Path,
        task_event_stream_name: str,
        model_provider: ModelProvider | None,
        retrieval: LexicalRetrievalOperator | None = None,
        budget_governor: BudgetGovernor | None = None,
        execution_service: ExecutionRunService | None = None,
        decision_store: DecisionResultStore | None = None,
        session_store: QuestionSessionStore | None = None,
        retrieval_invocations: RetrievalInvocationService | None = None,
        investigation_state_service: InvestigationStateService | None = None,
        model_payload_persistence: str | None = None,
    ) -> None:
        self._policy_path = policy_path
        self._stream_name = task_event_stream_name
        self._provider = model_provider
        self._retrieval = retrieval or LexicalRetrievalOperator()
        self._budget = budget_governor or BudgetGovernor()
        self._execution = execution_service or ExecutionRunService()
        self._decisions = decision_store or DecisionResultStore()
        self._sessions = session_store or QuestionSessionStore()
        self._retrieval_invocations = retrieval_invocations or RetrievalInvocationService()
        self._investigation_state = investigation_state_service or InvestigationStateService()
        self._model_payload_persistence = model_payload_persistence

    async def execute(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
    ) -> QuestionResultView:
        record, replay = await claim_command(
            session,
            principal=command.principal,
            operation="ask_question",
            key=command.idempotency_key,
            digest=command_digest(command.model_dump(
                mode="json", exclude={"principal", "request_id", "trace_id", "idempotency_key"}
            )),
        )
        if replay:
            assert record is not None and record.response_payload is not None
            return QuestionResultView.model_validate(record.response_payload)
        session_context = await self._sessions.resolve(
            session,
            session_id=command.session_id,
            principal=command.principal,
        )
        latest_investigation_turn = await self._sessions.latest_investigation_turn(
            session,
            session_id=command.session_id,
            principal=command.principal,
        )
        active_case_id = await _active_session_investigation_case_id(
            session,
            latest_investigation_turn.investigation_ref
            if latest_investigation_turn is not None
            else None,
        )
        if command.task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            if active_case_id is not None:
                if command.cve_id is not None or command.object_id is not None:
                    raise LifecycleConflictError(
                        "active investigation follow-up cannot rebind the session target",
                        context={"case_id": active_case_id},
                    )
                investigation = await self._continue_investigation(
                    session,
                    command,
                    case_id=active_case_id,
                )
                turn = await self._sessions.append_turn(
                    session,
                    session_id=session_context.session_id,
                    principal=command.principal,
                    request_id=command.request_id,
                    question=command.question,
                    task_kind=command.task_kind.value,
                    target_object_ids=investigation.target_object_ids,
                    knowledge_revision=await _current_knowledge_revision(session),
                    context_id=None,
                    decision_ref=None,
                    investigation_ref=f"case:{investigation.case_id}",
                )
                result = QuestionResultView(
                    request_id=command.request_id,
                    session_id=session_context.session_id,
                    turn_index=turn.turn_index,
                    mode="accepted",
                    execution_profile=investigation.execution_profile or "INVESTIGATE",
                    investigation=investigation,
                )
                complete_command(
                    record, f"{session_context.session_id}:{turn.turn_index}",
                    result.model_dump(mode="json"),
                )
                await session.commit()
                return result
        case_read_id = (
            active_case_id
            if command.task_kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}
            and command.cve_id is None
            and command.object_id is None
            else None
        )
        command = _bind_session_target(command, session_context)
        next_turn_index = (
            session_context.latest_turn.turn_index + 1 if session_context.latest_turn else 1
        )
        if command.task_kind not in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            investigation = await self._start_investigation(session, command, command.question)
            turn = await self._sessions.append_turn(
                session,
                session_id=session_context.session_id,
                principal=command.principal,
                request_id=command.request_id,
                question=command.question,
                task_kind=command.task_kind.value,
                target_object_ids=investigation.target_object_ids,
                knowledge_revision=await _current_knowledge_revision(session),
                context_id=None,
                decision_ref=None,
                investigation_ref=f"case:{investigation.case_id}",
            )
            result = QuestionResultView(
                request_id=command.request_id,
                session_id=session_context.session_id,
                turn_index=turn.turn_index,
                mode="accepted",
                execution_profile=investigation.execution_profile or "INVESTIGATE",
                investigation=investigation,
            )
            complete_command(
                record, f"{session_context.session_id}:{turn.turn_index}",
                result.model_dump(mode="json"),
            )
            await session.commit()
            return result
        if self._provider is None:
            raise DependencyUnavailableError("model provider is not configured")

        context = await self._load_context(
            session,
            command,
            session_context=session_context,
            turn_index=next_turn_index,
            active_case_id=case_read_id,
        )
        history_payload = await self._session_history_payload(session, session_context)
        run_id, execution_id, profile = await self._open_sync_runtime(
            session,
            command=command,
            context=context,
            session_context=session_context,
        )
        await session.commit()

        try:
            runtime_metadata: dict[str, JsonValue] = {
                "request_owner_ref": f"task-run:{run_id}",
                "task_run_id": run_id,
                "execution_id": execution_id,
                "budget_ref": f"budget:{run_id}",
                # Ordinary DIRECT/RETRIEVE questions remain lightweight. An
                # explicit session Case-read carries the real M4 Case FK.
                "case_id": context.state.case_id if context.case_ref else None,
                "product_request_id": command.request_id,
                "product_session_id": session_context.session_id,
                "product_turn_index": next_turn_index,
                "model_wall_seconds": command.interactive_timeout_seconds,
            }
            if self._model_payload_persistence is not None:
                runtime_metadata["model_payload_persistence"] = self._model_payload_persistence
            proposal = await ModelDecisionPlanner(self._provider).plan(
                context.state,
                citation_sources=context.citation_sources,
                session_context=history_payload,
                runtime_metadata=runtime_metadata,
            )
            if isinstance(proposal, DecisionDraft):
                decision = DecisionService().decide(
                    context.state,
                    proposal,
                    citation_sources=context.citation_sources,
                )
            else:
                proposal = DecisionService().request_continuation(context.state, proposal)
        except Exception as exc:
            stop_reason = (
                "question_deadline_exceeded"
                if isinstance(exc, TimeoutError)
                else "question_reasoning_failed"
            )
            async with session.begin():
                await self._execution.finish(
                    session,
                    execution_id,
                    status="failed",
                    stop_reason=stop_reason,
                )
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.FAILED,
                    payload_ref=f"task-run:{run_id}",
                    idempotency_key=f"question-failed:{run_id}",
                    stream_name=self._stream_name,
                    producer="product-question",
                    stop_reason=stop_reason,
                )
                if record is not None:
                    record.status = "failed"
                    record.response_ref = f"task-run:{run_id}"
            if isinstance(exc, TimeoutError):
                raise DeadlineExceededError(
                    "question reasoning exceeded the interactive time limit",
                    context={
                        "run_id": run_id,
                        "timeout_seconds": command.interactive_timeout_seconds,
                    },
                ) from exc
            raise

        if isinstance(proposal, DecisionDraft):
            async with session.begin():
                stored = await self._decisions.persist(session, decision)
                await self._execution.finish(
                    session,
                    execution_id,
                    status="completed",
                    stop_reason=decision.stop_reason,
                )
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.COMPLETED,
                    payload_ref=decision.decision_id,
                    idempotency_key=f"question-completed:{run_id}",
                    stream_name=self._stream_name,
                    producer="product-question",
                    result_ref=decision.decision_id,
                    stop_reason=decision.stop_reason,
                )
                turn = await self._sessions.append_turn(
                    session,
                    session_id=session_context.session_id,
                    principal=command.principal,
                    request_id=command.request_id,
                    question=command.question,
                    task_kind=command.task_kind.value,
                    target_object_ids=list(context.state.targets),
                    knowledge_revision=context.state.last_world_revision,
                    context_id=f"context:{run_id}",
                    decision_ref=decision.decision_id,
                    investigation_ref=None,
                )
                result = QuestionResultView(
                    request_id=command.request_id,
                    session_id=session_context.session_id,
                    turn_index=turn.turn_index,
                    mode="completed",
                    execution_profile=profile.value,
                    decision=decision_view(decision.model_dump(mode="json"), stored.created_at),
                )
                complete_command(
                    record, f"{session_context.session_id}:{turn.turn_index}",
                    result.model_dump(mode="json"),
                )
            return result

        continuation_target = _continuation_investigation_target(command, proposal.target_objects)
        if command.cve_id is None and command.object_id is None and continuation_target is None:
            async with session.begin():
                await self._execution.finish(
                    session,
                    execution_id,
                    status="blocked",
                    stop_reason="continuation_requires_bound_target",
                )
                await transition_task_run(
                    session,
                    run_id=run_id,
                    target=TaskRunStatus.BLOCKED,
                    payload_ref=f"task-run:{run_id}",
                    idempotency_key=f"question-blocked:{run_id}",
                    stream_name=self._stream_name,
                    producer="product-question",
                    stop_reason="continuation_requires_bound_target",
                )
            raise LifecycleConflictError(
                "question continuation requires a bound target before investigation escalation"
            )
        if context.case_ref is not None:
            investigation = await self._continue_investigation(
                session,
                command,
                case_id=context.case_ref,
                question=proposal.proposition_or_question,
                purpose=proposal.purpose,
                required_source_roles=proposal.evidence_contract.required_source_roles,
                priority=proposal.priority,
            )
        else:
            investigation = await self._start_investigation(
                session,
                command,
                proposal.proposition_or_question,
                purpose=proposal.purpose,
                required_source_roles=proposal.evidence_contract.required_source_roles,
                priority=proposal.priority,
                target_object_id=continuation_target,
            )
        # The investigation launch, session turn and parent task terminal record
        # now commit together; only the earlier sync model attempt is durable.
        await self._execution.finish(
            session,
            execution_id,
            status="completed",
            stop_reason="escalated_to_investigation",
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.COMPLETED,
            payload_ref=f"case:{investigation.case_id}",
            idempotency_key=f"question-escalated:{run_id}",
            stream_name=self._stream_name,
            producer="product-question",
            result_ref=f"case:{investigation.case_id}",
            stop_reason="escalated_to_investigation",
        )
        turn = await self._sessions.append_turn(
            session,
            session_id=session_context.session_id,
            principal=command.principal,
            request_id=command.request_id,
            question=command.question,
            task_kind=command.task_kind.value,
            target_object_ids=investigation.target_object_ids,
            knowledge_revision=context.state.last_world_revision,
            context_id=f"context:{run_id}",
            decision_ref=None,
            investigation_ref=f"case:{investigation.case_id}",
        )
        result = QuestionResultView(
            request_id=command.request_id,
            session_id=session_context.session_id,
            turn_index=turn.turn_index,
            mode="accepted",
            execution_profile=investigation.execution_profile or "INVESTIGATE",
            investigation=investigation,
        )
        complete_command(
            record, f"{session_context.session_id}:{turn.turn_index}",
            result.model_dump(mode="json"),
        )
        await session.commit()
        return result

    async def _open_sync_runtime(
        self,
        session: AsyncSession,
        *,
        command: AskQuestionCommand,
        context: _QuestionContext,
        session_context: QuestionSessionContext,
    ) -> tuple[str, str, ExecutionProfile]:
        policy = load_runtime_policy(self._policy_path)
        intent = TaskIntentParser().parse(
            raw_request=command.question,
            trigger_ref=f"product-request:{command.request_id}",
            candidate_task_kind=command.task_kind,
            candidate_targets=list(context.state.targets),
            requested_output={"result_type": "DecisionResult"},
            requested_actions=["answer_question"],
        )
        admission = await create_task_contract_service(policy).admit(
            TaskAdmissionRequest(
                intent=intent,
                principal=command.principal,
                policy_revision=policy.policy_revision,
                binding_context={
                    "question": command.question,
                    "target_object_ids": cast(JsonValue, list(context.state.targets)),
                    "product_session_id": session_context.session_id,
                },
            )
        )
        profile = (
            ExecutionProfile.DIRECT
            if command.task_kind is TaskKind.LOOKUP
            else ExecutionProfile.RETRIEVE
        )
        run_id = str(uuid4())
        execution_id = f"execution:{run_id}"
        budget_ref = f"budget:{run_id}"
        manifest = ContextManifest(
            context_id=f"context:{run_id}",
            context_revision=1,
            parent_context_id=(
                session_context.latest_turn.context_id if session_context.latest_turn else None
            ),
            task_contract_ref=(
                f"{admission.contract.task_contract_id}@{admission.contract.contract_revision}"
            ),
            role_ref="DecisionRole@1",
            case_ref=context.case_ref,
            knowledge_revision=context.state.last_world_revision,
            investigation_state_ref=context.investigation_state_ref,
            object_refs=list(context.object_refs),
            relation_refs=list(context.relation_refs),
            evidence_refs=list(context.evidence_refs),
            retrieval_invocation_refs=list(context.retrieval_invocation_refs),
            policy_context_ref=f"policy-context:{policy.policy_revision}",
            capability_envelope_ref=(
                "capability:question:case-read-v1"
                if context.case_ref is not None
                else "capability:question:local-read-v1"
            ),
            budget_ref=budget_ref,
        )
        await create_task_run(
            session,
            contract=admission.contract,
            manifest=manifest,
            role=canonical_roles()["DecisionRole"],
            execution_envelope_ref=execution_id,
            stream_name=self._stream_name,
            case_id=context.case_ref,
            run_id=run_id,
            producer="product-question",
        )
        await self._budget.create_account(
            session,
            account_id=budget_ref,
            task_run_id=run_id,
            limits=BudgetLimits(
                quantities={
                    "wall_seconds": Decimal(command.interactive_timeout_seconds),
                    "agent_turns": Decimal(1),
                    "tool_calls": Decimal(0),
                }
            ),
        )
        await self._execution.create(
            session,
            ExecutionEnvelope(
                execution_id=execution_id,
                task_contract_id=admission.contract.task_contract_id,
                task_run_id=run_id,
                role_revision="DecisionRole@1",
                context_manifest_revision=1,
                execution_profile=profile,
                capability_scope=[],
                deadline_at=datetime.now(UTC)
                + timedelta(seconds=command.interactive_timeout_seconds),
                budget_ref=budget_ref,
                policy_revision=policy.policy_revision,
                identity_scope=["public"],
                network_policy="local-only",
                side_effect_policy="read-only",
                sandbox_profile_revision="none@1",
                trace_context={
                    "request_id": command.request_id,
                    "trace_id": command.trace_id,
                    "product_session_id": session_context.session_id,
                    "surface": "product-api",
                },
            ),
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref="queue:product-question",
            idempotency_key=f"question-queued:{run_id}",
            stream_name=self._stream_name,
            producer="product-question",
        )
        await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.RUNNING,
            payload_ref="role:DecisionRole@1",
            idempotency_key=f"question-running:{run_id}",
            stream_name=self._stream_name,
            producer="product-question",
        )
        await self._execution.start(session, execution_id)
        return run_id, execution_id, profile

    async def _session_history_payload(
        self,
        session: AsyncSession,
        context: QuestionSessionContext,
    ) -> list[dict[str, JsonValue]]:
        payload: list[dict[str, JsonValue]] = []
        for turn in context.turns:
            item: dict[str, JsonValue] = {
                "turn_index": turn.turn_index,
                "user_input": turn.question,
                "target_object_ids": cast(JsonValue, list(turn.target_object_ids)),
                "knowledge_revision": turn.knowledge_revision,
            }
            if turn.decision_ref is not None:
                decision = await self._decisions.get_optional(session, turn.decision_ref)
                item["outcome"] = cast(
                    JsonValue,
                    {
                        "kind": "decision",
                        "decision_ref": turn.decision_ref,
                        "answer": decision.answer_payload if decision is not None else {},
                        "conclusions": (
                            [conclusion.statement for conclusion in decision.conclusions]
                            if decision is not None
                            else []
                        ),
                    },
                )
            elif turn.investigation_ref is not None:
                item["outcome"] = cast(
                    JsonValue,
                    {
                        "kind": "investigation",
                        "investigation_ref": turn.investigation_ref,
                    },
                )
            payload.append(item)
        return payload

    async def _load_context(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
        *,
        session_context: QuestionSessionContext,
        turn_index: int,
        active_case_id: str | None = None,
    ) -> _QuestionContext:
        if active_case_id is not None:
            return await self._load_active_case_context(
                session,
                command,
                session_context=session_context,
                turn_index=turn_index,
                case_id=active_case_id,
            )
        view = await _resolve_optional_target(session, command)
        revision = int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)
        confirmed: list[InvestigationStateItem] = []
        tentative: list[InvestigationStateItem] = []
        citations: dict[str, CitationSource] = {}
        object_refs: list[str] = []
        relation_refs: list[str] = []
        evidence_refs: list[str] = []
        retrieval_invocation_refs: list[str] = []
        targets: list[str] = []

        if view is not None:
            targets.append(view.object_id)
            object_refs.append(f"object:{view.object_id}")
            development_target_ids: list[str] = []
            for claim in view.claims:
                refs = _evidence_refs(claim.evidence, citations)
                if not refs:
                    continue
                confirmed.append(
                    InvestigationStateItem(
                        proposition=render_claim_fact(
                            view.canonical_key,
                            claim.predicate,
                            claim.value,
                            qualifier=claim.qualifier,
                        ),
                        target_ref=f"object:{view.object_id}",
                        evidence_refs=refs,
                        writer="M3Knowledge",
                        reason_code="product_question_context",
                        updated_revision=max(1, claim.created_revision),
                    )
                )
                evidence_refs.extend(refs)
            for relation in view.relations:
                refs = _evidence_refs(relation.evidence, citations)
                if not refs:
                    continue
                relation_ref = f"relation:{relation.relation_id}"
                relation_refs.append(relation_ref)
                confirmed.append(
                    InvestigationStateItem(
                        proposition=render_relation_fact(
                            view.canonical_key,
                            relation.relation_type,
                            relation.target.canonical_key,
                            qualifier=relation.qualifier,
                            target_properties=relation.target.properties,
                        ),
                        target_ref=relation_ref,
                        evidence_refs=refs,
                        writer="M3Knowledge",
                        reason_code="product_question_context",
                        updated_revision=max(1, relation.created_revision),
                    )
                )
                evidence_refs.extend(refs)
                if relation.relation_type == "references-development-object":
                    development_target_ids.append(relation.target.object_id)

            for target_id in _stable_unique(development_target_ids)[
                :_QUESTION_MAX_DEVELOPMENT_TARGETS
            ]:
                target_view = await get_object_by_id(session, target_id)
                if target_view is None:
                    continue
                object_refs.append(f"object:{target_view.object_id}")
                added = 0
                for relation in target_view.relations:
                    if relation.relation_type not in _QUESTION_SECOND_HOP_RELATION_TYPES:
                        continue
                    refs = _evidence_refs(relation.evidence, citations)
                    if not refs:
                        continue
                    relation_ref = f"relation:{relation.relation_id}"
                    relation_refs.append(relation_ref)
                    object_refs.append(f"object:{relation.target.object_id}")
                    confirmed.append(
                        InvestigationStateItem(
                            proposition=render_relation_fact(
                                target_view.canonical_key,
                                relation.relation_type,
                                relation.target.canonical_key,
                                qualifier=relation.qualifier,
                                target_properties=relation.target.properties,
                            ),
                            target_ref=relation_ref,
                            evidence_refs=refs,
                            writer="M3Knowledge",
                            reason_code="product_question_depth2_context",
                            updated_revision=max(1, relation.created_revision),
                        )
                    )
                    evidence_refs.extend(refs)
                    added += 1
                    if added >= _QUESTION_MAX_SECOND_HOP_RELATIONS:
                        break
        if command.task_kind is TaskKind.RETRIEVE:
            candidates, invocation_ref = await self._retrieve_candidates(
                session,
                command,
                session_context=session_context,
                turn_index=turn_index,
                revision=revision,
            )
            retrieval_invocation_refs.append(invocation_ref)
            for candidate in candidates:
                chunk_id = candidate.document_chunk_id
                text = candidate.payload.get("text")
                if not chunk_id or not isinstance(text, str) or not text.strip():
                    continue
                if (
                    command.cve_id is None
                    and command.object_id is None
                    and candidate.object_id is not None
                ):
                    targets.append(candidate.object_id)
                    object_refs.append(f"object:{candidate.object_id}")
                ref = _document_chunk_ref(candidate)
                source_ref = None
                canonical_url = candidate.payload.get("canonical_url")
                if isinstance(canonical_url, str) and canonical_url:
                    source_ref = canonical_url
                elif candidate.source_id:
                    source_ref = f"source:{candidate.source_id}"
                citations[ref] = CitationSource(
                    evidence_ref=ref,
                    source_ref=source_ref,
                    locator=cast(dict[str, JsonValue], dict(candidate.locator)),
                )
                tentative.append(
                    InvestigationStateItem(
                        proposition=f"retrieved passage: {text[:2000]}",
                        target_ref=f"chunk:{chunk_id}",
                        evidence_refs=[ref],
                        writer="M4Perception",
                        reason_code="bounded_product_retrieval",
                        updated_revision=max(1, revision),
                    )
                )
                evidence_refs.append(ref)

        now = datetime.now(UTC)
        state = InvestigationState(
            case_id=f"question:{command.request_id}",
            case_revision=0,
            goal=command.question,
            targets=_stable_unique(targets),
            confirmed=confirmed,
            tentative=tentative,
            last_world_revision=revision,
            updated_at=now,
        )
        return _QuestionContext(
            state=state,
            citation_sources=list(citations.values()),
            object_refs=_stable_unique(object_refs),
            relation_refs=_stable_unique(relation_refs),
            evidence_refs=_stable_unique(evidence_refs),
            retrieval_invocation_refs=_stable_unique(retrieval_invocation_refs),
        )

    async def _load_active_case_context(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
        *,
        session_context: QuestionSessionContext,
        turn_index: int,
        case_id: str,
    ) -> _QuestionContext:
        state = await self._investigation_state.get_state(session, case_id)
        current_revision = await _current_knowledge_revision(session)
        if command.task_kind is TaskKind.RETRIEVE and state.last_world_revision != current_revision:
            raise LifecycleConflictError(
                "active investigation state must be refreshed before retrieval follow-up",
                context={
                    "case_id": case_id,
                    "case_world_revision": state.last_world_revision,
                    "current_world_revision": current_revision,
                },
            )

        citations = {
            item.evidence_ref: item for item in await _citation_sources_for_state(session, state)
        }
        evidence_refs = _state_evidence_refs(state)
        relation_refs = _stable_unique(
            [
                item.target_ref
                for group in _state_item_groups(state)
                for item in group
                if item.target_ref is not None and item.target_ref.startswith("relation:")
            ]
        )
        object_refs = _stable_unique([f"object:{item}" for item in state.targets])
        retrieval_invocation_refs: list[str] = []
        question_state = _question_state_projection(state, goal=command.question)

        if command.task_kind is TaskKind.RETRIEVE:
            candidates, invocation_ref = await self._retrieve_candidates(
                session,
                command,
                session_context=session_context,
                turn_index=turn_index,
                revision=current_revision,
            )
            retrieval_invocation_refs.append(invocation_ref)
            retrieved_items: list[InvestigationStateItem] = []
            for candidate in candidates:
                chunk_id = candidate.document_chunk_id
                text = candidate.payload.get("text")
                if not chunk_id or not isinstance(text, str) or not text.strip():
                    continue
                ref = _document_chunk_ref(candidate)
                source_ref = None
                canonical_url = candidate.payload.get("canonical_url")
                if isinstance(canonical_url, str) and canonical_url:
                    source_ref = canonical_url
                elif candidate.source_id:
                    source_ref = f"source:{candidate.source_id}"
                citations[ref] = CitationSource(
                    evidence_ref=ref,
                    source_ref=source_ref,
                    locator=cast(dict[str, JsonValue], dict(candidate.locator)),
                )
                retrieved_items.append(
                    InvestigationStateItem(
                        proposition=f"retrieved passage: {text[:2000]}",
                        target_ref=f"chunk:{chunk_id}",
                        evidence_refs=[ref],
                        writer="M4Perception",
                        reason_code="bounded_product_case_retrieval",
                        updated_revision=max(1, current_revision),
                    )
                )
                evidence_refs.append(ref)
            question_state = question_state.model_copy(
                update={
                    "tentative": [*question_state.tentative, *retrieved_items],
                    "updated_at": datetime.now(UTC),
                }
            )

        return _QuestionContext(
            state=question_state,
            citation_sources=list(citations.values()),
            case_ref=case_id,
            investigation_state_ref=f"case:{case_id}@{state.case_revision}",
            object_refs=object_refs,
            relation_refs=relation_refs,
            evidence_refs=_stable_unique(evidence_refs),
            retrieval_invocation_refs=_stable_unique(retrieval_invocation_refs),
        )

    async def _retrieve_candidates(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
        *,
        session_context: QuestionSessionContext,
        turn_index: int,
        revision: int,
    ) -> tuple[list[RetrievedCandidate], str]:
        request = RetrievalRequestCoordinate.lexical(
            query=command.question,
            knowledge_revision=revision,
            limit=command.retrieval_limit,
        )
        started_at = datetime.now(UTC)
        reusable = await self._retrieval_invocations.find_reusable(
            session,
            product_session_id=session_context.session_id,
            before_turn_index=turn_index,
            request=request,
        )
        candidates: list[RetrievedCandidate] | None = None
        disposition = RetrievalDisposition.EXECUTED
        reuse_of_invocation_id: str | None = None
        try:
            if reusable is not None:
                replayed = await self._retrieval.by_chunk_refs(
                    session,
                    refs=reusable.result_refs,
                )
                if len(replayed) == len(reusable.result_refs):
                    candidates = replayed
                    disposition = RetrievalDisposition.REUSED
                    reuse_of_invocation_id = reusable.invocation_id
            if candidates is None:
                candidates = await self._retrieval.search(
                    session,
                    query=command.question,
                    limit=command.retrieval_limit,
                )
        except Exception as exc:
            # No TaskRun/Context exists yet. Roll back any provisional command
            # claim, then commit only this failed physical retrieval attempt.
            await session.rollback()
            try:
                await self._retrieval_invocations.record_failed(
                    session,
                    request_owner_ref=f"product-request:{command.request_id}",
                    product_session_id=session_context.session_id,
                    product_turn_index=turn_index,
                    request=request,
                    failure_class=type(exc).__name__,
                    started_at=started_at,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                logging.getLogger(__name__).exception(
                    "failed to persist retrieval attempt", extra={"request_id": command.request_id}
                )
            raise
        invocation = await self._retrieval_invocations.record(
            session,
            request_owner_ref=f"product-request:{command.request_id}",
            product_session_id=session_context.session_id,
            product_turn_index=turn_index,
            request=request,
            result_refs=[_document_chunk_ref(candidate) for candidate in candidates],
            disposition=disposition,
            reuse_of_invocation_id=reuse_of_invocation_id,
            started_at=started_at,
        )
        return candidates, invocation.ref

    async def _start_investigation(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
        evidence_question: str,
        *,
        purpose: str = "answer_question",
        required_source_roles: list[str] | None = None,
        priority: int | None = None,
        target_object_id: str | None = None,
    ):
        kind = command.task_kind
        if kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            kind = TaskKind.INVESTIGATE_RELATION
        result = await StartInvestigationUseCase(
            policy_path=self._policy_path,
            task_event_stream_name=self._stream_name,
        ).execute(
            session,
            StartInvestigationCommand(
                principal=command.principal,
                request_id=command.request_id,
                trace_id=command.trace_id,
                cve_id=(None if target_object_id is not None else command.cve_id),
                object_id=target_object_id or command.object_id,
                goal=command.question,
                evidence_question=evidence_question,
                purpose=purpose,
                task_kind=kind,
                required_source_roles=(
                    list(required_source_roles)
                    if required_source_roles is not None
                    else command.required_source_roles
                ),
                priority=priority if priority is not None else command.priority,
                allow_wait=command.allow_wait,
                timeout_seconds=command.investigation_timeout_seconds,
                agent_turns=command.agent_turns,
                tool_calls=command.tool_calls,
            ),
            commit=False,
        )
        return result.investigation

    async def _continue_investigation(
        self,
        session: AsyncSession,
        command: AskQuestionCommand,
        *,
        case_id: str,
        question: str | None = None,
        purpose: str = "interactive_investigation_followup",
        required_source_roles: list[str] | None = None,
        priority: int | None = None,
    ):
        kind = command.task_kind
        if kind in {TaskKind.LOOKUP, TaskKind.RETRIEVE}:
            kind = TaskKind.INVESTIGATE_RELATION
        result = await ContinueInvestigationUseCase(
            policy_path=self._policy_path,
            task_event_stream_name=self._stream_name,
        ).execute(
            session,
            ContinueInvestigationCommand(
                principal=command.principal,
                request_id=command.request_id,
                trace_id=command.trace_id,
                case_id=case_id,
                question=question or command.question,
                purpose=purpose,
                task_kind=kind,
                required_source_roles=(
                    list(required_source_roles)
                    if required_source_roles is not None
                    else command.required_source_roles
                ),
                priority=priority if priority is not None else command.priority,
                allow_wait=command.allow_wait,
                timeout_seconds=command.investigation_timeout_seconds,
                agent_turns=command.agent_turns,
                tool_calls=command.tool_calls,
            ),
            commit=False,
        )
        return result.investigation


async def _resolve_optional_target(
    session: AsyncSession,
    command: AskQuestionCommand,
) -> KnowledgeObjectView | None:
    if command.cve_id is not None:
        view = await get_vulnerability_by_cve(session, command.cve_id)
        if view is None:
            raise ResourceNotFoundError(
                "vulnerability not found",
                context={"cve_id": command.cve_id.upper()},
            )
        return view
    if command.object_id is not None:
        view = await get_object_by_id(session, command.object_id)
        if view is None:
            raise ResourceNotFoundError(
                "intelligence object not found",
                context={"object_id": command.object_id},
            )
        return view
    return None


async def _current_knowledge_revision(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0)


async def _active_session_investigation_case_id(
    session: AsyncSession,
    investigation_ref: str | None,
) -> str | None:
    if investigation_ref is None:
        return None
    prefix = "case:"
    if not investigation_ref.startswith(prefix):
        raise LifecycleConflictError(
            "question session has an invalid investigation reference",
            context={"investigation_ref": investigation_ref},
        )
    case_id = investigation_ref.removeprefix(prefix)
    case = await session.get(InvestigationCaseModel, case_id)
    if case is None:
        raise ResourceNotFoundError(
            "investigation not found",
            context={"case_id": case_id},
        )
    if case.status in {"active", "waiting", "open", "running"}:
        return case_id
    return None


def _state_item_groups(state: InvestigationState) -> list[list[InvestigationStateItem]]:
    return [
        state.confirmed,
        state.tentative,
        state.conflicts,
        state.unknowns,
        state.hypotheses,
    ]


def _state_evidence_refs(state: InvestigationState) -> list[str]:
    return _stable_unique(
        [
            _canonical_evidence_ref(ref)
            for group in _state_item_groups(state)
            for item in group
            for ref in item.evidence_refs
        ]
    )


def _canonical_evidence_ref(ref: str) -> str:
    return ref if ref.startswith("evidence:") else f"evidence:{ref}"


def _question_state_projection(
    state: InvestigationState,
    *,
    goal: str,
) -> InvestigationState:
    def project(items: list[InvestigationStateItem]) -> list[InvestigationStateItem]:
        return [
            item.model_copy(
                update={
                    "evidence_refs": [_canonical_evidence_ref(ref) for ref in item.evidence_refs]
                }
            )
            for item in items
        ]

    return state.model_copy(
        update={
            "goal": goal,
            "confirmed": project(state.confirmed),
            "tentative": project(state.tentative),
            "conflicts": project(state.conflicts),
            "unknowns": project(state.unknowns),
            "hypotheses": project(state.hypotheses),
        }
    )


async def _citation_sources_for_state(
    session: AsyncSession,
    state: InvestigationState,
) -> list[CitationSource]:
    return await decision_citation_sources(
        session, _question_state_projection(state, goal=state.goal)
    )


def _evidence_refs(
    evidence: list[EvidenceRef],
    citations: dict[str, CitationSource],
) -> list[str]:
    refs: list[str] = []
    for item in evidence:
        refs.append(item.evidence_ref)
        source_ref = f"source:{item.source_id}:{item.external_object_id}"
        if item.external_revision:
            source_ref += f"@{item.external_revision}"
        citations[item.evidence_ref] = CitationSource(
            evidence_ref=item.evidence_ref,
            source_ref=source_ref,
            locator=cast(dict[str, JsonValue], dict(item.locator)),
        )
    return _stable_unique(refs)


def _document_chunk_ref(candidate: RetrievedCandidate) -> str:
    chunk_id = candidate.document_chunk_id
    if not chunk_id:
        raise ValueError("retrieval candidate is missing document_chunk_id")
    return f"document-chunk:{chunk_id}@{candidate.revision or 'current'}"


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _continuation_investigation_target(
    command: AskQuestionCommand,
    target_objects: list[str],
) -> str | None:
    if command.cve_id is not None or command.object_id is not None:
        return None
    unique = _stable_unique(target_objects)
    return unique[0] if len(unique) == 1 else None


def _bind_session_target(
    command: AskQuestionCommand,
    context: QuestionSessionContext,
) -> AskQuestionCommand:
    if command.cve_id is not None or command.object_id is not None:
        return command
    latest = context.latest_turn
    if latest is None:
        return command
    targets = _stable_unique(latest.target_object_ids)
    if len(targets) == 1:
        return command.model_copy(update={"object_id": targets[0]})
    if command.task_kind is not TaskKind.RETRIEVE:
        raise LifecycleConflictError(
            "question follow-up requires exactly one carried target",
            context={"session_id": context.session_id, "target_count": len(targets)},
        )
    return command
