from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, Field, JsonValue, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.application.errors import (
    LifecycleConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from apps.application.queries.investigations import InvestigationQueries
from apps.application.views.investigations import StartInvestigationResult
from apps.task_admission import create_task_contract_service
from packages.intelligence.knowledge.read import get_vulnerability_by_cve
from packages.intelligence.storage.knowledge_models import KnowledgeRevisionModel, ObjectModel
from packages.investigation.cases.service import CaseService
from packages.investigation.state.contracts import CaseLifecycle, EvidenceNeedContract
from packages.investigation.state.service import InvestigationStateService
from packages.investigation.storage.models import InvestigationCaseModel
from packages.runtime.budget import BudgetGovernor, BudgetLimits
from packages.runtime.execution.service import ExecutionRunService
from packages.runtime.policy.loader import load_runtime_policy
from packages.task_runtime.admission import (
    TaskAdmissionDenied,
    TaskAdmissionRequest,
    TaskAdmissionResult,
)
from packages.task_runtime.contracts.execution import ExecutionEnvelope
from packages.task_runtime.contracts.models import (
    ContextManifest,
    ExecutionProfile,
    TaskIntent,
    TaskKind,
    TaskRun,
    TaskRunStatus,
)
from packages.task_runtime.contracts.roles import canonical_roles
from packages.task_runtime.storage.models import TaskRunModel
from packages.task_runtime.storage.service import create_task_run, transition_task_run


class StartInvestigationCommand(BaseModel):
    principal: str
    request_id: str
    trace_id: str | None = None
    cve_id: str | None = None
    object_id: str | None = None
    goal: str = Field(min_length=1)
    evidence_question: str = Field(min_length=1)
    purpose: str = "interactive_investigation"
    task_kind: TaskKind = TaskKind.INVESTIGATE_RELATION
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    allow_wait: bool = True
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)

    @model_validator(mode="after")
    def validate_target(self) -> StartInvestigationCommand:
        if bool(self.cve_id) == bool(self.object_id):
            raise ValueError("exactly one of cve_id or object_id is required")
        if self.task_kind not in _INVESTIGATION_KINDS:
            raise ValueError("task_kind is not an InvestigationRole task")
        return self


class InvestigationLaunchResult(BaseModel):
    run: TaskRun
    admission: TaskAdmissionResult
    execution_profile: ExecutionProfile
    execution_id: str


class ContinueInvestigationCommand(BaseModel):
    principal: str
    request_id: str
    case_id: str
    trace_id: str | None = None
    question: str = Field(min_length=1)
    purpose: str = "interactive_investigation_followup"
    task_kind: TaskKind = TaskKind.INVESTIGATE_RELATION
    required_source_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    allow_wait: bool = True
    timeout_seconds: int = Field(default=300, ge=30, le=3600)
    agent_turns: int = Field(default=8, ge=1, le=64)
    tool_calls: int = Field(default=12, ge=0, le=128)

    @model_validator(mode="after")
    def validate_kind(self) -> ContinueInvestigationCommand:
        if self.task_kind not in _INVESTIGATION_KINDS:
            raise ValueError("task_kind is not an InvestigationRole task")
        return self


class InvestigationTaskLauncher:
    def __init__(
        self,
        *,
        policy_path: Path,
        task_event_stream_name: str,
        state_service: InvestigationStateService | None = None,
        budget_governor: BudgetGovernor | None = None,
        execution_service: ExecutionRunService | None = None,
    ) -> None:
        self._policy_path = policy_path
        self._stream_name = task_event_stream_name
        self._state = state_service or InvestigationStateService()
        self._budget = budget_governor or BudgetGovernor()
        self._execution = execution_service or ExecutionRunService()

    async def launch(
        self,
        session: AsyncSession,
        *,
        case_id: str,
        task_kind: TaskKind,
        required_need_ids: list[str],
        principal: str,
        trigger_ref: str,
        surface: str,
        request_id: str | None,
        trace_id: str | None,
        allow_wait: bool,
        timeout_seconds: int,
        agent_turns: int,
        tool_calls: int,
    ) -> InvestigationLaunchResult:
        case = await session.get(InvestigationCaseModel, case_id)
        if case is None:
            raise ResourceNotFoundError(
                "investigation not found",
                context={"case_id": case_id},
            )
        state = await self._state.get_state(session, case_id)
        if not required_need_ids:
            raise ValueError("investigation requires at least one EvidenceNeed")

        policy = load_runtime_policy(self._policy_path)
        try:
            admission = await create_task_contract_service(policy).admit(
                TaskAdmissionRequest(
                    intent=TaskIntent(
                        trigger_ref=trigger_ref,
                        candidate_task_kind=task_kind,
                        candidate_targets=[case_id, *case.target_object_ids],
                        requested_actions=["investigate_case"],
                    ),
                    principal=principal,
                    policy_revision=policy.policy_revision,
                    binding_context={
                        "case_id": case_id,
                        "target_object_ids": cast(JsonValue, list(case.target_object_ids)),
                        "required_need_ids": cast(JsonValue, required_need_ids),
                        "allow_wait": allow_wait,
                    },
                )
            )
        except TaskAdmissionDenied as exc:
            raise PermissionDeniedError(str(exc)) from exc

        run_id = str(uuid4())
        budget_ref = f"budget:{run_id}"
        execution_id = f"execution:{run_id}"
        profile = _execution_profile(task_kind)
        manifest = ContextManifest(
            context_id=f"context:{run_id}",
            context_revision=1,
            task_contract_ref=(
                f"{admission.contract.task_contract_id}@{admission.contract.contract_revision}"
            ),
            role_ref="InvestigationRole@1",
            case_ref=case_id,
            knowledge_revision=state.last_world_revision or case.initial_knowledge_revision or 0,
            investigation_state_ref=f"case:{case_id}@{state.case_revision}",
            object_refs=list(case.target_object_ids),
            policy_context_ref=f"policy-context:{policy.policy_revision}",
            capability_envelope_ref="capability:investigation:local-v1",
            budget_ref=budget_ref,
        )
        await create_task_run(
            session,
            contract=admission.contract,
            manifest=manifest,
            role=canonical_roles()["InvestigationRole"],
            execution_envelope_ref=execution_id,
            stream_name=self._stream_name,
            case_id=case_id,
            run_id=run_id,
            producer=surface,
        )
        await self._budget.create_account(
            session,
            account_id=budget_ref,
            task_run_id=run_id,
            limits=BudgetLimits(
                quantities={
                    "agent_turns": Decimal(agent_turns),
                    "tool_calls": Decimal(tool_calls),
                }
            ),
        )
        trace_context: dict[str, JsonValue] = {
            "trigger_ref": trigger_ref,
            "surface": surface,
        }
        if request_id:
            trace_context["request_id"] = request_id
        if trace_id:
            trace_context["trace_id"] = trace_id
        await self._execution.create(
            session,
            ExecutionEnvelope(
                execution_id=execution_id,
                task_contract_id=admission.contract.task_contract_id,
                task_run_id=run_id,
                case_id=case_id,
                role_revision="InvestigationRole@1",
                context_manifest_revision=1,
                execution_profile=profile,
                capability_scope=[],
                deadline_at=datetime.now(UTC) + timedelta(seconds=timeout_seconds),
                budget_ref=budget_ref,
                policy_revision=policy.policy_revision,
                identity_scope=["public"],
                network_policy="local-only",
                side_effect_policy="internal-state-only",
                sandbox_profile_revision="process_restricted@1",
                trace_context=trace_context,
            ),
        )
        queued = await transition_task_run(
            session,
            run_id=run_id,
            target=TaskRunStatus.QUEUED,
            payload_ref=f"queue:{surface}",
            idempotency_key=f"queued:{surface}:{run_id}",
            stream_name=self._stream_name,
            producer=surface,
        )
        return InvestigationLaunchResult(
            run=queued,
            admission=admission,
            execution_profile=profile,
            execution_id=execution_id,
        )


class StartInvestigationUseCase:
    def __init__(
        self,
        *,
        policy_path: Path,
        task_event_stream_name: str,
        case_service: CaseService | None = None,
        state_service: InvestigationStateService | None = None,
        queries: InvestigationQueries | None = None,
    ) -> None:
        self._case_service = case_service or CaseService()
        self._state = state_service or InvestigationStateService()
        self._queries = queries or InvestigationQueries(self._state)
        self._launcher = InvestigationTaskLauncher(
            policy_path=policy_path,
            task_event_stream_name=task_event_stream_name,
            state_service=self._state,
        )

    async def execute(
        self,
        session: AsyncSession,
        command: StartInvestigationCommand,
    ) -> StartInvestigationResult:
        object_id = await _resolve_target(session, command)
        knowledge_revision = int(
            await session.scalar(select(func.max(KnowledgeRevisionModel.revision))) or 0
        )
        case = await self._case_service.create(
            session,
            task_signature=f"product:{command.task_kind.value}",
            target_object_ids=[object_id],
            goal=command.goal,
            initial_knowledge_revision=knowledge_revision,
        )
        opened = await self._state.open_evidence_need(
            session,
            case_id=case.case_id,
            base_case_revision=0,
            need_id=str(uuid4()),
            proposition_or_question=command.evidence_question,
            purpose=command.purpose,
            target_objects=[object_id],
            evidence_contract=EvidenceNeedContract(
                required_source_roles=command.required_source_roles
            ),
            priority=command.priority,
            writer="product-application",
            reason_code="product_investigation_started",
        )
        await self._launcher.launch(
            session,
            case_id=case.case_id,
            task_kind=command.task_kind,
            required_need_ids=[opened.need.need_id],
            principal=command.principal,
            trigger_ref=f"product-request:{command.request_id}",
            surface="product-api",
            request_id=command.request_id,
            trace_id=command.trace_id,
            allow_wait=command.allow_wait,
            timeout_seconds=command.timeout_seconds,
            agent_turns=command.agent_turns,
            tool_calls=command.tool_calls,
        )
        await self._case_service.activate(session, case.case_id)
        await session.commit()
        return StartInvestigationResult(
            investigation=await self._queries.get(
                session,
                case.case_id,
                principal=command.principal,
            )
        )


class ContinueInvestigationUseCase:
    def __init__(
        self,
        *,
        policy_path: Path,
        task_event_stream_name: str,
        case_service: CaseService | None = None,
        state_service: InvestigationStateService | None = None,
        queries: InvestigationQueries | None = None,
    ) -> None:
        self._cases = case_service or CaseService()
        self._state = state_service or InvestigationStateService()
        self._queries = queries or InvestigationQueries(self._state)
        self._launcher = InvestigationTaskLauncher(
            policy_path=policy_path,
            task_event_stream_name=task_event_stream_name,
            state_service=self._state,
        )

    async def execute(
        self,
        session: AsyncSession,
        command: ContinueInvestigationCommand,
    ) -> StartInvestigationResult:
        case = await session.scalar(
            select(InvestigationCaseModel)
            .where(InvestigationCaseModel.case_id == command.case_id)
            .with_for_update()
        )
        if case is None:
            raise ResourceNotFoundError(
                "investigation not found",
                context={"case_id": command.case_id},
            )
        if case.status not in {
            CaseLifecycle.ACTIVE.value,
            CaseLifecycle.WAITING.value,
            "open",
            "running",
        }:
            raise LifecycleConflictError(
                "investigation is not open for follow-up",
                context={"case_id": command.case_id, "status": case.status},
            )
        active_run_id = await session.scalar(
            select(TaskRunModel.run_id)
            .where(
                TaskRunModel.case_id == command.case_id,
                TaskRunModel.role_id == "InvestigationRole",
                TaskRunModel.status.in_(
                    [
                        TaskRunStatus.SUBMITTED.value,
                        TaskRunStatus.QUEUED.value,
                        TaskRunStatus.RUNNING.value,
                        TaskRunStatus.WAITING_INPUT.value,
                        TaskRunStatus.WAITING_DEPENDENCY.value,
                    ]
                ),
            )
            .order_by(TaskRunModel.created_at.desc())
            .limit(1)
        )
        if active_run_id is not None:
            raise LifecycleConflictError(
                "investigation already has an active runtime episode",
                context={"case_id": command.case_id, "task_run_id": active_run_id},
            )

        state = await self._state.get_state(session, command.case_id)
        opened = await self._state.open_evidence_need(
            session,
            case_id=command.case_id,
            base_case_revision=state.case_revision,
            need_id=str(uuid4()),
            proposition_or_question=command.question,
            purpose=command.purpose,
            target_objects=list(case.target_object_ids),
            evidence_contract=EvidenceNeedContract(
                required_source_roles=command.required_source_roles
            ),
            priority=command.priority,
            writer="product-application",
            reason_code="product_investigation_followup",
        )
        await self._launcher.launch(
            session,
            case_id=command.case_id,
            task_kind=command.task_kind,
            required_need_ids=[opened.need.need_id],
            principal=command.principal,
            trigger_ref=f"product-request:{command.request_id}",
            surface="product-api-followup",
            request_id=command.request_id,
            trace_id=command.trace_id,
            allow_wait=command.allow_wait,
            timeout_seconds=command.timeout_seconds,
            agent_turns=command.agent_turns,
            tool_calls=command.tool_calls,
        )
        await self._cases.activate(session, command.case_id)
        await session.commit()
        return StartInvestigationResult(
            investigation=await self._queries.get(
                session,
                command.case_id,
                principal=command.principal,
            )
        )


async def _resolve_target(session: AsyncSession, command: StartInvestigationCommand) -> str:
    if command.object_id is not None:
        target = await session.get(ObjectModel, command.object_id)
        if target is None:
            raise ResourceNotFoundError(
                "intelligence object not found",
                context={"object_id": command.object_id},
            )
        return target.object_id
    assert command.cve_id is not None
    vulnerability = await get_vulnerability_by_cve(session, command.cve_id)
    if vulnerability is None:
        raise ResourceNotFoundError(
            "vulnerability not found",
            context={"cve_id": command.cve_id.upper()},
        )
    return vulnerability.object_id


def _execution_profile(task_kind: TaskKind) -> ExecutionProfile:
    if task_kind is TaskKind.VERIFY_VERSION_FIX:
        return ExecutionProfile.VERIFY
    if task_kind is TaskKind.WATCH_INCIDENT:
        return ExecutionProfile.WATCH
    return ExecutionProfile.INVESTIGATE


_INVESTIGATION_KINDS = {
    TaskKind.VERIFY_VERSION_FIX,
    TaskKind.RESOLVE_CONFLICT,
    TaskKind.INVESTIGATE_RELATION,
    TaskKind.INVESTIGATE_INCIDENT,
    TaskKind.WATCH_INCIDENT,
    TaskKind.ASSESS_NORMATIVE_APPLICABILITY,
    TaskKind.OBSERVE_LIVE_ASSET,
}
